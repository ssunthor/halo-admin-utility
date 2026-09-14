#!/usr/bin/env python3
import os
import sys
import json
import requests
import yaml
import urllib3
from requests.auth import HTTPBasicAuth

# Bypass proxy for gitlab
os.environ['NO_PROXY'] = 'gitlab.gt-t.net'
os.environ['no_proxy'] = 'gitlab.gt-t.net'

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
MODULE_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, '..'))
if MODULE_ROOT not in sys.path:
    sys.path.insert(0, MODULE_ROOT)

try:
    import bootstrap_helper
    bootstrap_helper.bootstrap_and_reexecute_if_needed()
except ImportError:
    pass

def main():
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    config_path = os.path.abspath(os.path.join(MODULE_ROOT, 'config', 'settings.yaml'))
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
        
    gitlab_url = config['external_services']['gitlab']['url'].rstrip('/')
    token = config['external_services']['gitlab']['bot_token']
    project_path = "ai/halo/backend"
    
    print("Fetching registry auth token...")
    auth_url = f"{gitlab_url}/jwt/auth?service=container_registry&scope=repository:{project_path}:pull"
    res_auth = requests.get(auth_url, auth=HTTPBasicAuth('oauth2', token), verify=False)
    if res_auth.status_code != 200:
        res_auth = requests.get(auth_url, headers={"Authorization": f"Bearer {token}"}, verify=False)
        if res_auth.status_code != 200:
            print(f"Failed to get registry token: {res_auth.status_code} {res_auth.text}")
            return
            
    registry_token = res_auth.json().get('token')
    domain = gitlab_url.replace("https://", "").replace("http://", "")
    registry_url = f"https://{domain}:4567/v2/{project_path}/manifests/dev"
    
    print(f"\nFetching manifest from {registry_url}...")
    headers = {
        "Authorization": f"Bearer {registry_token}",
        "Accept": "application/vnd.docker.distribution.manifest.v2+json, application/vnd.oci.image.manifest.v1+json"
    }
    res_manifest = requests.get(registry_url, headers=headers, verify=False)
    
    if res_manifest.status_code != 200:
        print(f"Failed to get manifest: {res_manifest.status_code} {res_manifest.text}")
        return
        
    manifest = res_manifest.json()
    config_digest = manifest.get('config', {}).get('digest')
    print(f"Manifest config digest: {config_digest}")
    
    if config_digest:
        blob_url = f"https://{domain}:4567/v2/{project_path}/blobs/{config_digest}"
        print(f"Fetching config blob from {blob_url}...")
        res_blob = requests.get(blob_url, headers=headers, verify=False)
        if res_blob.status_code == 200:
            blob = res_blob.json()
            created = blob.get('created')
            print(f"\n=> SUCCESS! The real 'created' date from the Docker Image Config is: {created}")
            print("\nFull Blob Config (truncated):")
            print(json.dumps({k: v for k, v in blob.items() if k in ('created', 'author', 'architecture', 'os')}, indent=2))
        else:
            print(f"Failed to fetch config blob: {res_blob.status_code} {res_blob.text}")

if __name__ == "__main__":
    main()
