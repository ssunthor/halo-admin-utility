import sys
import os

# Ensure we can import from the halo_admin_utility root
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from config.settings import load_config
from core.managers.gitlab_manager import GitlabManager

def fix_deployment_changelog():
    config = load_config()
    gm = GitlabManager(config)

    file_path = '/ai/utilities/halo_admin_utility/cache/halo/deployment/docs/config-analyzer-backend/CHANGELOG.yaml'
    
    print(f"Reading fully merged changelog from {file_path}...")
    with open(file_path, 'r') as f:
        content = f.read()

    print("Pushing to ai/halo/deployment on branch 'main'...")
    try:
        res, msg = gm.commit_file_api(
            project_path="ai/halo/deployment",
            branch="main",
            file_path="docs/config-analyzer-backend/CHANGELOG.yaml",
            content=content,
            commit_msg="chore(docs): sync missing historical changelog up to v0.1.4 [skip ci]",
            author_name="GIA AI",
            author_email="gia-ai@gtt.net"
        )
        print("Deployment repo result:", msg)
    except Exception as e:
        print("Deployment repo error:", e)

if __name__ == "__main__":
    fix_deployment_changelog()
