#!/usr/bin/env python3
import os
import yaml

DUMP_DIR = "/ai/utilities/halo_admin_utility/cache/halo/deployment/dump"
DEPLOYMENT_DIR = "/ai/utilities/halo_admin_utility/cache/halo/deployment"

BASE_COMPONENTS = ["backend", "config-analyzer", "dashboard", "oauth2-proxy", "redis"]

def sanitize_manifest(data, generic_name=None):
    if not data: return data
    if 'metadata' in data:
        data['metadata'].pop('namespace', None)
        if generic_name:
            data['metadata']['name'] = generic_name
        data['metadata'].pop('annotations', None)
        # Keep labels
    return data

def build_base():
    base_dir = os.path.join(DEPLOYMENT_DIR, "base")
    for comp in BASE_COMPONENTS:
        comp_dir = os.path.join(base_dir, comp)
        os.makedirs(comp_dir, exist_ok=True)
        
        resources = []
        
        # Deployment
        dep_file = f"{DUMP_DIR}/app_halo-babel_Deployment_{comp}.yaml"
        if os.path.exists(dep_file):
            with open(dep_file, 'r') as f:
                data = yaml.safe_load(f)
            data = sanitize_manifest(data)
            with open(f"{comp_dir}/deployment.yaml", 'w') as f:
                yaml.dump(data, f)
            resources.append("deployment.yaml")
            
        # Service
        svc_name = comp
        if comp == "oauth2-proxy":
            svc_name = "oauth2-proxy-svc"
        
        svc_file = f"{DUMP_DIR}/app_halo-babel_Service_{svc_name}.yaml"
        if os.path.exists(svc_file):
            with open(svc_file, 'r') as f:
                data = yaml.safe_load(f)
            data = sanitize_manifest(data)
            with open(f"{comp_dir}/service.yaml", 'w') as f:
                yaml.dump(data, f)
            resources.append("service.yaml")
            
        # Kustomization
        if resources:
            kustomization = {
                "resources": resources
            }
            with open(f"{comp_dir}/kustomization.yaml", 'w') as f:
                yaml.dump(kustomization, f)
            print(f"Created base for {comp}")

def build_tenant(tenant_name, include_bases=True):
    tenant_dir = os.path.join(DEPLOYMENT_DIR, "tenants", "slo", tenant_name)
    os.makedirs(tenant_dir, exist_ok=True)
    
    kustomization = {
        "namespace": tenant_name,
        "resources": [],
        "patches": []
    }
    
    if include_bases:
        kustomization["bases"] = [f"../../../../base/{comp}" for comp in BASE_COMPONENTS]
        
    # Add ingress and configmaps from the dump
    for file in os.listdir(DUMP_DIR):
        if file.startswith(f"app_{tenant_name}_"):
            parts = file.split("_")
            kind = parts[2]
            name = parts[3].replace(".yaml", "")
            
            # Skip bases since we include them via kustomize
            if include_bases and kind in ["Deployment", "Service"]:
                if name in BASE_COMPONENTS or name == "oauth2-proxy-svc":
                    continue
                    
            with open(os.path.join(DUMP_DIR, file), 'r') as f:
                data = yaml.safe_load(f)
                
            data = sanitize_manifest(data)
            out_name = f"{kind.lower()}_{name}.yaml"
            with open(os.path.join(tenant_dir, out_name), 'w') as f:
                yaml.dump(data, f)
                
            kustomization["resources"].append(out_name)
            
    with open(os.path.join(tenant_dir, "kustomization.yaml"), 'w') as f:
        yaml.dump(kustomization, f)
    print(f"Created tenant {tenant_name}")

if __name__ == "__main__":
    print("Building base components...")
    build_base()
    
    print("Building halo-babel...")
    build_tenant("halo-babel", include_bases=True)
    
    print("Building halo-corp...")
    build_tenant("halo-corp", include_bases=True)
    
    print("Building halo-scott-dev...")
    build_tenant("halo-scott-dev", include_bases=True)
