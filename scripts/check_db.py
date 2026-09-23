import sys
sys.path.insert(0, '/ai/utilities/halo_admin_utility')
import yaml
from core.database.database import initialize_database, get_db_session
from core.database.models import GitProject

with open('/ai/utilities/halo_admin_utility/config/settings.yaml', 'r') as f:
    config = yaml.safe_load(f)

initialize_database(config)

with get_db_session(read_only=True) as session:
    p = session.query(GitProject).filter_by(project_name='netbox-inventory').first()
    if p:
        print(f"Project: {p.project_name}")
        print("Branches:", [b.name for b in p.branches])
        for c in p.containers:
            print(f"Tag: {c.tag_name}, ImagePath: {c.image_path}")
    else:
        print("Project not found")
