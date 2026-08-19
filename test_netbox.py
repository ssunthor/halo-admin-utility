import yaml
import json
from core.clients.netbox_client import NetboxClient

with open('config/settings.yaml', 'r') as f:
    config = yaml.safe_load(f)
nb_config = config['external_services']['netbox']
client = NetboxClient(url=nb_config['url'], token=nb_config['token'], verify_ssl=False)

# Let's try some slugs
slugs = ['gtt3d0', 'halo-gtt3d0', 'loparex-llc', 'loparex']
for slug in slugs:
    tenant = client.get_tenant(slug)
    if tenant:
        print(f"Found {slug}:")
        print(json.dumps(tenant, indent=2))
        break
else:
    print("None found")
