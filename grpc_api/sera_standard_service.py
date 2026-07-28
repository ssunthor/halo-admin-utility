import os
import logging
import grpc
from typing import Dict, Any

try:
    import sera_standard_pb2
    import sera_standard_pb2_grpc
except ImportError:
    pass

logger = logging.getLogger(__name__)

def extract_client_id(context) -> str:
    if context:
        metadata = dict(context.invocation_metadata())
        return metadata.get('x-client-id', 'UNKNOWN')
    return 'UNKNOWN'

class SeraStandardServiceImpl(sera_standard_pb2_grpc.SeraAppServiceServicer):
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.module_info = config.get('module_info', {})
        self.base_dir = os.getcwd()

    def _get_changelog_path(self):
        return os.path.join(self.base_dir, 'docs', 'CHANGELOG.yaml')

    def _get_version(self):
        try:
            import yaml
            path = self._get_changelog_path()
            if os.path.exists(path):
                with open(path, 'r') as f:
                    cl = yaml.safe_load(f)
                    if cl and isinstance(cl, list) and len(cl) > 0:
                        return str(cl[0].get("version", "unknown"))
        except Exception as e:
            logger.warning(f"Failed to parse version from changelog: {e}")
        return "unknown"

    def GetAppInfo(self, request, context):
        client_id = extract_client_id(context)
        logger.info(f"[{client_id}] GetAppInfo (SERA Standard)")
        services = []
        sys_svcs = self.config.get('system_services', {})
        for svc_key, svc_data in sys_svcs.items():
            ep = ""
            if svc_data.get('host') and svc_data.get('port'):
                ep = f"{svc_data.get('host')}:{svc_data.get('port')}"
            
            service_name = svc_data.get('service_name', '')
            status = "unknown"
            if service_name:
                import subprocess
                try:
                    res = subprocess.run(['systemctl', 'is-active', service_name], capture_output=True, text=True, timeout=2)
                    status = "running" if res.stdout.strip() == "active" else "stopped"
                except Exception:
                    pass
                    
            services.append(sera_standard_pb2.ServiceInfo(
                service_name=service_name,
                endpoint=ep,
                service_type=svc_data.get('service_type', ''),
                status=status
            ))

        deps = []
        if 'database' in self.config:
            deps.append("postgresql")
        if any(k in self.config for k in ['redis', 'valkey', 'redis_cache']):
            deps.append("cache")
        if 'vector_database' in self.config:
            deps.append("chromadb")
        if 'rancher_clusters' in self.config:
            deps.append("rancher")
            
        for conn_name in self.config.get('connectors', {}).keys():
            deps.append(conn_name)
            
        for ext_name in self.config.get('external_services', {}).keys():
            deps.append(ext_name)
            
        resp = sera_standard_pb2.AppInfoResponse(
            version=self._get_version(),
            acronym=self.module_info.get('acronym', 'unknown'),
            name=self.module_info.get('name', 'unknown'),
            category=self.module_info.get('category', 'unknown'),
            description=self.module_info.get('description', 'unknown'),
            services=services,
            downstream_dependencies=deps,
            custom_metadata={"sera_standard": "v1-universal"}
        )

        llm_config = self.config.get("llm_engines", {})
        for model_key, model_data in llm_config.items():
            llm_info = resp.llm_models.add()
            llm_info.key = model_key
            llm_info.model_name = model_data.get("model", "")
            llm_info.base_url = model_data.get("base_url", "")

        return resp

    def GetDeepHealth(self, request, context):
        client_id = extract_client_id(context)
        logger.info(f"[{client_id}] GetDeepHealth (SERA Standard)")
        
        response = sera_standard_pb2.DeepHealthResponse(
            app_acronym=self.module_info.get('acronym', 'unknown'),
            app_version=self._get_version(),
            overall_status="HEALTHY"
        )
        
        # Database
        db_config = self.config.get('database', {})
        write_dsn = db_config.get('write_dsn', '')
        read_dsn = db_config.get('read_dsn', '')
        
        def sanitize_dsn(dsn_str: str) -> str:
            import urllib.parse
            def sanitize_single(single_dsn):
                if not single_dsn or "://" not in single_dsn: return single_dsn
                try:
                    parsed = urllib.parse.urlparse(single_dsn)
                    
                    # If neither username nor password exists, no sanitization needed
                    if not parsed.username and not parsed.password:
                        return single_dsn
                        
                    netloc = ""
                    if parsed.username:
                        netloc = f"{parsed.username}@"
                        
                    netloc += str(parsed.hostname or "")
                    if parsed.port:
                        netloc += f":{parsed.port}"
                        
                    return urllib.parse.urlunparse((parsed.scheme, netloc, parsed.path, parsed.params, parsed.query, parsed.fragment))
                except Exception:
                    return single_dsn
            
            if ";" in dsn_str:
                return ";".join(sanitize_single(p) for p in dsn_str.split(";"))
            elif "," in dsn_str:
                return ",".join(sanitize_single(p) for p in dsn_str.split(","))
            return sanitize_single(dsn_str)
            
        def get_host(dsn_str: str) -> str:
            if "@" in dsn_str:
                return dsn_str.split("@")[-1].split(":")[0]
            return "unknown"
            
        def get_db_name(dsn_str: str) -> str:
            if "/" in dsn_str:
                return dsn_str.split("/")[-1].split("?")[0]
            return "unknown"
            
        def get_host_port_from_url(url_str: str):
            if not url_str: return None, None
            if "://" not in url_str:
                url_str = "http://" + url_str
            import urllib.parse
            parsed = urllib.parse.urlparse(url_str)
            host = parsed.hostname
            port = parsed.port
            if not port:
                if parsed.scheme == 'https': port = 443
                elif parsed.scheme == 'http': port = 80
            return host, port

        def check_tcp_ping(host, port, timeout=1.0):
            if not host or not port:
                return "UNKNOWN", "Missing host/port"
            import socket
            try:
                with socket.create_connection((host, int(port)), timeout=timeout):
                    return "OK", "Connected"
            except socket.timeout:
                return "DOWN", "Connection Timeout"
            except Exception as e:
                return "DOWN", f"Connection Failed: {e}"

        if write_dsn or read_dsn:
            acronym = self.module_info.get('acronym', 'unknown').lower()
            category = self.module_info.get('category', 'unknown').lower()
            
            w_host, w_port = get_host_port_from_url(write_dsn)
            r_host, r_port = get_host_port_from_url(read_dsn)
            
            status = "OK"
            details = "Connected"
            
            w_status, w_det = check_tcp_ping(w_host, w_port) if w_host else ("OK", "Connected")
            r_status, r_det = check_tcp_ping(r_host, r_port) if r_host else ("OK", "Connected")
            
            if w_status == "DOWN" or r_status == "DOWN":
                status = "DOWN"
                details = "Database Unreachable"
                
            db_dep = sera_standard_pb2.DependencyHealth(
                dependency_name=f"{acronym}_{category}_db",
                status=status,
                details=details,
                dependency_type="postgresql",
                dependency_group="infra"
            )
            if write_dsn:
                db_dep.connection_metadata["write_host"] = str(w_host) if w_host else "unknown"
                db_dep.connection_metadata["database"] = get_db_name(write_dsn)
                db_dep.connection_metadata["write_sanitized_dsn"] = sanitize_dsn(write_dsn)
            if read_dsn:
                db_dep.connection_metadata["read_host"] = str(r_host) if r_host else "unknown"
                db_dep.connection_metadata["read_sanitized_dsn"] = sanitize_dsn(read_dsn)
            response.dependency_health_matrix.append(db_dep)
            
        # Connectors
        for conn_name, conn_data in self.config.get('connectors', {}).items():
            meta = {}
            for k, v in conn_data.items():
                if k == 'timeout_seconds':
                    meta['timeout'] = str(v)
                else:
                    meta[k] = str(v)
                    
            if 'target' not in meta and 'host' in meta and 'port' in meta:
                meta['target'] = f"{meta['host']}:{meta['port']}"
                del meta['host']
                del meta['port']
                
            d_name = f"{conn_name}_connector" if not conn_name.endswith("_connector") else conn_name
            
            target = meta.get('target', '')
            c_host, c_port = get_host_port_from_url(target)
            if not c_port and ":" in target:
                parts = target.split(":")
                c_host, c_port = parts[0], parts[1]
                
            status, details = check_tcp_ping(c_host, c_port)
            
            response.dependency_health_matrix.append(
                sera_standard_pb2.DependencyHealth(
                    dependency_name=d_name,
                    status=status,
                    details=details,
                    dependency_type="grpc_connector",
                    dependency_group="connector",
                    connection_metadata=meta
                )
            )
            

        # Caching (Redis/Valkey)
        import urllib.parse
        for cache_key in ['redis', 'valkey', 'redis_cache']:
            c_data = self.config.get(cache_key)
            if c_data and isinstance(c_data, dict):
                usages = []
                for k, v in c_data.items():
                    if k in ['url', 'host', 'nodes']:
                        usages.append((cache_key, {k: str(v)}))
                    elif k.endswith('_url') or k.endswith('_backend') or k in ['broker', 'result']:
                        usages.append((k, {'url': str(v)}))
                
                for name, meta in usages:
                    clean_name = name.replace('_url', '').replace('_backend', '')
                    
                    acronym = self.module_info.get('acronym', 'unknown').lower()
                    if clean_name not in cache_key:
                        dep_name = f"{acronym}_{cache_key}_{clean_name}"
                    else:
                        dep_name = f"{acronym}_{cache_key}" if cache_key.endswith("_cache") else f"{acronym}_{cache_key}_cache"
                        
                    c_type = "valkey" if "valkey" in cache_key.lower() else "redis"
                    
                    url_str = meta.get('url', meta.get('host', ''))
                    
                    if url_str and "://" in url_str:
                        meta['sanitized_url'] = sanitize_dsn(url_str)
                        if 'url' in meta:
                            del meta['url']
                            
                        first_url = url_str.split(';')[0].split(',')[0]
                        c_host, c_port = get_host_port_from_url(first_url)
                        if c_host:
                            meta['host'] = c_host
                            
                        import urllib.parse
                        path_part = urllib.parse.urlparse(first_url).path
                        if path_part and path_part.startswith('/'):
                            db_str = path_part[1:].split('?')[0]
                            if db_str.isdigit():
                                meta['database'] = db_str

                        hosts_to_check = url_str.split(';') if ';' in url_str else url_str.split(',')
                        alive_nodes = 0
                        status = "DOWN"
                        details = "All nodes unreachable"
                        
                        for u in hosts_to_check:
                            h, p = get_host_port_from_url(u.strip())
                            s, d = check_tcp_ping(h, p)
                            if s == "OK":
                                alive_nodes += 1
                                status = "OK"
                                details = "Connected"
                        
                        try:
                            import redis
                            r = None
                            for u in hosts_to_check:
                                u_clean = u.strip()
                                try:
                                    r_url = u_clean.replace("valkey://", "redis://").replace("sentinel://", "redis://").replace(":26379", ":6379")
                                    r = redis.from_url(r_url, decode_responses=True, socket_timeout=0.2)
                                    if r: break
                                except Exception:
                                    pass
                                        
                            if r:
                                owner_flag = r.get("__GIA_DB_OWNER__")
                                if not owner_flag:
                                    owner_flag = r.get("__SERA_DB_OWNER__")
                                if owner_flag:
                                    if " - " in owner_flag:
                                        owner_flag = owner_flag.split(" - ", 1)[-1]
                                    meta['description'] = owner_flag
                                r.close()
                        except Exception:
                            pass
                    else:
                        c_host = meta.get('host', '')
                        c_port = meta.get('port', '')
                        status, details = check_tcp_ping(c_host, c_port)
                        if 'database' in c_data:
                            meta['database'] = str(c_data['database'])
                    
                    response.dependency_health_matrix.append(
                        sera_standard_pb2.DependencyHealth(
                            dependency_name=dep_name,
                            status=status,
                            details=details,
                            dependency_type=c_type,
                            dependency_group="infra",
                            connection_metadata=meta
                        )
                    )

        # Vector Database
        vdb_config = self.config.get('vector_database', {})
        if vdb_config:
            meta = {}
            collections_list = []
            for k, v in vdb_config.items():
                if k in ['host', 'port', 'url']:
                    meta[k] = str(v)
                elif k.endswith('collection_name') or k == 'collections':
                    if isinstance(v, str):
                        collections_list.extend([c.strip() for c in v.split(',') if c.strip()])
                        
            if collections_list:
                meta['collections'] = ", ".join(list(dict.fromkeys(collections_list)))
                    
            acronym = self.module_info.get('acronym', 'unknown').lower()
            category = self.module_info.get('category', 'unknown').lower()
            
            v_host = meta.get('host')
            v_port = meta.get('port')
            status, details = check_tcp_ping(v_host, v_port)
            
            response.dependency_health_matrix.append(
                sera_standard_pb2.DependencyHealth(
                    dependency_name=f"{acronym}_{category}_vdb",
                    status=status,
                    details=details,
                    dependency_type="chromadb",
                    dependency_group="infra",
                    connection_metadata=meta
                )
            )

        # Rancher Clusters (External Nested)
        rancher_clusters = self.config.get('rancher_clusters', {})
        if rancher_clusters:
            for loc, r_data in rancher_clusters.items():
                meta = {}
                for k, v in r_data.items():
                    if k in ['url', 'cluster_id', 'cluster_name', 'app_cluster_name', 'gpu_cluster_name']:
                        meta[k] = str(v)
                r_host, r_port = get_host_port_from_url(meta.get('url'))
                status, details = check_tcp_ping(r_host, r_port)
                
                response.dependency_health_matrix.append(
                    sera_standard_pb2.DependencyHealth(
                        dependency_name=f"rancher_{loc.lower()}",
                        status=status,
                        details=details,
                        dependency_type="rest_api",
                        dependency_group="internal",
                        connection_metadata=meta
                    )
                )
                

        # External Services
        for ext_name, ext_data in self.config.get('external_services', {}).items():
            meta = {}
            dep_name = ext_name
            dep_type = "external_api"
            if isinstance(ext_data, dict):
                dep_name = ext_data.get('dependency_name', ext_name)
                dep_type = ext_data.get('type', 'external_api')
                for k, v in ext_data.items():
                    if k in ['url', 'instance_url', 'api_url', 'base_url', 'host', 'port', 'server_address']:
                        meta[k] = str(v) if not isinstance(v, list) else ", ".join([str(x) for x in v])
            else:
                meta['value'] = str(ext_data)

            e_host = None
            e_port = None
            
            if isinstance(ext_data, dict):
                if 'server_address' in ext_data:
                    addrs = ext_data['server_address']
                    if isinstance(addrs, list) and len(addrs) > 0:
                        e_host = str(addrs[0])
                    elif isinstance(addrs, str):
                        e_host = addrs.split(',')[0].strip()
                        
            if not e_host:
                e_host, parsed_port = get_host_port_from_url(meta.get('url', meta.get('api_url', meta.get('base_url', meta.get('host', '')))))
                if parsed_port:
                    e_port = parsed_port
                    
            if isinstance(ext_data, dict) and 'port' in ext_data:
                e_port = ext_data['port']
            elif dep_type == 'ldap' and not e_port:
                e_port = 636

            status, details = check_tcp_ping(e_host, e_port)

            group = "external"
            if isinstance(ext_data, dict) and 'dependency_group' in ext_data:
                group = ext_data['dependency_group']
            elif "vault" in dep_name.lower() or "keycloak" in dep_name.lower() or "gateway" in dep_name.lower():
                group = "internal"

            response.dependency_health_matrix.append(
                sera_standard_pb2.DependencyHealth(
                    dependency_name=dep_name,
                    status=status,
                    details=details,
                    dependency_type=dep_type,
                    dependency_group=group,
                    connection_metadata=meta
                )
            )
            


        # Services
        sys_svcs = self.config.get('system_services', {})
        for svc_key, svc_data in sys_svcs.items():
            ep = ""
            if svc_data.get('host') and svc_data.get('port'):
                ep = f"{svc_data.get('host')}:{svc_data.get('port')}"
                
            service_name = svc_data.get('service_name', '')
            status = "unknown"
            if service_name:
                import subprocess
                try:
                    res = subprocess.run(['systemctl', 'is-active', service_name], capture_output=True, text=True, timeout=2)
                    status = "running" if res.stdout.strip() == "active" else "stopped"
                except Exception:
                    pass
                    
            response.service_health_matrix.append(
                sera_standard_pb2.ServiceInfo(
                    service_name=service_name,
                    endpoint=ep,
                    service_type=svc_data.get('service_type', ''),
                    status=status
                )
            )

        overall = "HEALTHY"
        for svc in response.service_health_matrix:
            if svc.status != "running":
                overall = "DEGRADED"
        for dep in response.dependency_health_matrix:
            if dep.status != "OK":
                overall = "DEGRADED"
        response.overall_status = overall

        return response

    def GetFeedback(self, request, context):
        client_id = extract_client_id(context)
        logger.info(f"[{client_id}] GetFeedback (SERA Standard)")
        return sera_standard_pb2.FeedbackResponse()

    def GetChangelog(self, request, context):
        client_id = extract_client_id(context)
        logger.info(f"[{client_id}] GetChangelog (SERA Standard)")
        try:
            path = self._get_changelog_path()
            if os.path.exists(path):
                with open(path, 'r') as f:
                    return sera_standard_pb2.ChangelogResponse(raw_yaml_changelog=f.read())
            return sera_standard_pb2.ChangelogResponse()
        except Exception as e:
            logger.error(f"Failed to read changelog: {e}", exc_info=True)
            context.set_details(str(e))
            context.set_code(grpc.StatusCode.INTERNAL)
            return sera_standard_pb2.ChangelogResponse()

    def GetDocs(self, request, context):
        client_id = extract_client_id(context)
        logger.info(f"[{client_id}] GetDocs (SERA Standard)")
        try:
            acronym = self.module_info.get('acronym', '').lower()
            doc_path = os.path.join(self.base_dir, 'docs', f'{acronym}_design.md')
            if not os.path.exists(doc_path):
                doc_path = os.path.join(self.base_dir, 'README.md')
                
            if os.path.exists(doc_path):
                with open(doc_path, 'r') as f:
                    return sera_standard_pb2.DocsResponse(raw_markdown=f.read())
            return sera_standard_pb2.DocsResponse(raw_markdown="# Documentation not found")
        except Exception as e:
            logger.error(f"Failed to read docs: {e}", exc_info=True)
            context.set_details(str(e))
            context.set_code(grpc.StatusCode.INTERNAL)
            return sera_standard_pb2.DocsResponse()
