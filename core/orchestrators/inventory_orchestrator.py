import logging
from core.managers.kube_manager import KubeManager
from kubernetes.client import NetworkingV1Api

logger = logging.getLogger(__name__)

class InventoryOrchestrator:
    def __init__(self, config, sql_writer):
        self.config = config
        self.sql_writer = sql_writer
        self.rancher_clusters = config.get('rancher_clusters', {})

    def parse_tenant_metadata(self, slug_name):
        # Best effort parsing of halo-<customer>-<environment> or known mess
        is_internal = False
        environment = 'prod' # Default
        
        # Determine internal flag based on keywords
        internal_keywords = ['corp', 'nfv', 'soc', 'dev', 'core', 'sentinel']
        for kw in internal_keywords:
            if kw in slug_name.split('-'):
                is_internal = True
                break
                
        # Determine environment based on keywords
        if 'dev' in slug_name:
            environment = 'dev'
        elif 'demo' in slug_name:
            environment = 'demo'
        elif 'stage' in slug_name:
            environment = 'stage'
            
        return environment, is_internal

    def sync_inventory(self):
        logger.info("Starting inventory sync across all configured clusters...")
        self.sql_writer.clear_inventory()
        
        for region, cluster_conf in self.rancher_clusters.items():
            app_cluster = cluster_conf.get('halo_cluster_name')
            gpu_cluster = cluster_conf.get('gpu_cluster_name')

            if app_cluster:
                self._sync_app_cluster(region, cluster_conf, app_cluster)
            
            if gpu_cluster:
                self._sync_gpu_cluster(region, cluster_conf, gpu_cluster)

        logger.info("Inventory sync complete.")

    def _sync_app_cluster(self, region, cluster_conf, app_cluster):
        logger.info(f"Connecting to App cluster: {app_cluster}")
        try:
            km = KubeManager(cluster_conf, app_cluster)
            namespaces = km.core_v1.list_namespace()
        except Exception as e:
            logger.error(f"Failed to connect or list namespaces on {app_cluster}: {e}")
            return
            
        for ns in namespaces.items:
            ns_name = ns.metadata.name
            
            # Identify if it is a halo namespace
            if ns_name.startswith("halo") or ns_name.startswith("tenant"):
                self._process_app_namespace(km, app_cluster, ns_name)

    def _process_app_namespace(self, km, app_cluster, ns_name):
        env, is_internal = self.parse_tenant_metadata(ns_name)
        tenant = self.sql_writer.upsert_halo_tenant(
            slug_name=ns_name,
            target_cluster=app_cluster,
            environment=env,
            is_internal=is_internal
        )
            
        # Get deployments
        try:
            deps = km.apps_v1.list_namespaced_deployment(ns_name)
            for d in deps.items:
                image = d.spec.template.spec.containers[0].image.split('/')[-1] if d.spec.template.spec.containers else "None"
                meta = {
                    "status": f"{d.status.ready_replicas or 0}/{d.status.replicas or 0} Ready",
                    "image": image
                }
                self.sql_writer.upsert_tenant_resource(tenant.id, 'Deployments', d.metadata.name, meta, app_cluster)
        except Exception as e:
            logger.error(f"Failed to list deployments in {ns_name}: {e}")

        # Get Services
        try:
            svcs = km.core_v1.list_namespaced_service(ns_name)
            for s in svcs.items:
                port_maps = []
                if s.spec.ports:
                    for p in s.spec.ports:
                        port_maps.append(f"{p.port}:{p.target_port}/{p.protocol}")
                meta = {
                    "type": s.spec.type,
                    "cluster_ip": s.spec.cluster_ip,
                    "ports": ", ".join(port_maps)
                }
                self.sql_writer.upsert_tenant_resource(tenant.id, 'Services', s.metadata.name, meta, app_cluster)
        except Exception as e:
            logger.error(f"Failed to list services in {ns_name}: {e}")

        # Get Endpoints
        try:
            endpoints = km.core_v1.list_namespaced_endpoints(ns_name)
            for e in endpoints.items:
                target_ips = []
                if e.subsets:
                    for subset in e.subsets:
                        if subset.addresses:
                            target_ips.extend([addr.ip for addr in subset.addresses])
                meta = {
                    "backend_ips": ", ".join(target_ips) if target_ips else "No active backends"
                }
                self.sql_writer.upsert_tenant_resource(tenant.id, 'Endpoints', e.metadata.name, meta, app_cluster)
        except Exception as e:
            logger.error(f"Failed to list endpoints in {ns_name}: {e}")
            
        # Get Active Pods
        try:
            pods = km.core_v1.list_namespaced_pod(ns_name)
            for p in pods.items:
                meta = {
                    "phase": p.status.phase,
                    "pod_ip": p.status.pod_ip,
                    "host_ip": p.status.host_ip if p.status.host_ip else "Unknown",
                    "node_name": p.spec.node_name if p.spec.node_name else "Unknown"
                }
                self.sql_writer.upsert_tenant_resource(tenant.id, 'Active Pods', p.metadata.name, meta, app_cluster)
        except Exception as e:
            logger.error(f"Failed to list pods in {ns_name}: {e}")
            
        # Get PVCs
        try:
            pvcs = km.core_v1.list_namespaced_persistent_volume_claim(ns_name)
            for p in pvcs.items:
                meta = {
                    "status": p.status.phase,
                    "size": p.spec.resources.requests.get('storage', 'Unknown') if p.spec.resources.requests else "Unknown"
                }
                self.sql_writer.upsert_tenant_resource(tenant.id, 'PVCs', p.metadata.name, meta, app_cluster)
        except Exception as e:
            logger.error(f"Failed to list pvcs in {ns_name}: {e}")

        # Get ingresses
        try:
            net_v1 = NetworkingV1Api(km.api_client)
            ings = net_v1.list_namespaced_ingress(ns_name)
            for i in ings.items:
                hosts = []
                if i.spec.rules:
                    for r in i.spec.rules:
                        if r.host and not tenant.url:
                            tenant.url = f"https://{r.host}"
                        if r.http and r.http.paths:
                            for path in r.http.paths:
                                p_num = path.backend.service.port.number if path.backend.service and path.backend.service.port else "Unknown"
                                hosts.append(f"{r.host or '*'}->svc_port:{p_num}")
                        else:
                            hosts.append(r.host or '*')
                lb_ips = []
                if i.status and i.status.load_balancer and i.status.load_balancer.ingress:
                    lb_ips = [lbi.ip for lbi in i.status.load_balancer.ingress if lbi.ip]
                meta = {
                    "hosts": ", ".join(hosts),
                    "load_balancer_ips": ", ".join(lb_ips) if lb_ips else "Pending/None"
                }
                self.sql_writer.upsert_tenant_resource(tenant.id, 'Ingresses', i.metadata.name, meta, app_cluster)
        except Exception as e:
            logger.error(f"Failed to list ingresses in {ns_name}: {e}")

        # Get ConfigMaps
        try:
            cms = km.core_v1.list_namespaced_config_map(ns_name)
            for c in cms.items:
                matched_keys = list(c.data.keys()) if c.data else []
                meta = {
                    "matched_keys": ", ".join(matched_keys)
                }
                self.sql_writer.upsert_tenant_resource(tenant.id, 'ConfigMaps', c.metadata.name, meta, app_cluster)
        except Exception as e:
            logger.error(f"Failed to list configmaps in {ns_name}: {e}")

    def _sync_gpu_cluster(self, region, cluster_conf, gpu_cluster):
        logger.info(f"Connecting to GPU cluster: {gpu_cluster}")
        try:
            km = KubeManager(cluster_conf, gpu_cluster)
            ns_name = "halo"
            deps = km.apps_v1.list_namespaced_deployment(ns_name)
            svcs = km.core_v1.list_namespaced_service(ns_name)
            endpoints = km.core_v1.list_namespaced_endpoints(ns_name)
            pods = km.core_v1.list_namespaced_pod(ns_name)
        except Exception as e:
            logger.error(f"Failed to connect or list resources in GPU cluster {gpu_cluster}: {e}")
            return
            
        tenant_map = {}
        
        def get_tenant(dep_name):
            if dep_name in tenant_map:
                return tenant_map[dep_name]
                
            tenant_slug = self._infer_tenant_from_pipeline(dep_name)
            if tenant_slug:
                env, is_internal = self.parse_tenant_metadata(tenant_slug)
                tenant = self.sql_writer.upsert_halo_tenant(
                    slug_name=tenant_slug,
                    target_cluster=cluster_conf.get('halo_cluster_name', 'UNKNOWN'),
                    environment=env,
                    is_internal=is_internal
                )
            else:
                unmapped_slug = f"unmapped-gpu-{region}"
                tenant = self.sql_writer.upsert_halo_tenant(
                    slug_name=unmapped_slug,
                    target_cluster=gpu_cluster,
                    environment='unknown',
                    is_internal=True
                )
            tenant_map[dep_name] = tenant
            return tenant

        for d in deps.items:
            dep_name = d.metadata.name
            if 'triton' in dep_name:
                continue
                
            tenant = get_tenant(dep_name)
            image = d.spec.template.spec.containers[0].image.split('/')[-1] if d.spec.template.spec.containers else "None"
            meta = {
                "status": f"{d.status.ready_replicas or 0}/{d.status.replicas or 0} Ready",
                "image": image
            }
            self.sql_writer.upsert_tenant_resource(tenant.id, 'GPU_Deployments', dep_name, meta, gpu_cluster)
            
        for s in svcs.items:
            svc_name = s.metadata.name
            if 'triton' in svc_name:
                continue
            tenant = get_tenant(svc_name)
            port_maps = []
            if s.spec.ports:
                for p in s.spec.ports:
                    port_maps.append(f"{p.port}:{p.target_port}/{p.protocol}")
            meta = {
                "type": s.spec.type,
                "cluster_ip": s.spec.cluster_ip,
                "ports": ", ".join(port_maps)
            }
            self.sql_writer.upsert_tenant_resource(tenant.id, 'GPU_Services', svc_name, meta, gpu_cluster)
            
        for e in endpoints.items:
            ep_name = e.metadata.name
            if 'triton' in ep_name:
                continue
            tenant = get_tenant(ep_name)
            target_ips = []
            if e.subsets:
                for subset in e.subsets:
                    if subset.addresses:
                        target_ips.extend([addr.ip for addr in subset.addresses])
            meta = {
                "backend_ips": ", ".join(target_ips) if target_ips else "No active backends"
            }
            self.sql_writer.upsert_tenant_resource(tenant.id, 'GPU_Endpoints', ep_name, meta, gpu_cluster)
            
        for p in pods.items:
            pod_name = p.metadata.name
            if 'triton' in pod_name:
                continue
            # Try to map pod to a deployment by removing suffix
            base_name = "-".join(pod_name.split("-")[:-2]) if len(pod_name.split("-")) > 2 else pod_name
            tenant = get_tenant(base_name)
            meta = {
                "phase": p.status.phase,
                "pod_ip": p.status.pod_ip,
                "host_ip": p.status.host_ip if p.status.host_ip else "Unknown",
                "node_name": p.spec.node_name if p.spec.node_name else "Unknown"
            }
            self.sql_writer.upsert_tenant_resource(tenant.id, 'GPU_Active_Pods', pod_name, meta, gpu_cluster)


    def _infer_tenant_from_pipeline(self, dep_name):
        # Patterns like gtt-corp-syslog-pipeline -> halo-corp
        prefixes_to_strip = ['gtt-']
        suffixes_to_strip = [
            '-syslog-pipeline', '-syslog-pipeline-v2', 
            '-netflow-pipeline', '-netflow-pipeline-v2', 
            '-netflow-dfp', '-firewall-pipeline', '-firewall-pipeline-v2',
            '-fortinet-pipeline', '-fortinet-pipeline-v2'
        ]
        
        base_name = dep_name
        
        # Remove -loadbalancer suffix if it exists (e.g. for services)
        if base_name.endswith('-loadbalancer'):
            base_name = base_name[:-len('-loadbalancer')]
            
        for s in suffixes_to_strip:
            if base_name.endswith(s):
                base_name = base_name[:-len(s)]
                
        # If it was just triton or test pod, we can't map it to a specific tenant
        if base_name == dep_name or 'test-' in base_name:
            return None 
            
        # Clean prefix
        for p in prefixes_to_strip:
            if base_name.startswith(p):
                base_name = base_name[len(p):]
                
        return f"halo-{base_name}"
