#!/usr/bin/env python3
import os
import yaml
import glob

def main():
    for f in glob.glob("/ai/utilities/halo_admin_utility/cache/halo/deployment/tenants/**/patch-env.yaml", recursive=True):
        with open(f, 'r') as file:
            try:
                dump = yaml.safe_load(file)
                container = dump.get('spec', {}).get('template', {}).get('spec', {}).get('containers', [{}])[0]
                has_patch = False
                for key in ['env', 'envFrom', 'args', 'volumeMounts', 'command']:
                    if key in container and container[key]:
                        has_patch = True
                        break
                
                if not has_patch:
                    print(f"Deleting empty patch {f}")
                    os.remove(f)
                    
                    # Update kustomization.yaml
                    kust_file = os.path.join(os.path.dirname(f), "kustomization.yaml")
                    if os.path.exists(kust_file):
                        with open(kust_file, 'r') as kf:
                            k_data = yaml.safe_load(kf)
                        if 'patchesStrategicMerge' in k_data:
                            k_data['patchesStrategicMerge'].remove('patch-env.yaml')
                            if not k_data['patchesStrategicMerge']:
                                del k_data['patchesStrategicMerge']
                        with open(kust_file, 'w') as kf:
                            yaml.dump(k_data, kf, default_flow_style=False, sort_keys=False)
            except Exception as e:
                print(f"Error parsing {f}: {e}")

if __name__ == "__main__":
    main()
