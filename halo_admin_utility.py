#!/usr/bin/env python3
import os
import sys
import yaml
import logging

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

try:
    import bootstrap_helper
    bootstrap_helper.bootstrap_and_reexecute_if_needed()
except ImportError:
    pass

from utils.logging_setup import setup_logging
from cli import hau_cli

logger = logging.getLogger(__name__)

def load_config(config_path='config/settings.yaml') -> dict:
    full_path = os.path.join(SCRIPT_DIR, config_path)
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
    hau_cli.cli(obj={'config': config})

if __name__ == '__main__':
    main()
