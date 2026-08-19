#!/usr/bin/env python3
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
HAU_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, '..'))
if HAU_ROOT not in sys.path: sys.path.insert(0, HAU_ROOT)

import halo_admin_utility
from core.managers.kube_manager import KubeManager
from kubernetes.client import CustomObjectsApi
from core.clients.vault_client import VaultClient

config = halo_admin_utility.load_config()
rancher_clusters = config.get('rancher_clusters', {})
slo_conf = rancher_clusters.get('slo')

vault_client = VaultClient(config['external_services']['vault'])
app_cluster = slo_conf.get('halo_cluster_name')
km_app = KubeManager(slo_conf, app_cluster, vault_client=vault_client, config_ref=config)

custom_api = CustomObjectsApi(km_app.api_client)

print(f"Checking ClusterSecretStores (v1) in cluster {app_cluster}...")
try:
    css_list = custom_api.list_cluster_custom_object(
        group="external-secrets.io",
        version="v1",
        plural="clustersecretstores"
    )
    for item in css_list.get('items', []):
        print(f" - Found ClusterSecretStore: {item['metadata']['name']}")
except Exception as e:
    print(f"Error fetching ClusterSecretStores: {e}")
