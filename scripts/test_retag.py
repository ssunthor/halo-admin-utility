#!/usr/bin/env python3
import os
import sys
import yaml

# Add parent directory to path so we can import core modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.managers.gitlab_manager import GitlabManager

def test_retag():
    # Load config
    config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config", "settings.yaml")
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)
        
    gitlab_config = config.get("external_services", {}).get("gitlab", {})
    manager = GitlabManager(gitlab_config)
    
    project_path = "ai/halo/pipelines/netflow-dfp-test"
    old_tag = "feat-changelog"
    new_tag = "v0.3.0-dev"
    
    print(f"Testing retagging container for {project_path} from '{old_tag}' to '{new_tag}'...")
    success, msg = manager.retag_container(project_path, old_tag, new_tag)
    
    if success:
        print(f"✅ SUCCESS: {msg}")
    else:
        print(f"❌ FAILED: {msg}")

if __name__ == "__main__":
    test_retag()
