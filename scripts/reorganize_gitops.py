import os
import shutil
import glob


BASE_DIR = "/ai/utilities/halo_admin_utility/cache/halo/deployment"

def rename_directory(src_rel, dst_rel):
    src = os.path.join(BASE_DIR, src_rel)
    dst = os.path.join(BASE_DIR, dst_rel)
    if os.path.exists(src):
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        print(f"Moving {src_rel} to {dst_rel}")
        shutil.move(src, dst)
    else:
        print(f"Source {src_rel} does not exist, skipping.")

def remove_directory(rel_path):
    path = os.path.join(BASE_DIR, rel_path)
    if os.path.exists(path):
        print(f"Removing {rel_path}")
        shutil.rmtree(path)

def restructure_directories():
    print("--- Restructuring Directories ---")
    
    # 1. Halo components
    rename_directory("base/backend", "base/halo/backend")
    rename_directory("base/dashboard", "base/halo/dashboard/frontend")
    rename_directory("base/config-analyzer", "base/halo/dashboard/config-analyzer-backend")
    
    # 2. Ingest
    rename_directory("collectors/goflow2", "base/halo/ingest/netflow-goflow2")
    rename_directory("collectors/fluent-bit", "base/halo/ingest/syslog-fluent-bit")
    
    # 3. Pipelines
    rename_directory("morpheus_runtime/netflow-pipeline", "base/halo/pipelines/netflow-dfp")
    rename_directory("morpheus_runtime/syslog-pipeline", "base/halo/pipelines/syslog-dfp")
    rename_directory("morpheus_runtime/firewall-pipeline", "base/halo/pipelines/forti-dfp")
    
    # 4. Vendor
    rename_directory("base/oauth2-proxy", "base/vendor/oauth2-proxy")
    rename_directory("base/redis", "base/vendor/redis")
    rename_directory("morpheus_runtime/triton", "base/vendor/triton")
    
    # 5. Delete Garbage
    remove_directory("base/firewall-backend")
    remove_directory("base/firewall-frontend")
    
    # 6. Cleanup empty dirs
    for d in ["collectors", "morpheus_runtime"]:
        path = os.path.join(BASE_DIR, d)
        if os.path.exists(path) and not os.listdir(path):
            os.rmdir(path)
            print(f"Removed empty directory {d}")

def update_kustomization_references():
    print("--- Updating Kustomize References ---")
    
    # A mapping of old relative base targets to new relative base targets
    # (Since Kustomize bases are relative, we search for the standard pattern)
    
    replacements = {
        "../../../../../../base/backend": "../../../../../../base/halo/backend",
        "../../../../../../base/dashboard": "../../../../../../base/halo/dashboard/frontend",
        "../../../../../../base/config-analyzer": "../../../../../../base/halo/dashboard/config-analyzer-backend",
        
        "../../../../../../collectors/goflow2": "../../../../../../base/halo/ingest/netflow-goflow2",
        "../../../../../../collectors/fluent-bit": "../../../../../../base/halo/ingest/syslog-fluent-bit",
        
        "../../../../../../morpheus_runtime/netflow-pipeline": "../../../../../../base/halo/pipelines/netflow-dfp",
        "../../../../../../morpheus_runtime/syslog-pipeline": "../../../../../../base/halo/pipelines/syslog-dfp",
        "../../../../../../morpheus_runtime/firewall-pipeline": "../../../../../../base/halo/pipelines/forti-dfp",
        "../../../../../../morpheus_runtime/triton": "../../../../../../base/vendor/triton",
        
        "../../../../../../base/oauth2-proxy": "../../../../../../base/vendor/oauth2-proxy",
        "../../../../../../base/redis": "../../../../../../base/vendor/redis"
    }
    
    tenants_dir = os.path.join(BASE_DIR, "tenants")
    count = 0
    for root, _, files in os.walk(tenants_dir):
        if "kustomization.yaml" in files:
            kustom_path = os.path.join(root, "kustomization.yaml")
            
            with open(kustom_path, 'r') as f:
                content = f.read()
                
            modified = False
            for old_str, new_str in replacements.items():
                if old_str in content:
                    content = content.replace(old_str, new_str)
                    modified = True
                    
            if modified:
                with open(kustom_path, 'w') as f:
                    f.write(content)
                count += 1
                
    print(f"Updated {count} kustomization.yaml files.")

if __name__ == "__main__":
    restructure_directories()
    update_kustomization_references()
    print("Structural Reorganization Complete!")
