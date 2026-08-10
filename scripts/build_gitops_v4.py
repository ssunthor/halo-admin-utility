#!/usr/bin/env python3
import os
import yaml
import glob
import re
from copy import deepcopy

DUMP_DIR = "/ai/utilities/halo_admin_utility/output/dump"
DEPLOYMENT_DIR = "/ai/utilities/halo_admin_utility/cache/halo/deployment"

def multiline_str(dumper, data):
    if '\n' in data: return dumper.represent_scalar('tag:yaml.org,2002:str', data, style='|')
    return dumper.represent_scalar('tag:yaml.org,2002:str', data)
yaml.add_representer(str, multiline_str)

def write_yaml(data, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w') as f: yaml.dump(data, f, default_flow_style=False, sort_keys=False)

def build_pristine_deployment(dump, base_name):
    clean = {
        "apiVersion": "apps/v1",
        "kind": "Deployment",
        "metadata": {"name": base_name, "labels": {"app": base_name}},
        "spec": {
            "replicas": 1,
            "selector": {"matchLabels": {"app": base_name}},
            "template": {
                "metadata": {"labels": {"app": base_name}},
                "spec": {}
            }
        }
    }
    
    spec = dump.get('spec', {}).get('template', {}).get('spec', {})
    if 'imagePullSecrets' in spec:
        clean['spec']['template']['spec']['imagePullSecrets'] = [{'name': 'halo-gitlab'}]
        
    containers = []
    for c in spec.get('containers', []):
        new_c = {
            "name": base_name,
            "image": c.get("image"),
            "imagePullPolicy": "Always"
        }
        if "command" in c: new_c["command"] = c["command"]
        if "args" in c: new_c["args"] = c["args"]
        if "ports" in c and c["ports"]: new_c["ports"] = [{"containerPort": p["containerPort"]} for p in c.get("ports") if p and "containerPort" in p]
        if "resources" in c:
            new_c["resources"] = c["resources"]
        else:
            new_c["resources"] = {"requests": {"cpu": "100m", "memory": "128Mi"}, "limits": {"cpu": "500m", "memory": "512Mi"}}
            
        if "livenessProbe" in c: new_c["livenessProbe"] = c["livenessProbe"]
        if "readinessProbe" in c: new_c["readinessProbe"] = c["readinessProbe"]
        
        # Keep generic volumeMounts (like emptyDir or standard configs), strip specific ones later if needed
        # For now, keep them in base and let tenants patch them, or strip them from base.
        containers.append(new_c)
        
    clean['spec']['template']['spec']['containers'] = containers
    return clean

def build_pristine_service(dump, base_name):
    clean = {
        "apiVersion": "v1",
        "kind": "Service",
        "metadata": {"name": base_name, "labels": {"app": base_name}},
        "spec": {
            "type": dump.get('spec', {}).get('type', 'ClusterIP'),
            "selector": {"app": base_name},
            "ports": []
        }
    }
    for p in dump.get('spec', {}).get('ports', []):
        new_p = {"port": p["port"], "targetPort": p.get("targetPort", p["port"]), "protocol": p.get("protocol", "TCP")}
        if "name" in p: new_p["name"] = p["name"]
        if "nodePort" in p: new_p["nodePort"] = p["nodePort"]
        clean['spec']['ports'].append(new_p)
    return clean


def main():
    os.system(f"rm -rf {DEPLOYMENT_DIR}/*")
    
    # Generate generic bases
    print("Generating bases...")
    bases = {
        "base/backend": "app_halo-babel_Deployment_backend.yaml",
        "base/config-analyzer": "app_halo-babel_Deployment_config-analyzer.yaml",
        "base/dashboard": "app_halo-babel_Deployment_dashboard.yaml",
        "base/oauth2-proxy": "app_halo-babel_Deployment_oauth2-proxy.yaml",
        "base/redis": "app_halo-babel_Deployment_redis.yaml",
        "collectors/fluent-bit": "app_halo-corp_Deployment_fluent-bit-syslog-ingest.yaml",
        "collectors/goflow2": "app_halo-corp_Deployment_netflow-ingestion.yaml",
        "morpheus_runtime/syslog-pipeline": "gpu_halo_Deployment_gtt-corp-syslog-pipeline-v2.yaml",
        "morpheus_runtime/firewall-pipeline": "gpu_halo_Deployment_gtt-corp-firewall-pipeline-v2.yaml",
        "morpheus_runtime/netflow-pipeline": "gpu_halo_Deployment_gtt-corp-netflow-pipeline-v2.yaml",
        "morpheus_runtime/triton": "gpu_halo_Deployment_triton-server.yaml"
    }
    
    for base_path, dump_name in bases.items():
        base_name = os.path.basename(base_path)
        dump_path = os.path.join(DUMP_DIR, dump_name)
        if not os.path.exists(dump_path):
            print(f"Missing {dump_path}, skipping base {base_name}")
            continue
            
        with open(dump_path, 'r') as f: dump_yaml = yaml.safe_load(f)
        
        dep = build_pristine_deployment(dump_yaml, base_name)
        write_yaml(dep, f"{DEPLOYMENT_DIR}/{base_path}/deployment.yaml")
        
        resources = ["deployment.yaml"]
        
        svc_dump_name = dump_name.replace("Deployment_", "Service_").replace("-v2", "")
        # Try to find corresponding service
        if "syslog-pipeline" in svc_dump_name: svc_dump_name = svc_dump_name.replace("gtt-corp-", "") # fuzzy match
        
        # Write base service if found
        svc_paths = glob.glob(f"{DUMP_DIR}/*Service_*{base_name}*.yaml")
        if svc_paths:
            with open(svc_paths[0], 'r') as f: svc_dump = yaml.safe_load(f)
            svc = build_pristine_service(svc_dump, base_name)
            write_yaml(svc, f"{DEPLOYMENT_DIR}/{base_path}/service.yaml")
            resources.append("service.yaml")
            
        write_yaml({"resources": resources}, f"{DEPLOYMENT_DIR}/{base_path}/kustomization.yaml")
        
    print("Generating tenants...")
    # Map raw dump deployments to their generic base paths
    def map_to_base(name):
        if "backend" in name and "fw" not in name and "firewall" not in name: return "base/backend"
        if "config-analyzer" in name: return "base/config-analyzer"
        if "dashboard" in name and "frontend" not in name: return "base/dashboard"
        if "oauth2-proxy" in name: return "base/oauth2-proxy"
        if "redis" in name: return "base/redis"
        
        if "firewall-backend" in name: return "base/backend"
        if "firewall-frontend" in name: return "base/dashboard"
        
        if "fluent-bit" in name: return "collectors/fluent-bit"
        if "syslog-ingestion" in name: return "collectors/goflow2"
        if "netflow-ingestion" in name: return "collectors/goflow2"
        if "firewall-ingestion" in name: return "collectors/goflow2"
        
        if "syslog-pipeline" in name: return "morpheus_runtime/syslog-pipeline"
        if "firewall-pipeline" in name: return "morpheus_runtime/firewall-pipeline"
        if "netflow-pipeline" in name: return "morpheus_runtime/netflow-pipeline"
        if "triton" in name: return "morpheus_runtime/triton"
        return None

    # Loop all deployments
    for f in glob.glob(f"{DUMP_DIR}/*_Deployment_*.yaml"):
        with open(f, 'r') as file: dump = yaml.safe_load(file)
        
        raw_name = dump['metadata']['name']
        base_path = map_to_base(raw_name)
        if not base_path: continue
        
        cluster = "app" if f.split('/')[-1].startswith("app_") else "gpu"
        tenant_match = re.search(r"app_(halo-[a-z-]+)_", f.split('/')[-1])
        if not tenant_match:
             # handle gpu tenants (gpu_halo_Deployment_gtt-corp-syslog.yaml -> halo-corp)
             if "gtt-corp" in raw_name: tenant = "halo-corp"
             elif "gtt-babel" in raw_name: tenant = "halo-babel"
             elif "gtt-scott" in raw_name: tenant = "halo-scott-dev"
             else: tenant = "halo-unknown"
        else:
             tenant = tenant_match.group(1)
             
        # Extract environment variables to create a patch
        env_vars = dump.get('spec', {}).get('template', {}).get('spec', {}).get('containers', [{}])[0].get('env') or []
        envFrom = dump.get('spec', {}).get('template', {}).get('spec', {}).get('containers', [{}])[0].get('envFrom') or []
        
        # Clean up secrets from env vars
        clean_env = []
        for e in env_vars:
            if "PASSWORD" in e.get("name", "") or "SECRET" in e.get("name", "") or "TOKEN" in e.get("name", ""):
                # Add to envFrom placeholder instead
                if not any(ef.get("secretRef", {}).get("name") == "halo-credentials" for ef in envFrom):
                    envFrom.append({"secretRef": {"name": "halo-credentials"}})
            elif e.get("value_from"):
                pass
            else:
                clean_env.append({"name": e["name"], "value": e["value"]})
                
        base_name = os.path.basename(base_path)
        tenant_dir = f"{DEPLOYMENT_DIR}/tenants/slo/{tenant}/{cluster}/{raw_name}"
        
        patch = {
            "apiVersion": "apps/v1",
            "kind": "Deployment",
            "metadata": {"name": base_name},
            "spec": {
                "template": {
                    "spec": {
                        "containers": [{
                            "name": base_name,
                        }]
                    }
                }
            }
        }
        if clean_env: patch["spec"]["template"]["spec"]["containers"][0]["env"] = clean_env
        if envFrom: patch["spec"]["template"]["spec"]["containers"][0]["envFrom"] = envFrom
        
        write_yaml(patch, f"{tenant_dir}/patch-env.yaml")
        
        kustomize = {
            "bases": [f"../../../../../../{base_path}"],
            "patchesStrategicMerge": ["patch-env.yaml"]
        }
        
        if raw_name != base_name:
            # Determine prefix
            if raw_name.endswith(base_name):
                kustomize["namePrefix"] = raw_name[:-len(base_name)]
            else:
                # Just use raw name as the overriding mechanism
                # Kustomize NamePrefix is easiest
                kustomize["namePrefix"] = raw_name.replace(base_name, "")
                
        write_yaml(kustomize, f"{tenant_dir}/kustomization.yaml")

    print("Complete!")

if __name__ == "__main__":
    main()
