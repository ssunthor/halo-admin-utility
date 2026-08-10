#!/usr/bin/env python3
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
HAU_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, '..'))

if HAU_ROOT not in sys.path:
    sys.path.insert(0, HAU_ROOT)

try:
    import bootstrap_helper
    bootstrap_helper.bootstrap_and_reexecute_if_needed()
except ImportError:
    pass

import yaml
import halo_admin_utility
from core.managers.kube_manager import KubeManager
from kubernetes.client import NetworkingV1Api

config = halo_admin_utility.load_config()
rancher_clusters = config.get('rancher_clusters', {})
slo_conf = rancher_clusters.get('slo')

output_dir = os.path.join(HAU_ROOT, "output/dump")

def dump_resource(kind, name, ns, data, cluster):
    data_dict = data.to_dict()
    if 'metadata' in data_dict:
        data_dict['metadata'].pop('managed_fields', None)
        data_dict['metadata'].pop('creation_timestamp', None)
        data_dict['metadata'].pop('resource_version', None)
        data_dict['metadata'].pop('uid', None)
        data_dict['metadata'].pop('generation', None)
    if 'status' in data_dict:
        data_dict.pop('status', None)
        
    kind_dir = os.path.join(output_dir, ns, cluster, kind)
    os.makedirs(kind_dir, exist_ok=True)
    
    file_path = os.path.join(kind_dir, f"{name}.yaml")
    with open(file_path, "w") as f:
        yaml.dump(data_dict, f)

def dump_cluster_namespaces(km, cluster_alias):
    print(f"Fetching namespaces for cluster {cluster_alias}...")
    try:
        ns_list = km.core_v1.list_namespace()
        namespaces_to_dump = []
        for ns_obj in ns_list.items:
            name = ns_obj.metadata.name
            if name.startswith("halo") or name.startswith("unmapped"):
                namespaces_to_dump.append(name)
                
        for ns in namespaces_to_dump:
            print(f"  -> Dumping {ns} from {cluster_alias}...")
            try:
                deps = km.apps_v1.list_namespaced_deployment(ns)
                for d in deps.items:
                    dump_resource("Deployment", d.metadata.name, ns, d, cluster_alias)
                
                svcs = km.core_v1.list_namespaced_service(ns)
                for s in svcs.items:
                    dump_resource("Service", s.metadata.name, ns, s, cluster_alias)
                    
                cms = km.core_v1.list_namespaced_config_map(ns)
                for c in cms.items:
                    dump_resource("ConfigMap", c.metadata.name, ns, c, cluster_alias)
                    
                ings = NetworkingV1Api(km.api_client).list_namespaced_ingress(ns)
                for i in ings.items:
                    dump_resource("Ingress", i.metadata.name, ns, i, cluster_alias)
                    
                pvcs = km.core_v1.list_namespaced_persistent_volume_claim(ns)
                for p in pvcs.items:
                    dump_resource("PVC", p.metadata.name, ns, p, cluster_alias)
            except Exception as e:
                print(f"    Error dumping namespace {ns}: {e}")
    except Exception as e:
        print(f"Error accessing cluster {cluster_alias}: {e}")

# App Cluster dump
app_cluster = slo_conf.get('halo_cluster_name')
km_app = KubeManager(slo_conf, app_cluster)
dump_cluster_namespaces(km_app, "app")

tenant_prefixes = {
    "gtt-core": "halo-core",
    "gtt-corp": "halo-corp",
    "gtt-demo": "halo-demo",
    "gtt-dev": "halo-dev",
    "gtt-nfv": "halo-nfv",
    "gtt-scott-dev": "halo-scott-dev",
    "gtt3d0": "halo-gtt3d0",
    "statrb": "halo-statrb"
}

def get_gpu_tenant(name):
    for prefix, tenant in tenant_prefixes.items():
        if name.startswith(prefix):
            return tenant
    return "halo"  # Default if no match (e.g. triton-server)

gpu_cluster = slo_conf.get('gpu_cluster_name')
print(f"Fetching namespaces for cluster gpu...")
try:
    km_gpu = KubeManager(slo_conf, gpu_cluster)
    deps = km_gpu.apps_v1.list_namespaced_deployment("halo")
    for d in deps.items:
        t_ns = get_gpu_tenant(d.metadata.name)
        dump_resource("Deployment", d.metadata.name, t_ns, d, "gpu")
    
    svcs = km_gpu.core_v1.list_namespaced_service("halo")
    for s in svcs.items:
        t_ns = get_gpu_tenant(s.metadata.name)
        dump_resource("Service", s.metadata.name, t_ns, s, "gpu")
        
    cms = km_gpu.core_v1.list_namespaced_config_map("halo")
    for c in cms.items:
        t_ns = get_gpu_tenant(c.metadata.name)
        dump_resource("ConfigMap", c.metadata.name, t_ns, c, "gpu")
        
    ings = NetworkingV1Api(km_gpu.api_client).list_namespaced_ingress("halo")
    for i in ings.items:
        t_ns = get_gpu_tenant(i.metadata.name)
        dump_resource("Ingress", i.metadata.name, t_ns, i, "gpu")
        
    pvcs = km_gpu.core_v1.list_namespaced_persistent_volume_claim("halo")
    for p in pvcs.items:
        t_ns = get_gpu_tenant(p.metadata.name)
        dump_resource("PVC", p.metadata.name, t_ns, p, "gpu")
except Exception as e:
    print(f"Error accessing cluster gpu: {e}")
