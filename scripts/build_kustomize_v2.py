#!/usr/bin/env python3
import os
import yaml

DUMP_DIR = "/ai/utilities/halo_admin_utility/cache/halo/deployment/dump"
DEPLOYMENT_DIR = "/ai/utilities/halo_admin_utility/cache/halo/deployment"

BASE_COMPONENTS = ["backend", "config-analyzer", "dashboard", "oauth2-proxy", "redis"]
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
                clean_env.append({'name': e['name'], 'value': str(e.get('value', ''))})
                
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

def build_pristine_deployment(comp, info, namespace=None, is_base=True):
    base_path = f"deployments/base/{comp}/deployment.yaml" if is_base else f"deployments/tenants/slo/{namespace}/{comp}-deployment.yaml"
    dep = {
        'apiVersion': 'apps/v1',
        'kind': 'Deployment',
        'metadata': {
            'name': comp,
            'annotations': {
                'halo-admin/source-file': base_path
            },
            'labels': {'app': comp}
        },
        'spec': {
            'replicas': 1,
            'selector': {'matchLabels': {'app': comp}},
            'template': {
                'metadata': {'labels': {'app': comp}},
                'spec': {
                    'imagePullSecrets': [{'name': 'halo-gitlab'}],
                    'containers': [{
                        'name': comp,
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

def build_pristine_service(comp, dump_data, namespace=None, is_base=True):
    base_path = f"deployments/base/{comp}/service.yaml" if is_base else f"deployments/tenants/slo/{namespace}/{comp}-service.yaml"
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
            'name': comp if comp != 'oauth2-proxy' else 'oauth2-proxy-svc',
            'annotations': {
                'halo-admin/source-file': base_path
            },
            'labels': {'app': comp}
        },
        'spec': {
            'type': svc_type,
            'selector': {'app': comp},
            'ports': ports
        }
    }
    if namespace:
        svc['metadata']['namespace'] = namespace
    return svc

def build_pristine_ingress(name, dump_data, namespace):
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
            'namespace': namespace,
            'annotations': {
                'halo-admin/source-file': f"deployments/tenants/slo/{namespace}/ingress-{name}.yaml"
            }
        },
        'spec': {'rules': rules}
    }
    
    # Add tls if present
    if dump_data and 'spec' in dump_data and dump_data['spec'].get('tls'):
        tls_clean = []
        for t in dump_data['spec']['tls']:
            tls_clean.append({
                'hosts': t.get('hosts', []),
                'secretName': t.get('secret_name', '')
            })
        ing['spec']['tls'] = tls_clean
        
    return ing

def build_pristine_configmap(name, dump_data, namespace):
    cm = {
        'apiVersion': 'v1',
        'kind': 'ConfigMap',
        'metadata': {
            'name': name,
            'namespace': namespace,
            'annotations': {
                'halo-admin/source-file': f"deployments/tenants/slo/{namespace}/configmap-{name}.yaml"
            }
        },
        'data': {}
    }
    
    if dump_data and dump_data.get('data'):
        for k, v in dump_data['data'].items():
            if 'cert' in k.lower() or 'key' in k.lower() or name == 'oauth2-proxy-certs':
                cm['data'][k] = "<redacted-certificate-data>"
            else:
                cm['data'][k] = v
                
    return cm

def build_pristine_pvc(name, dump_data, namespace):
    pvc = {
        'apiVersion': 'v1',
        'kind': 'PersistentVolumeClaim',
        'metadata': {
            'name': name,
            'namespace': namespace,
            'annotations': {
                'halo-admin/source-file': f"deployments/tenants/slo/{namespace}/pvc-{name}.yaml"
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
    return pvc

def generate_base():
    base_dir = os.path.join(DEPLOYMENT_DIR, "base")
    for comp in BASE_COMPONENTS:
        comp_dir = os.path.join(base_dir, comp)
        os.makedirs(comp_dir, exist_ok=True)
        dep_file = f"{DUMP_DIR}/app_halo-babel_Deployment_{comp}.yaml"
        dump_dep = yaml.safe_load(open(dep_file)) if os.path.exists(dep_file) else {}
        svc_name = comp if comp != "oauth2-proxy" else "oauth2-proxy-svc"
        svc_file = f"{DUMP_DIR}/app_halo-babel_Service_{svc_name}.yaml"
        dump_svc = yaml.safe_load(open(svc_file)) if os.path.exists(svc_file) else {}
        
        info = extract_container_info(dump_dep)
        clean_dep = build_pristine_deployment(comp, info, is_base=True)
        clean_svc = build_pristine_service(comp, dump_svc, is_base=True)
        
        yaml.dump(clean_dep, open(os.path.join(comp_dir, 'deployment.yaml'), 'w'), sort_keys=False)
        yaml.dump(clean_svc, open(os.path.join(comp_dir, 'service.yaml'), 'w'), sort_keys=False)
        yaml.dump({'resources': ['deployment.yaml', 'service.yaml']}, open(os.path.join(comp_dir, 'kustomization.yaml'), 'w'), sort_keys=False)

def generate_tenants():
    for tenant in TENANTS:
        tenant_dir = os.path.join(DEPLOYMENT_DIR, "tenants", "slo", tenant)
        os.makedirs(tenant_dir, exist_ok=True)
        
        resources = []
        
        for file in sorted(os.listdir(DUMP_DIR)):
            if file.startswith(f"app_{tenant}_") or file.startswith(f"gpu_halo_") and tenant in file:
                parts = file.split("_")
                kind = parts[2]
                name = parts[3].replace(".yaml", "")
                
                if kind in ["Deployment", "Service"] and name in BASE_COMPONENTS + ["oauth2-proxy-svc"]:
                    continue
                    
                dump_data = yaml.safe_load(open(os.path.join(DUMP_DIR, file)))
                out_name = f"{kind.lower()}-{name}.yaml"
                
                if kind == "Ingress":
                    clean = build_pristine_ingress(name, dump_data, tenant)
                elif kind == "ConfigMap":
                    if name == "kube-root-ca.crt":
                        continue
                    clean = build_pristine_configmap(name, dump_data, tenant)
                elif kind == "PVC":
                    clean = build_pristine_pvc(name, dump_data, tenant)
                elif kind == "Deployment":
                    info = extract_container_info(dump_data)
                    clean = build_pristine_deployment(name, info, namespace=tenant, is_base=False)
                elif kind == "Service":
                    clean = build_pristine_service(name, dump_data, namespace=tenant, is_base=False)
                else:
                    continue
                    
                yaml.dump(clean, open(os.path.join(tenant_dir, out_name), 'w'), sort_keys=False)
                resources.append(out_name)
                
        # Also map GPU stuff correctly if corp/scott-dev
        # For GPU, we already matched `tenant in file` in the loop above.
        
        kustomization = {
            'namespace': tenant,
            'bases': [f"../../../../base/{comp}" for comp in BASE_COMPONENTS],
            'resources': resources
        }
        yaml.dump(kustomization, open(os.path.join(tenant_dir, 'kustomization.yaml'), 'w'), sort_keys=False)
        print(f"Generated pristine tenant {tenant}")

if __name__ == "__main__":
    generate_base()
    generate_tenants()
