#!/usr/bin/env python3
import os
import yaml

class multiline_str(str):
    pass

def represent_multiline_str(dumper, data):
    if '\n' in data:
        return dumper.represent_scalar('tag:yaml.org,2002:str', data, style='|')
    return dumper.represent_scalar('tag:yaml.org,2002:str', data)

yaml.add_representer(multiline_str, represent_multiline_str)
yaml.add_representer(multiline_str, represent_multiline_str, Dumper=yaml.SafeDumper)

DUMP_DIR = "/ai/utilities/halo_admin_utility/output/dump"
DEPLOYMENT_DIR = "/ai/utilities/halo_admin_utility/cache/halo/deployment"

BASE_APPS = ["backend", "config-analyzer", "dashboard", "oauth2-proxy", "redis"]
COLLECTORS = ["fluent-bit-firewall-ingest", "fluent-bit-syslog-ingest", "netflow-ingestion", "firewall-ingestion", "syslog-ingestion"]
MORPHEUS = ["gtt-core-syslog-pipeline", "gtt-corp-syslog-pipeline-v2", "gtt-corp-firewall-pipeline-v2", "gtt-corp-netflow-pipeline-v2", "gtt-scott-dev-syslog-pipeline", "triton", "triton-server"]
TENANTS = ["halo-babel", "halo-corp", "halo-scott-dev"]

def extract_container_info(dump_data):
    if not dump_data or 'spec' not in dump_data: return {}
    try:
        containers = dump_data['spec']['template']['spec']['containers']
        if not containers: return {}
        c = containers[0]
        
        clean_env = []
        if c.get('env'):
            for e in c['env']:
                val = e.get('value', '')
                clean_env.append({'name': e['name'], 'value': str(val)})
                
        clean_ports = []
        if c.get('ports'):
            for p in c['ports']:
                clean_ports.append({'containerPort': p.get('container_port')})
                
        volumes = dump_data['spec']['template']['spec'].get('volumes', [])
        clean_vols = []
        if volumes:
            for v in volumes:
                v_clean = {'name': v['name']}
                if v.get('config_map'):
                    v_clean['configMap'] = {'name': v['config_map']['name']}
                elif v.get('empty_dir') is not None:
                    v_clean['emptyDir'] = {}
                elif v.get('persistent_volume_claim'):
                    v_clean['persistentVolumeClaim'] = {'claimName': v['persistent_volume_claim']['claim_name']}
                elif v.get('host_path'):
                    v_clean['hostPath'] = {'path': v['host_path']['path']}
                if len(v_clean) > 1:
                    clean_vols.append(v_clean)
                    
        clean_mounts = []
        if c.get('volume_mounts'):
            for m in c['volume_mounts']:
                clean_mounts.append({'name': m['name'], 'mountPath': m['mount_path']})
                
        return {
            'image': c.get('image', ''),
            'command': c.get('command', []),
            'args': c.get('args', []),
            'env': clean_env,
            'ports': clean_ports,
            'volumeMounts': clean_mounts,
            'volumes': clean_vols
        }
    except Exception as e:
        return {}

def build_pristine_deployment(name, info, target_cluster, source_file, namespace=None):
    dep = {
        'apiVersion': 'apps/v1',
        'kind': 'Deployment',
        'metadata': {
            'name': name,
            'annotations': {
                'halo-admin/source-file': source_file,
                'halo/target-cluster': target_cluster
            },
            'labels': {'app': name}
        },
        'spec': {
            'replicas': 1,
            'selector': {'matchLabels': {'app': name}},
            'template': {
                'metadata': {'labels': {'app': name}},
                'spec': {
                    'imagePullSecrets': [{'name': 'halo-gitlab'}],
                    'containers': [{
                        'name': name,
                        'image': info.get('image', 'nginx:latest'),
                        'imagePullPolicy': 'Always',
                        'resources': {
                            'requests': {'cpu': '100m', 'memory': '128Mi'},
                            'limits': {'cpu': '500m', 'memory': '512Mi'}
                        },
                        'livenessProbe': {
                            'httpGet': {'path': '/health', 'port': info['ports'][0]['containerPort'] if info.get('ports') else 80},
                            'initialDelaySeconds': 15,
                            'periodSeconds': 20
                        },
                        'readinessProbe': {
                            'httpGet': {'path': '/health', 'port': info['ports'][0]['containerPort'] if info.get('ports') else 80},
                            'initialDelaySeconds': 5,
                            'periodSeconds': 10
                        }
                    }]
                }
            }
        }
    }
    if namespace:
        dep['metadata']['namespace'] = namespace
        
    c = dep['spec']['template']['spec']['containers'][0]
    if info.get('command'): c['command'] = info['command']
    if info.get('args'): c['args'] = info['args']
    if info.get('env'): c['env'] = info['env']
    if info.get('ports'): c['ports'] = info['ports']
    if info.get('volumeMounts'): c['volumeMounts'] = info['volumeMounts']
    if info.get('volumes'): dep['spec']['template']['spec']['volumes'] = info['volumes']
        
    return dep

def build_pristine_service(name, dump_data, target_cluster, source_file, namespace=None):
    ports = []
    if dump_data and 'spec' in dump_data and dump_data['spec'].get('ports'):
        for p in dump_data['spec']['ports']:
            ports.append({
                'name': p.get('name', 'http'),
                'port': p.get('port', 80),
                'targetPort': p.get('target_port', 80),
                'protocol': p.get('protocol', 'TCP')
            })
    else:
        ports = [{'name': 'http', 'port': 80, 'targetPort': 80}]
        
    svc_type = dump_data.get('spec', {}).get('type', 'ClusterIP') if dump_data else 'ClusterIP'
        
    svc = {
        'apiVersion': 'v1',
        'kind': 'Service',
        'metadata': {
            'name': name if name != 'oauth2-proxy' else 'oauth2-proxy-svc',
            'annotations': {
                'halo-admin/source-file': source_file,
                'halo/target-cluster': target_cluster
            },
            'labels': {'app': name}
        },
        'spec': {
            'type': svc_type,
            'selector': {'app': name},
            'ports': ports
        }
    }
    if namespace:
        svc['metadata']['namespace'] = namespace
    return svc

def build_pristine_configmap(name, dump_data, target_cluster, source_file, namespace=None):
    cm = {
        'apiVersion': 'v1',
        'kind': 'ConfigMap',
        'metadata': {
            'name': name,
            'annotations': {
                'halo-admin/source-file': source_file,
                'halo/target-cluster': target_cluster
            }
        },
        'data': {}
    }
    if namespace:
        cm['metadata']['namespace'] = namespace
        
    if dump_data and dump_data.get('data'):
        for k, v in dump_data['data'].items():
            if 'cert' in k.lower() or 'key' in k.lower() or name == 'oauth2-proxy-certs':
                cm['data'][k] = "<redacted-certificate-data>"
            else:
                if '\n' in v:
                    # Strip trailing spaces on all lines to force PyYAML to use block scalar '|'
                    cleaned_str = '\n'.join([line.rstrip() for line in v.split('\n')]).strip()
                    cm['data'][k] = multiline_str(cleaned_str)
                else:
                    cm['data'][k] = v
    return cm

def write_yaml(data, path):
    with open(path, 'w') as f:
        yaml.safe_dump(data, f, sort_keys=False)

def process_base(category, comps, target_cluster):
    base_dir = os.path.join(DEPLOYMENT_DIR, category)
    for comp in comps:
        comp_dir = os.path.join(base_dir, comp)
        os.makedirs(comp_dir, exist_ok=True)
        
        # Determine prefix for dump files
        prefix = "app_halo-corp" if target_cluster == "slo-hal-clu01" else "gpu_halo"
        if comp in BASE_APPS:
            prefix = "app_halo-babel"
            
        dep_file = f"{DUMP_DIR}/{prefix}_Deployment_{comp}.yaml"
        dump_dep = yaml.safe_load(open(dep_file)) if os.path.exists(dep_file) else {}
        svc_name = comp if comp != "oauth2-proxy" else "oauth2-proxy-svc"
        svc_file = f"{DUMP_DIR}/{prefix}_Service_{svc_name}.yaml"
        dump_svc = yaml.safe_load(open(svc_file)) if os.path.exists(svc_file) else {}
        
        source_dep = f"deployments/{category}/{comp}/deployment.yaml"
        source_svc = f"deployments/{category}/{comp}/service.yaml"
        
        info = extract_container_info(dump_dep)
        if info:
            clean_dep = build_pristine_deployment(comp, info, target_cluster, source_dep)
            write_yaml(clean_dep, os.path.join(comp_dir, 'deployment.yaml'))
            
        if dump_svc:
            clean_svc = build_pristine_service(comp, dump_svc, target_cluster, source_svc)
            write_yaml(clean_svc, os.path.join(comp_dir, 'service.yaml'))
            
        resources = []
        if info: resources.append('deployment.yaml')
        if dump_svc: resources.append('service.yaml')
        
        # Centralize redis-users.acl in base/redis instead of duplicating per tenant
        if comp == "redis":
            redis_cm_dump = yaml.safe_load(open(f"{DUMP_DIR}/{prefix}_ConfigMap_redis-users.acl.yaml"))
            redis_cm = build_pristine_configmap("redis-users.acl", redis_cm_dump, target_cluster, "deployments/base/redis/configmap-redis-users.acl.yaml")
            write_yaml(redis_cm, os.path.join(comp_dir, 'configmap-redis-users.acl.yaml'))
            resources.append('configmap-redis-users.acl.yaml')
        
        if resources:
            write_yaml({'resources': resources}, os.path.join(comp_dir, 'kustomization.yaml'))

def generate_tenants():
    for tenant in TENANTS:
        tenant_dir = os.path.join(DEPLOYMENT_DIR, "tenants", "slo", tenant)
        app_dir = os.path.join(tenant_dir, "app")
        gpu_dir = os.path.join(tenant_dir, "gpu")
        os.makedirs(app_dir, exist_ok=True)
        os.makedirs(gpu_dir, exist_ok=True)
        
        app_resources = []
        gpu_resources = []
        
        for file in sorted(os.listdir(DUMP_DIR)):
            if not file.startswith(f"app_{tenant}_") and not (file.startswith("gpu_halo_") and tenant.replace("halo-", "") in file):
                continue
                
            parts = file.split("_")
            cluster_type = parts[0]
            kind = parts[2]
            name = parts[3].replace(".yaml", "")
            
            # Skip base apps and base collectors / morpheus if they match perfectly (we will override them if they are custom named)
            # Actually, to make it simple, we just dump them into tenant folder if they are not in bases
            if kind in ["Deployment", "Service"] and name in BASE_APPS + COLLECTORS + MORPHEUS + ["oauth2-proxy-svc"]:
                continue
                
            dump_data = yaml.safe_load(open(os.path.join(DUMP_DIR, file)))
            
            target_cluster = "slo-hal-clu01" if cluster_type == "app" else "slo-aif-nvclu01"
            out_dir = app_dir if cluster_type == "app" else gpu_dir
            source_dir = f"deployments/tenants/slo/{tenant}/app" if cluster_type == "app" else f"deployments/tenants/slo/{tenant}/gpu"
            
            out_name = f"{kind.lower()}-{name}.yaml"
            source_path = f"{source_dir}/{out_name}"
            
            if kind == "Ingress":
                # Ingress handled simply
                rules = []
                if dump_data and 'spec' in dump_data and dump_data['spec'].get('rules'):
                    for r in dump_data['spec']['rules']:
                        rule = {'host': r.get('host', '')}
                        if r.get('http') and r['http'].get('paths'):
                            paths = []
                            for p in r['http']['paths']:
                                paths.append({
                                    'path': p.get('path', '/'),
                                    'pathType': p.get('path_type', 'Prefix'),
                                    'backend': {
                                        'service': {
                                            'name': p['backend']['service']['name'],
                                            'port': {'number': p['backend']['service']['port'].get('number', 80)}
                                        }
                                    }
                                })
                            rule['http'] = {'paths': paths}
                        rules.append(rule)
                ing = {
                    'apiVersion': 'networking.k8s.io/v1',
                    'kind': 'Ingress',
                    'metadata': {
                        'name': name,
                        'namespace': tenant,
                        'annotations': {
                            'halo-admin/source-file': source_path,
                            'halo/target-cluster': target_cluster
                        }
                    },
                    'spec': {'rules': rules}
                }
                if dump_data and 'spec' in dump_data and dump_data['spec'].get('tls'):
                    tls_clean = []
                    for t in dump_data['spec']['tls']:
                        tls_clean.append({
                            'hosts': t.get('hosts', []),
                            'secretName': t.get('secret_name', '')
                        })
                    ing['spec']['tls'] = tls_clean
                write_yaml(ing, os.path.join(out_dir, out_name))
                app_resources.append(out_name)
                
            elif kind == "ConfigMap":
                if name in ["kube-root-ca.crt", "redis-users.acl"]: continue
                cm = build_pristine_configmap(name, dump_data, target_cluster, source_path, tenant)
                write_yaml(cm, os.path.join(out_dir, out_name))
                if cluster_type == "app": app_resources.append(out_name)
                else: gpu_resources.append(out_name)
                
            elif kind == "PVC":
                pvc = {
                    'apiVersion': 'v1',
                    'kind': 'PersistentVolumeClaim',
                    'metadata': {
                        'name': name,
                        'namespace': tenant,
                        'annotations': {
                            'halo-admin/source-file': source_path,
                            'halo/target-cluster': target_cluster
                        }
                    },
                    'spec': {
                        'accessModes': dump_data.get('spec', {}).get('access_modes', ['ReadWriteOnce']),
                        'resources': {
                            'requests': {
                                'storage': dump_data.get('spec', {}).get('resources', {}).get('requests', {}).get('storage', '10Gi')
                            }
                        }
                    }
                }
                write_yaml(pvc, os.path.join(out_dir, out_name))
                if cluster_type == "app": app_resources.append(out_name)
                else: gpu_resources.append(out_name)
                
            elif kind == "Deployment":
                info = extract_container_info(dump_data)
                clean = build_pristine_deployment(name, info, target_cluster, source_path, tenant)
                write_yaml(clean, os.path.join(out_dir, out_name))
                if cluster_type == "app": app_resources.append(out_name)
                else: gpu_resources.append(out_name)
                
            elif kind == "Service":
                clean = build_pristine_service(name, dump_data, target_cluster, source_path, tenant)
                write_yaml(clean, os.path.join(out_dir, out_name))
                if cluster_type == "app": app_resources.append(out_name)
                else: gpu_resources.append(out_name)
                
        # Write kustomizations
        if app_resources or BASE_APPS:
            app_kust = {'namespace': tenant, 'resources': app_resources, 'bases': []}
            # Only babel and corp have standard apps
            app_kust['bases'].extend([f"../../../../../base/{c}" for c in BASE_APPS])
            if tenant == "halo-corp":
                app_kust['bases'].extend([f"../../../../../collectors/{c}" for c in ["fluent-bit-firewall-ingest", "fluent-bit-syslog-ingest", "netflow-ingestion", "firewall-ingestion", "syslog-ingestion"]])
            
            write_yaml(app_kust, os.path.join(app_dir, 'kustomization.yaml'))
            
        if gpu_resources or tenant == "halo-corp" or tenant == "halo-scott-dev":
            gpu_kust = {'namespace': "halo", 'resources': gpu_resources, 'bases': []} # gpu runs in halo namespace
            if tenant == "halo-corp":
                gpu_kust['bases'].extend([f"../../../../../morpheus_runtime/{c}" for c in ["gtt-corp-syslog-pipeline-v2", "gtt-corp-firewall-pipeline-v2", "gtt-corp-netflow-pipeline-v2"]])
            elif tenant == "halo-scott-dev":
                gpu_kust['bases'].extend([f"../../../../../morpheus_runtime/gtt-scott-dev-syslog-pipeline"])
                
            if gpu_resources or gpu_kust['bases']:
                write_yaml(gpu_kust, os.path.join(gpu_dir, 'kustomization.yaml'))

if __name__ == "__main__":
    process_base("base", BASE_APPS, "slo-hal-clu01")
    process_base("collectors", COLLECTORS, "slo-hal-clu01")
    process_base("morpheus_runtime", MORPHEUS, "slo-aif-nvclu01")
    generate_tenants()
