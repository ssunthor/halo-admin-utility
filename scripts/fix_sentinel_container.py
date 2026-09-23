#!/usr/bin/env python3
import os
import sys
import yaml
import logging

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
HAU_ROOT = os.path.dirname(SCRIPT_DIR)
if HAU_ROOT not in sys.path:
    sys.path.insert(0, HAU_ROOT)

try:
    import bootstrap_helper
    bootstrap_helper.bootstrap_and_reexecute_if_needed()
except ImportError:
    pass

from utils.logging_setup import setup_logging
from core.managers.container_registry_manager import ContainerRegistryManager

logger = logging.getLogger(__name__)

def load_config(config_path='config/settings.yaml') -> dict:
    full_path = os.path.join(HAU_ROOT, config_path)
    try:
        with open(full_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        return config
    except Exception as e:
        print(f"[FATAL] Could not load configuration from {full_path}. Error: {e}", file=sys.stderr)
        sys.exit(1)

def main():
    config = load_config()
    setup_logging(config)
    crm = ContainerRegistryManager(config)
    
    project = "ai/halo/sentinel"
    tag_to_delete = "v0.1.6-dev"
    
    print(f"Deleting tag '{tag_to_delete}' in project '{project}'...")
    succ, msg = crm.delete_container_tag(project, tag_to_delete)
    print(msg)
    
    print(f"Retagging 'dev' to '{tag_to_delete}' in project '{project}'...")
    succ, msg = crm.retag_container(project, 'dev', tag_to_delete)
    print(msg)
    
    if succ:
        print("Successfully fixed the container tag!")
    else:
        print("Failed to fix the container tag.")

if __name__ == "__main__":
    main()
