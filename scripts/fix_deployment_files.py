#!/usr/bin/env python3
import os
import yaml
import shutil
import glob

BASE_DIR = "/ai/utilities/halo_admin_utility/cache/halo/deployment"

def main():
    # 1. Fix collectors/fluent-bit
    fluent_bit_base = os.path.join(BASE_DIR, "collectors", "fluent-bit")
    if os.path.exists(fluent_bit_base):
        with open(os.path.join(fluent_bit_base, "fluent-bit.conf"), "w") as f:
            f.write("[SERVICE]\n    Flush 1\n")
        with open(os.path.join(fluent_bit_base, "parsers.conf"), "w") as f:
            f.write("[PARSER]\n    Name dummy\n")
            
        kust_file = os.path.join(fluent_bit_base, "kustomization.yaml")
        if os.path.exists(kust_file):
            with open(kust_file, "r") as f:
                k_data = yaml.safe_load(f) or {}
            
            # Ensure configMapGenerator exists
            cm_gen = {
                "name": "fluent-bit-config",
                "files": ["fluent-bit.conf", "parsers.conf"]
            }
            if "configMapGenerator" not in k_data:
                k_data["configMapGenerator"] = [cm_gen]
            else:
                # Update if exists but missing files
                updated = False
                for cm in k_data["configMapGenerator"]:
                    if cm.get("name") == "fluent-bit-config":
                        cm["files"] = ["fluent-bit.conf", "parsers.conf"]
                        updated = True
                if not updated:
                    k_data["configMapGenerator"].append(cm_gen)
            
            with open(kust_file, "w") as f:
                yaml.dump(k_data, f, default_flow_style=False, sort_keys=False)

    # 2. Create missing bases (firewall-backend, firewall-frontend)
    for missing_base, template in [("firewall-backend", "backend"), ("firewall-frontend", "dashboard")]:
        target = os.path.join(BASE_DIR, "base", missing_base)
        source = os.path.join(BASE_DIR, "base", template)
        if not os.path.exists(target) and os.path.exists(source):
            shutil.copytree(source, target)
            # rename inside yaml files
            for f in glob.glob(f"{target}/*.yaml"):
                with open(f, "r") as file:
                    content = file.read()
                content = content.replace(template, missing_base)
                with open(f, "w") as file:
                    file.write(content)

    # 3. Fix tenant configurations
    tenants_dir = os.path.join(BASE_DIR, "tenants")
    for kust_file in glob.glob(f"{tenants_dir}/**/kustomization.yaml", recursive=True):
        folder = os.path.dirname(kust_file)
        folder_name = os.path.basename(folder)
        
        with open(kust_file, "r") as f:
            k_data = yaml.safe_load(f) or {}

        changed = False

        # Fix namePrefix
        if "namePrefix" in k_data:
            prefix = k_data["namePrefix"]
            if prefix.startswith("-"):
                k_data["namePrefix"] = prefix[1:] + "-"
                changed = True
            elif not prefix.endswith("-"):
                k_data["namePrefix"] = prefix + "-"
                changed = True

        # Special handling for fluent-bit ingesters
        if "fluent-bit" in folder_name:
            # Add dummy conf files to tenant so they can replace them
            with open(os.path.join(folder, "fluent-bit.conf"), "w") as f:
                f.write(f"[SERVICE]\n    # Tenant override for {folder_name}\n")
            with open(os.path.join(folder, "parsers.conf"), "w") as f:
                f.write(f"[PARSER]\n    # Tenant override for {folder_name}\n")
            
            cm_override = {
                "name": "fluent-bit-config",
                "behavior": "replace",
                "files": ["fluent-bit.conf", "parsers.conf"]
            }
            if "configMapGenerator" not in k_data:
                k_data["configMapGenerator"] = [cm_override]
                changed = True
            else:
                updated = False
                for cm in k_data["configMapGenerator"]:
                    if cm.get("name") == "fluent-bit-config":
                        cm["behavior"] = "replace"
                        cm["files"] = ["fluent-bit.conf", "parsers.conf"]
                        updated = True
                if not updated:
                    k_data["configMapGenerator"].append(cm_override)
                    changed = True

        # Fix wrong base references
        if "bases" in k_data:
            new_bases = []
            for b in k_data["bases"]:
                # If pointing to firewall-backend but we moved it to base/firewall-backend
                if "firewall-backend" in folder_name and "firewall-backend" not in b:
                    new_bases.append("../../../../../../base/firewall-backend")
                    changed = True
                elif "firewall-frontend" in folder_name and "firewall-frontend" not in b:
                    new_bases.append("../../../../../../base/firewall-frontend")
                    changed = True
                else:
                    new_bases.append(b)
            k_data["bases"] = new_bases

        if changed:
            with open(kust_file, "w") as f:
                yaml.dump(k_data, f, default_flow_style=False, sort_keys=False)

    # 4. Remove redundant firewall-ingestion (if fluent-bit-firewall-ingest exists)
    for fw_ingest in glob.glob(f"{tenants_dir}/**/firewall-ingestion", recursive=True):
        if os.path.exists(fw_ingest):
            shutil.rmtree(fw_ingest)

if __name__ == "__main__":
    main()
