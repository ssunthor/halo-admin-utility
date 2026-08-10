import os
import re
import yaml

# Safe dumper to make YAML look nicer
class SafeDumper(yaml.SafeDumper):
    def increase_indent(self, flow=False, indentless=False):
        return super(SafeDumper, self).increase_indent(flow, False)

def get_yaml_content(path):
    with open(path, 'r') as f:
        return yaml.safe_load(f)

def write_yaml_content(path, data):
    with open(path, 'w') as f:
        yaml.dump(data, f, Dumper=SafeDumper, default_flow_style=False, sort_keys=False)

DEPLOYMENT_DIR = "/ai/utilities/halo_admin_utility/cache/halo/deployment"
BASE_DIR = os.path.join(DEPLOYMENT_DIR, "base")
TENANTS_DIR = os.path.join(DEPLOYMENT_DIR, "tenants/slo")

GLOBAL_ENV_VARS = [
    {'name': 'NETBOX_URL', 'value': 'https://netbox.gt-t.net'},
    {'name': 'REDIS_HOST', 'value': 'redis'},
    {'name': 'VLLM_ENDPOINT', 'value': 'https://aif-llm-vllm-gemma3-27b.prg.gt-t.net/v1/chat/completions'},
    {'name': 'LLM_AUTH_URL', 'value': 'https://keycloak-aif.gt-t.net/realms/aif-llm/protocol/openid-connect/token'}
]

def step1_base_refactor():
    print("--- Step 1: Base Refactor ---")
    for root, dirs, files in os.walk(BASE_DIR):
        if 'deployment.yaml' in files:
            path = os.path.join(root, 'deployment.yaml')
            data = get_yaml_content(path)
            if not data or 'spec' not in data:
                continue
            
            containers = data.get('spec', {}).get('template', {}).get('spec', {}).get('containers', [])
            for c in containers:
                if 'image' in c:
                    # Strip :main or :latest
                    c['image'] = re.sub(r':(main|latest)$', '', c['image'])
                
                # Inject global vars for backend and config-analyzer
                if 'backend' in root or 'config-analyzer' in root:
                    if 'env' not in c:
                        c['env'] = []
                    # Avoid duplicates
                    existing_vars = {e['name'] for e in c['env']}
                    for gv in GLOBAL_ENV_VARS:
                        if gv['name'] not in existing_vars:
                            c['env'].append(gv)
            
            write_yaml_content(path, data)
            print(f"Refactored base: {path}")

def step2_tenant_app_refactor():
    print("--- Step 2, 3, 5: Tenant App Overhaul ---")
    if not os.path.exists(TENANTS_DIR):
        return
    
    for tenant_id in os.listdir(TENANTS_DIR):
        tenant_app_dir = os.path.join(TENANTS_DIR, tenant_id, 'app')
        if not os.path.exists(tenant_app_dir):
            continue
            
        kustom_path = os.path.join(tenant_app_dir, 'kustomization.yaml')
        k_data = {}
        if os.path.exists(kustom_path):
            k_data = get_yaml_content(kustom_path) or {}
            
        # Step 2: Namespace
        k_data['namespace'] = tenant_id
        
        # Step 2: Annotations
        if 'commonAnnotations' not in k_data:
            k_data['commonAnnotations'] = {}
        k_data['commonAnnotations']['halo/target-cluster'] = 'slo-hal-clu01'
        k_data['commonAnnotations']['halo/source-file'] = f"deployment/tenants/slo/{tenant_id}/app/kustomization.yaml"
        
        # We need to build the bases list from the local subdirectories
        local_bases = []
        for comp in os.listdir(tenant_app_dir):
            if os.path.isdir(os.path.join(tenant_app_dir, comp)):
                if os.path.exists(os.path.join(tenant_app_dir, comp, 'kustomization.yaml')):
                    local_bases.append(comp)
        
        if local_bases:
            k_data['bases'] = local_bases
            
        # Step 2: Images block
        images = []
        if 'backend' in local_bases:
            images.append({'name': 'gitlab.gt-t.net:4567/ai/halo/backend', 'newTag': 'main'})
        if 'dashboard' in local_bases:
            images.append({'name': 'gitlab.gt-t.net:4567/ai/halo/dashboard/frontend', 'newTag': 'main'})
        if 'config-analyzer' in local_bases:
            images.append({'name': 'gitlab.gt-t.net:4567/ai/halo/config-analyzer-backend', 'newTag': 'main'})
            
        if images:
            k_data['images'] = images
            
        write_yaml_content(kustom_path, k_data)
        print(f"Updated app kustomization for {tenant_id}")
            
        # Iterate over components in the app dir to do Step 3 and 5
        for comp in os.listdir(tenant_app_dir):
            comp_dir = os.path.join(tenant_app_dir, comp)
            if not os.path.isdir(comp_dir):
                continue
                
            patch_env = os.path.join(comp_dir, 'patch-env.yaml')
            patch_sec = os.path.join(comp_dir, 'patch-secrets-placeholder.yaml')
            comp_kustom = os.path.join(comp_dir, 'kustomization.yaml')
            
            if os.path.exists(patch_env):
                env_data = get_yaml_content(patch_env)
                if not env_data:
                    continue
                
                containers = env_data.get('spec', {}).get('template', {}).get('spec', {}).get('containers', [])
                secrets = []
                for c in containers:
                    envs = c.get('env', [])
                    new_envs = []
                    
                    global_var_names = {v['name'] for v in GLOBAL_ENV_VARS}
                    
                    for e in envs:
                        name = e.get('name', '')
                        # Step 3: Remove global bloat
                        if name in global_var_names:
                            continue
                        # Step 5: Segregate secrets
                        elif 'SECRET' in name or 'PASSWORD' in name or 'TOKEN' in name:
                            secrets.append(e)
                        else:
                            new_envs.append(e)
                            
                    c['env'] = new_envs
                
                write_yaml_content(patch_env, env_data)
                
                if secrets:
                    # Create patch-secrets-placeholder.yaml
                    sec_data = {
                        'apiVersion': env_data.get('apiVersion', 'apps/v1'),
                        'kind': env_data.get('kind', 'Deployment'),
                        'metadata': {'name': env_data.get('metadata', {}).get('name', comp)},
                        'spec': {
                            'template': {
                                'spec': {
                                    'containers': [{
                                        'name': containers[0].get('name', comp) if containers else comp,
                                        'env': secrets
                                    }]
                                }
                            }
                        }
                    }
                    write_yaml_content(patch_sec, sec_data)
                    
                    # Prepend TODO comment
                    with open(patch_sec, 'r') as f:
                        content = f.read()
                    with open(patch_sec, 'w') as f:
                        f.write("# ⚠️ TODO: Migrate to Vault / ExternalSecrets ⚠️\n" + content)
                        
                    print(f"Created secret placeholder for {tenant_id}/{comp}")
                    
                    # Ensure patch-secrets-placeholder.yaml is in comp kustomization
                    if os.path.exists(comp_kustom):
                        c_k = get_yaml_content(comp_kustom)
                        patches = c_k.get('patchesStrategicMerge', [])
                        if 'patch-secrets-placeholder.yaml' not in patches:
                            patches.append('patch-secrets-placeholder.yaml')
                            c_k['patchesStrategicMerge'] = patches
                            write_yaml_content(comp_kustom, c_k)

def step4_gpu_refactor():
    print("--- Step 4: GPU Workloads ---")
    if not os.path.exists(TENANTS_DIR):
        return
        
    for tenant_id in os.listdir(TENANTS_DIR):
        gpu_dir = os.path.join(TENANTS_DIR, tenant_id, 'gpu')
        if not os.path.exists(gpu_dir):
            continue
            
        for pipe in os.listdir(gpu_dir):
            pipe_dir = os.path.join(gpu_dir, pipe)
            if not os.path.isdir(pipe_dir):
                continue
                
            kustom_path = os.path.join(pipe_dir, 'kustomization.yaml')
            if os.path.exists(kustom_path):
                k_data = get_yaml_content(kustom_path)
                
                if 'commonAnnotations' not in k_data:
                    k_data['commonAnnotations'] = {}
                k_data['commonAnnotations']['halo/target-cluster'] = 'slo-aif-nvclu01'
                k_data['commonAnnotations']['halo/source-file'] = f"deployment/tenants/slo/{tenant_id}/gpu/{pipe}/kustomization.yaml"
                
                write_yaml_content(kustom_path, k_data)
                print(f"Updated gpu kustomization for {tenant_id}/{pipe}")

def step5_restore_secrets():
    print("--- Step 5: Restoring Secrets from Raw Dumps ---")
    if not os.path.exists(TENANTS_DIR):
        return
        
    for tenant_id in os.listdir(TENANTS_DIR):
        tenant_app_dir = os.path.join(TENANTS_DIR, tenant_id, 'app')
        if not os.path.exists(tenant_app_dir):
            continue
            
        for comp in os.listdir(tenant_app_dir):
            comp_dir = os.path.join(tenant_app_dir, comp)
            if not os.path.isdir(comp_dir):
                continue
                
            raw_dump_path = os.path.join("/ai/utilities/halo_admin_utility/output/dump", tenant_id, "app", "Deployment", f"{comp}.yaml")
            if not os.path.exists(raw_dump_path):
                continue
                
            raw_data = get_yaml_content(raw_dump_path)
            if not raw_data:
                continue
                
            containers = raw_data.get('spec', {}).get('template', {}).get('spec', {}).get('containers', [])
            secrets = []
            for c in containers:
                envs = c.get('env') or []
                for e in envs:
                    name = e.get('name', '')
                    if 'SECRET' in name or 'PASSWORD' in name or 'TOKEN' in name:
                        secrets.append({'name': name, 'value': e.get('value', '')})
                        
            if secrets:
                patch_sec = os.path.join(comp_dir, 'patch-secrets-placeholder.yaml')
                comp_kustom = os.path.join(comp_dir, 'kustomization.yaml')
                
                sec_data = {
                    'apiVersion': 'apps/v1',
                    'kind': 'Deployment',
                    'metadata': {'name': comp},
                    'spec': {
                        'template': {
                            'spec': {
                                'containers': [{
                                    'name': comp,
                                    'env': secrets
                                }]
                            }
                        }
                    }
                }
                write_yaml_content(patch_sec, sec_data)
                
                # Prepend TODO comment
                with open(patch_sec, 'r') as f:
                    content = f.read()
                with open(patch_sec, 'w') as f:
                    f.write("# ⚠️ TODO: Migrate to Vault / ExternalSecrets ⚠️\n" + content)
                    
                print(f"Restored secret placeholder for {tenant_id}/{comp}")
                
                if os.path.exists(comp_kustom):
                    c_k = get_yaml_content(comp_kustom) or {}
                    patches = c_k.get('patchesStrategicMerge', [])
                    if 'patch-secrets-placeholder.yaml' not in patches:
                        patches.append('patch-secrets-placeholder.yaml')
                        c_k['patchesStrategicMerge'] = patches
                        write_yaml_content(comp_kustom, c_k)

if __name__ == "__main__":
    step1_base_refactor()
    step2_tenant_app_refactor()
    step4_gpu_refactor()
    step5_restore_secrets()
    print("Refactoring complete.")
