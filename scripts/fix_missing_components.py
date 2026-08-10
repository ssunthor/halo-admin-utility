#!/usr/bin/env python3
import os
import yaml
import glob

BASE_DIR = "/ai/utilities/halo_admin_utility/cache/halo/deployment"

def add_volume_to_deployment(filepath, volume_name, config_map_name, mount_path, sub_path=None):
    with open(filepath, "r") as f:
        data = yaml.safe_load(f)

    containers = data["spec"]["template"]["spec"]["containers"]
    for container in containers:
        if "volumeMounts" not in container:
            container["volumeMounts"] = []
        # Check if already exists
        exists = False
        for vm in container["volumeMounts"]:
            if vm["name"] == volume_name:
                exists = True
        if not exists:
            vm = {"name": volume_name, "mountPath": mount_path}
            if sub_path:
                vm["subPath"] = sub_path
            container["volumeMounts"].append(vm)
            
    spec = data["spec"]["template"]["spec"]
    if "volumes" not in spec:
        spec["volumes"] = []
    
    v_exists = False
    for v in spec["volumes"]:
        if v["name"] == volume_name:
            v_exists = True
    if not v_exists:
        spec["volumes"].append({
            "name": volume_name,
            "configMap": {"name": config_map_name}
        })
        
    with open(filepath, "w") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)

def update_kustomization_cm(kust_file, cm_name, files_list):
    with open(kust_file, "r") as f:
        k_data = yaml.safe_load(f) or {}

    cm_gen = {
        "name": cm_name,
        "files": files_list
    }
    
    if "configMapGenerator" not in k_data:
        k_data["configMapGenerator"] = [cm_gen]
    else:
        updated = False
        for cm in k_data["configMapGenerator"]:
            if cm.get("name") == cm_name:
                cm["files"] = files_list
                if "behavior" in cm:
                    # remove behavior if it's base
                    pass
                updated = True
        if not updated:
            k_data["configMapGenerator"].append(cm_gen)
            
    with open(kust_file, "w") as f:
        yaml.dump(k_data, f, default_flow_style=False, sort_keys=False)


def main():
    # 1. Fix Redis
    redis_dep = os.path.join(BASE_DIR, "base", "redis", "deployment.yaml")
    add_volume_to_deployment(redis_dep, "redis-acl", "redis-users.acl", "/etc/redis/redis-users.acl", "redis-users.acl")
    
    redis_kust = os.path.join(BASE_DIR, "base", "redis", "kustomization.yaml")
    update_kustomization_cm(redis_kust, "redis-users.acl", ["redis-users.acl"])
    
    with open(os.path.join(BASE_DIR, "base", "redis", "redis-users.acl"), "w") as f:
        f.write("user default on nopass ~* +@all\n")

    # 2. Fix oauth2-proxy
    oauth_dep = os.path.join(BASE_DIR, "base", "oauth2-proxy", "deployment.yaml")
    add_volume_to_deployment(oauth_dep, "certs", "oauth2-proxy-certs", "/mnt/certs")
    
    oauth_kust = os.path.join(BASE_DIR, "base", "oauth2-proxy", "kustomization.yaml")
    update_kustomization_cm(oauth_kust, "oauth2-proxy-certs", ["cabundle.crt"])
    
    with open(os.path.join(BASE_DIR, "base", "oauth2-proxy", "cabundle.crt"), "w") as f:
        f.write("-----BEGIN CERTIFICATE-----\nDummy\n-----END CERTIFICATE-----\n")

    # Update service name and targetPort
    oauth_svc = os.path.join(BASE_DIR, "base", "oauth2-proxy", "service.yaml")
    with open(oauth_svc, "r") as f:
        svc_data = yaml.safe_load(f)
    svc_data["metadata"]["name"] = "oauth2-proxy-svc"
    for port in svc_data["spec"]["ports"]:
        if port.get("port") == 80:
            port["targetPort"] = 4180
    with open(oauth_svc, "w") as f:
        yaml.dump(svc_data, f, default_flow_style=False, sort_keys=False)
        
    # Also add ingress to oauth2-proxy
    ingress_path = os.path.join(BASE_DIR, "base", "oauth2-proxy", "ingress.yaml")
    ingress_data = {
        "apiVersion": "networking.k8s.io/v1",
        "kind": "Ingress",
        "metadata": {
            "name": "oauth2-proxy-ingress",
            "labels": {"app": "oauth2-proxy"}
        },
        "spec": {
            "rules": [{
                "host": "dummy.defensehalo.ai",
                "http": {
                    "paths": [{
                        "path": "/",
                        "pathType": "Prefix",
                        "backend": {
                            "service": {
                                "name": "oauth2-proxy-svc",
                                "port": {"number": 80}
                            }
                        }
                    }]
                }
            }]
        }
    }
    with open(ingress_path, "w") as f:
        yaml.dump(ingress_data, f, default_flow_style=False, sort_keys=False)
        
    # Update kustomization to include ingress
    with open(oauth_kust, "r") as f:
        k_data = yaml.safe_load(f)
    if "resources" in k_data and "ingress.yaml" not in k_data["resources"]:
        k_data["resources"].append("ingress.yaml")
    with open(oauth_kust, "w") as f:
        yaml.dump(k_data, f, default_flow_style=False, sort_keys=False)

    # 3. Add overrides to tenants
    tenants_dir = os.path.join(BASE_DIR, "tenants")
    for app_dir in glob.glob(f"{tenants_dir}/**/app/*", recursive=True):
        if not os.path.isdir(app_dir): continue
        
        folder_name = os.path.basename(app_dir)
        kust_file = os.path.join(app_dir, "kustomization.yaml")
        if not os.path.exists(kust_file): continue
        
        with open(kust_file, "r") as f:
            k_data = yaml.safe_load(f) or {}
            
        changed = False

        if folder_name == "redis":
            with open(os.path.join(app_dir, "redis-users.acl"), "w") as f:
                f.write("user default on nopass ~* +@all\n")
            
            cm_override = {
                "name": "redis-users.acl",
                "behavior": "replace",
                "files": ["redis-users.acl"]
            }
            if "configMapGenerator" not in k_data:
                k_data["configMapGenerator"] = []
            
            updated = False
            for cm in k_data["configMapGenerator"]:
                if cm.get("name") == "redis-users.acl":
                    updated = True
            if not updated:
                k_data["configMapGenerator"].append(cm_override)
                changed = True

        elif folder_name == "oauth2-proxy":
            with open(os.path.join(app_dir, "cabundle.crt"), "w") as f:
                f.write("-----BEGIN CERTIFICATE-----\nTenant Dummy\n-----END CERTIFICATE-----\n")
            
            cm_override = {
                "name": "oauth2-proxy-certs",
                "behavior": "replace",
                "files": ["cabundle.crt"]
            }
            if "configMapGenerator" not in k_data:
                k_data["configMapGenerator"] = []
            
            updated = False
            for cm in k_data["configMapGenerator"]:
                if cm.get("name") == "oauth2-proxy-certs":
                    updated = True
            if not updated:
                k_data["configMapGenerator"].append(cm_override)
                changed = True
                
            # Create a patch for the ingress host
            # we will extract tenant name from the directory path (e.g. halo-babel)
            tenant_name = app_dir.split("/")[-3] # tenants/slo/halo-babel/app/oauth2-proxy
            tenant_host = tenant_name.replace("halo-", "") + ".defensehalo.ai"
            
            ingress_patch = {
                "apiVersion": "networking.k8s.io/v1",
                "kind": "Ingress",
                "metadata": {
                    "name": "oauth2-proxy-ingress",
                },
                "spec": {
                    "rules": [{
                        "host": tenant_host,
                    }]
                }
            }
            with open(os.path.join(app_dir, "patch-ingress.yaml"), "w") as f:
                yaml.dump(ingress_patch, f, default_flow_style=False, sort_keys=False)
                
            if "patchesStrategicMerge" not in k_data:
                k_data["patchesStrategicMerge"] = []
            if "patch-ingress.yaml" not in k_data["patchesStrategicMerge"]:
                k_data["patchesStrategicMerge"].append("patch-ingress.yaml")
                changed = True

        if changed:
            with open(kust_file, "w") as f:
                yaml.dump(k_data, f, default_flow_style=False, sort_keys=False)

if __name__ == "__main__":
    main()
