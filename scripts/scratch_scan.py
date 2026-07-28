import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from bootstrap_helper import bootstrap_and_reexecute_if_needed
bootstrap_and_reexecute_if_needed()
import yaml
from core.managers.kube_manager import KubeManager

with open("config/settings.yaml") as f:
    config = yaml.safe_load(f)

rancher_config = config['rancher_clusters']['slo']
cluster_name = rancher_config['gpu_cluster_name']

km = KubeManager(rancher_config, cluster_name)
print(f"Scanning GPU cluster: {cluster_name}")
ns_name = "halo"
print(f"Namespace: {ns_name}")
deps = km.apps_v1.list_namespaced_deployment(ns_name)
for d in deps.items:
    print(f"  - Deployment: {d.metadata.name}")
    # let's also check labels to see if tenant info is there
    print(f"    Labels: {d.metadata.labels}")
    
# also let's check pods just in case
pods = km.core_v1.list_namespaced_pod(ns_name)
for p in pods.items:
    print(f"  - Pod: {p.metadata.name}")
    print(f"    Labels: {p.metadata.labels}")
