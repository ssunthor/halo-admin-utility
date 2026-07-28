import os
import tarfile
import tempfile
import yaml
import logging
import urllib3
from kubernetes import client, config
from kubernetes.stream import stream
from kubernetes.client.rest import ApiException
import requests

from core.managers.prometheus_manager import PrometheusManager

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)

class KubeManager:
    @staticmethod
    def get_all_cluster_names(rancher_config):
        api_url = rancher_config['url']
        token = rancher_config['token']
        resp = requests.get(f"{api_url}/v3/clusters", headers={'Authorization': f"Bearer {token}"}, verify=False, timeout=10)
        if resp.status_code == 200:
            clusters = resp.json().get('data', [])
            return [c.get('name') for c in clusters if c.get('name')]
        return []

    def __init__(self, rancher_config, cluster_name):
        self.api_url = rancher_config['url']
        self.token = rancher_config['token']
        
        resp = requests.get(f"{self.api_url}/v3/clusters", headers={'Authorization': f"Bearer {self.token}"}, verify=False, timeout=10)
        if resp.status_code == 200:
            clusters = resp.json().get('data', [])
            cluster_id = None
            for c in clusters:
                if c.get('name') == cluster_name:
                    cluster_id = c.get('id')
                    break
            if not cluster_id:
                raise RuntimeError(f"Could not find Rancher cluster ID for '{cluster_name}'")
        else:
            raise RuntimeError(f"Failed to fetch clusters from Rancher: {resp.status_code} {resp.text}")
            
        self.cluster_url = f"{self.api_url}/k8s/clusters/{cluster_id}"
        
        configuration = client.Configuration()
        configuration.host = self.cluster_url
        configuration.api_key['authorization'] = f"Bearer {self.token}"
        configuration.verify_ssl = False
        
        self.api_client = client.ApiClient(configuration)
        self.core_v1 = client.CoreV1Api(self.api_client)
        self.apps_v1 = client.AppsV1Api(self.api_client)
        
        self.prom_manager = PrometheusManager(self.cluster_url, self.token)

    def _get_target_pod(self, namespace, pod_prefix):
        pods = self.core_v1.list_namespaced_pod(namespace)
        for pod in pods.items:
            if pod.metadata.name.startswith(pod_prefix) and pod.status.phase == 'Running':
                return pod.metadata.name
        raise RuntimeError(f"No active running pod found with prefix '{pod_prefix}' in namespace '{namespace}'")



    def wait_for_deployment_rollout(self, namespace, deployment_name, timeout_seconds=900):
        import time
        start_time = time.time()
        last_status = None
        reported_crashes = set()
        
        while time.time() - start_time < timeout_seconds:
            try:
                dep = self.apps_v1.read_namespaced_deployment(name=deployment_name, namespace=namespace)
                status = dep.status
                spec = dep.spec
                
                desired_replicas = spec.replicas if spec.replicas is not None else 1
                updated_replicas = status.updated_replicas or 0
                available_replicas = status.available_replicas or 0
                total_replicas = status.replicas or 0
                old_replicas = max(0, total_replicas - updated_replicas)
                
                if status.observed_generation and status.observed_generation < dep.metadata.generation:
                    current_status = f"Waiting for deployment spec update to be observed..."
                    if current_status != last_status:
                        yield current_status
                        last_status = current_status
                    time.sleep(5)
                    continue
                    
                label_selector = ",".join([f"{k}={v}" for k, v in spec.selector.match_labels.items()])
                pods = self.core_v1.list_namespaced_pod(namespace=namespace, label_selector=label_selector)
                
                terminating_pods = [p.metadata.name for p in pods.items if p.metadata.deletion_timestamp is not None]
                starting_pods = []
                crashed_pods = {}
                
                for pod in pods.items:
                    if pod.metadata.deletion_timestamp is not None:
                        continue
                        
                    is_ready = True
                    pod_reasons = []
                    if pod.status and pod.status.container_statuses:
                        for cs in pod.status.container_statuses:
                            if not cs.ready:
                                is_ready = False
                                if cs.state.waiting:
                                    pod_reasons.append(cs.state.waiting.reason)
                                elif cs.state.running:
                                    pod_reasons.append("Running (Not Ready)")
                            if cs.state.waiting and cs.state.waiting.reason in ['CrashLoopBackOff', 'Error', 'CreateContainerError']:
                                crashed_pods[pod.metadata.name] = pod.spec.node_name or "Unknown Node"
                                break
                            if cs.state.terminated and cs.state.terminated.exit_code != 0:
                                crashed_pods[pod.metadata.name] = pod.spec.node_name or "Unknown Node"
                                break
                    else:
                        is_ready = False
                        if pod.status and pod.status.phase:
                            pod_reasons.append(pod.status.phase)
                        
                    if not is_ready and pod.metadata.name not in crashed_pods:
                        reason_str = "/".join(set(pod_reasons)) if pod_reasons else "Pending"
                        starting_pods.append(f"{pod.metadata.name} [{reason_str}]")
                        
                if crashed_pods:
                    for crashed_pod, node_name in crashed_pods.items():
                        if crashed_pod not in reported_crashes:
                            yield f"Pod {crashed_pod} crashed on worker '{node_name}'! Fetching logs..."
                            try:
                                raw_logs = self.core_v1.read_namespaced_pod_log(name=crashed_pod, namespace=namespace, tail_lines=1000)
                                if isinstance(raw_logs, bytes):
                                    raw_logs = raw_logs.decode('utf-8', errors='replace')
                                    
                                log_lines = []
                                for line in raw_logs.splitlines():
                                    if line.startswith("b'") and line.endswith("'"):
                                        try:
                                            import ast
                                            parsed = ast.literal_eval(line)
                                            if isinstance(parsed, bytes):
                                                log_lines.extend(parsed.decode('utf-8', errors='replace').splitlines())
                                                continue
                                        except Exception:
                                            pass
                                    log_lines.append(line)
                                    
                                keywords = ['ERROR', 'TRACEBACK', 'EXCEPTION', 'FAILED', 'FATAL', 'CRITICAL']
                                error_lines = [line for line in log_lines if any(k in line.upper() for k in keywords)]
                                
                                if not error_lines:
                                    error_lines = log_lines[-30:]
                                    
                                error_text = '\n'.join(error_lines[-50:])
                                yield f"--- Relevant Crash Logs for {crashed_pod} ---\n{error_text}\n-----------------------"
                            except ApiException as e:
                                yield f"Could not fetch logs for {crashed_pod}: {e}"
                            
                            reported_crashes.add(crashed_pod)
                    
                status_lines = []
                is_rolled_out = False
                
                if updated_replicas < desired_replicas:
                    status_lines.append(f"Waiting for rollout to finish: {updated_replicas} out of {desired_replicas} new replicas have been updated...")
                elif old_replicas > 0:
                    status_lines.append(f"Waiting for rollout to finish: {old_replicas} old replicas are pending termination...")
                elif available_replicas < desired_replicas:
                    status_lines.append(f"Waiting for rollout to finish: {available_replicas} of {desired_replicas} updated replicas are starting and becoming available...")
                else:
                    is_rolled_out = True
                    
                if not is_rolled_out:
                    if terminating_pods:
                        status_lines.append(f"  -> Terminating: {', '.join(terminating_pods)}")
                    if starting_pods:
                        status_lines.append(f"  -> Starting/Not Ready: {', '.join(starting_pods)}")
                        
                    current_status = "\n".join(status_lines)
                    if current_status != last_status:
                        for line in status_lines:
                            yield line
                        last_status = current_status
                    else:
                        yield "."
                else:
                    yield f"Deployment {deployment_name} successfully rolled out."
                    try:
                        final_pods = self.core_v1.list_namespaced_pod(namespace=namespace, label_selector=label_selector)
                        for p in final_pods.items:
                            if p.status.phase == 'Running':
                                yield f" -> Pod {p.metadata.name} is running on Node: {p.spec.node_name}"
                    except Exception as e:
                        pass
                    return
                
            except ApiException as e:
                current_status = f"Error fetching deployment status: {e}"
                if current_status != last_status:
                    yield current_status
                    last_status = current_status
                else:
                    yield "."
                
            time.sleep(5)
            
        raise RuntimeError(f"Deployment {deployment_name} failed to rollout within {timeout_seconds} seconds.")



    def _find_drift(self, desired, live, path=""):
        drifts = []
        if isinstance(desired, dict) and isinstance(live, dict):
            for k, v in desired.items():
                if k not in live:
                    if v == {} or v == [] or v is None:
                        continue
                    
                    full_key = f"{path}.{k}" if path else k
                    if v in [0, False, ""]:
                        drifts.append(f"{full_key} is missing in cluster (Hint: K8s drops default values like 0 or false. Remove from YAML to fix this false-positive drift!)")
                    else:
                        drifts.append(f"{full_key} is missing in cluster")
                else:
                    drifts.extend(self._find_drift(v, live[k], path=f"{path}.{k}" if path else k))
        elif isinstance(desired, list) and isinstance(live, list):
            if len(desired) != len(live):
                drifts.append(f"{path} list length mismatch (desired: {len(desired)}, live: {len(live)})")
            else:
                for i, (d_val, l_val) in enumerate(zip(desired, live)):
                    drifts.extend(self._find_drift(d_val, l_val, path=f"{path}[{i}]"))
        else:
            if str(desired) != str(live):
                drifts.append(f"{path} mismatch: desired '{desired}' vs live '{live}'")
        return drifts

    def verify_manifest(self, raw_yaml_string, namespace='default'):
        docs = yaml.safe_load_all(raw_yaml_string)
        results = []
        for doc in docs:
            if not doc:
                continue
            kind = doc.get('kind')
            name = doc['metadata']['name']
            ns = doc['metadata'].get('namespace', namespace)
            
            logger.info(f"Verifying {kind} {name} in namespace {ns}")
            status = {
                'kind': kind,
                'name': name,
                'namespace': ns,
                'has_drift': False,
                'drifts': [],
                'active_pods': [],
                'exists': False,
                'live_state_json': ''
            }
            
            live_obj = None
            try:
                if kind == 'Deployment':
                    live_obj = self.apps_v1.read_namespaced_deployment(name, ns)
                    try:
                        labels = live_obj.spec.selector.match_labels or {}
                        if labels:
                            label_selector = ",".join([f"{k}={v}" for k, v in labels.items()])
                            pods = self.core_v1.list_namespaced_pod(ns, label_selector=label_selector)
                            status['active_pods'] = [pod.metadata.name for pod in pods.items if pod.status.phase == 'Running']
                    except Exception as e:
                        logger.warning(f"Failed to fetch pods for {name}: {e}")
                elif kind == 'Service':
                    live_obj = self.core_v1.read_namespaced_service(name, ns)
                elif kind == 'PersistentVolumeClaim':
                    live_obj = self.core_v1.read_namespaced_persistent_volume_claim(name, ns)
                elif kind == 'ConfigMap':
                    live_obj = self.core_v1.read_namespaced_config_map(name, ns)
                elif kind == 'Ingress':
                    net_v1 = client.NetworkingV1Api(self.api_client)
                    live_obj = net_v1.read_namespaced_ingress(name, ns)
                elif kind == 'NIMService':
                    custom_api = client.CustomObjectsApi(self.api_client)
                    group = "apps.nvidia.com"
                    version = "v1alpha1"
                    plural = "nimservices"
                    live_obj = custom_api.get_namespaced_custom_object(group, version, ns, plural, name)
                else:
                    status['drifts'].append(f"Unsupported kind {kind} for verification.")
                    results.append(status)
                    continue
                    
                status['exists'] = True
                live_dict = self.api_client.sanitize_for_serialization(live_obj)
                
                import json
                status['live_state_json'] = json.dumps(live_dict, indent=2)
                
                drifts = self._find_drift(doc, live_dict)
                if drifts:
                    status['has_drift'] = True
                    status['drifts'] = drifts
                    
            except ApiException as e:
                if e.status == 404:
                    status['exists'] = False
                    status['has_drift'] = True
                    status['drifts'] = ["Resource does not exist in the cluster."]
                else:
                    raise RuntimeError(f"Failed to verify {kind} {name}: {str(e)}")
            except Exception as e:
                raise RuntimeError(f"Failed to verify {kind} {name}: {str(e)}")
                
            results.append(status)
            
        return results

    def get_pvc_usage_bytes(self, namespace, pvc_name):
        b = self.prom_manager.get_pvc_usage_bytes(namespace, pvc_name)
        if b is None:
            return 'Unknown'
        for unit in ['B', 'Ki', 'Mi', 'Gi', 'Ti']:
            if b < 1024.0:
                return f"{b:.2f}{unit}"
            b /= 1024.0
        return f"{b:.2f}Pi"

    def search_volume(self, volume_name):
        matches = []
        seen_pvcs = set()
        
        def _add_match(ns, name, phase, capacity, pv_name):
            pvc_key = f"{ns}/{name}"
            if pvc_key not in seen_pvcs:
                active_pods = []
                try:
                    pods = self.core_v1.list_namespaced_pod(ns)
                    for pod in pods.items:
                        if pod.spec and pod.spec.volumes:
                            for vol in pod.spec.volumes:
                                if vol.persistent_volume_claim and vol.persistent_volume_claim.claim_name == name:
                                    active_pods.append(pod.metadata.name)
                                    break
                except Exception as e:
                    logger.warning(f"Could not list pods for pvc {name} in {ns}: {e}")
                
                used_size = self.get_pvc_usage_bytes(ns, name)
                
                matches.append({
                    'namespace': ns,
                    'name': name,
                    'phase': phase,
                    'active_pods': active_pods,
                    'capacity': capacity,
                    'used_size': used_size,
                    'pv_name': pv_name
                })
                seen_pvcs.add(pvc_key)

        try:
            pvcs = self.core_v1.list_persistent_volume_claim_for_all_namespaces()
            for pvc in pvcs.items:
                if (pvc.spec and pvc.spec.volume_name and volume_name in pvc.spec.volume_name) or \
                   (pvc.metadata and pvc.metadata.name and volume_name in pvc.metadata.name):
                    cap = pvc.status.capacity.get('storage', 'Unknown') if pvc.status and pvc.status.capacity else 'Unknown'
                    pv_n = pvc.spec.volume_name if pvc.spec else 'Unknown'
                    _add_match(pvc.metadata.namespace, pvc.metadata.name, pvc.status.phase if pvc.status else 'Unknown', cap, pv_n)

            pvs = self.core_v1.list_persistent_volume()
            for pv in pvs.items:
                pv_dict = self.api_client.sanitize_for_serialization(pv)
                if volume_name in str(pv_dict):
                    if pv.spec and pv.spec.claim_ref:
                        cap = pv.spec.capacity.get('storage', 'Unknown') if pv.spec and pv.spec.capacity else 'Unknown'
                        _add_match(pv.spec.claim_ref.namespace, pv.spec.claim_ref.name, pv.status.phase if pv.status else 'Unknown', cap, pv.metadata.name)
                        
        except Exception as e:
            logger.error(f"Failed to search volumes: {e}")
        
        return matches

    def scan_volumes(self, usage_threshold_pct=0.0):
        matches = []
        
        def _parse_to_bytes(size_str):
            import re
            match = re.match(r'^(\d+)(Ki|Mi|Gi|Ti|Pi)$', size_str)
            if not match: return None
            val = int(match.group(1))
            unit = match.group(2)
            multipliers = {'Ki': 1024, 'Mi': 1024**2, 'Gi': 1024**3, 'Ti': 1024**4, 'Pi': 1024**5}
            return val * multipliers.get(unit, 1)

        try:
            bulk_usage = self.prom_manager.get_all_pvc_usage_bytes()
            
            pvcs = self.core_v1.list_persistent_volume_claim_for_all_namespaces()
            for pvc in pvcs.items:
                ns = pvc.metadata.namespace
                name = pvc.metadata.name
                phase = pvc.status.phase if pvc.status else 'Unknown'
                cap_str = pvc.status.capacity.get('storage', 'Unknown') if pvc.status and pvc.status.capacity else 'Unknown'
                pv_name = pvc.spec.volume_name if pvc.spec else 'Unknown'
                
                used_bytes = bulk_usage.get((ns, name), 0.0)
                used_str = 'Unknown'
                
                if (ns, name) in bulk_usage:
                    b = used_bytes
                    for unit in ['B', 'Ki', 'Mi', 'Gi', 'Ti']:
                        if b < 1024.0:
                            used_str = f"{b:.2f}{unit}"
                            break
                        b /= 1024.0
                    if used_str == 'Unknown':
                        used_str = f"{b:.2f}Pi"

                pct = 0.0
                cap_bytes = _parse_to_bytes(cap_str) if cap_str != 'Unknown' else None
                if cap_bytes and cap_bytes > 0:
                    pct = (used_bytes / cap_bytes) * 100.0

                if pct >= usage_threshold_pct:
                    active_pods = []
                    try:
                        pods = self.core_v1.list_namespaced_pod(ns)
                        for pod in pods.items:
                            if pod.spec and pod.spec.volumes:
                                for vol in pod.spec.volumes:
                                    if vol.persistent_volume_claim and vol.persistent_volume_claim.claim_name == name:
                                        active_pods.append(pod.metadata.name)
                                        break
                    except Exception:
                        pass

                    matches.append({
                        'namespace': ns,
                        'name': name,
                        'phase': phase,
                        'capacity': cap_str,
                        'used_size': used_str,
                        'pv_name': pv_name,
                        'active_pods': active_pods,
                        'usage_percentage': pct
                    })
        except Exception as e:
            logger.error(f"Error scanning volumes: {e}")
        return matches

    def expand_volume(self, namespace, pvc_name, new_size):
        try:
            pvc = self.core_v1.read_namespaced_persistent_volume_claim(pvc_name, namespace)
            if not pvc:
                return False, f"PVC '{pvc_name}' not found in namespace '{namespace}'"
            
            if new_size == 'auto':
                current_size_str = pvc.status.capacity.get('storage') if pvc.status and pvc.status.capacity else None
                if not current_size_str and pvc.spec.resources.requests:
                    current_size_str = pvc.spec.resources.requests.get('storage')
                    
                if not current_size_str:
                    return False, "Could not determine current PVC size for auto-expansion."
                
                import re
                match = re.match(r'^(\d+)(Gi|Mi|Ti)$', current_size_str)
                if not match:
                    return False, f"Unsupported storage unit for auto-expansion: {current_size_str}"
                    
                val = int(match.group(1))
                unit = match.group(2)
                
                if unit == 'Gi':
                    if val < 100:
                        new_val = val + 5
                    else:
                        new_val = int(val * 1.1)
                    new_size = f"{new_val}Gi"
                elif unit == 'Ti':
                    new_val = int(val * 1.1)
                    new_size = f"{new_val}Ti"
                else:
                    return False, f"Auto-expand only supports Gi/Ti units, got {unit}."

            if not pvc.spec.resources.requests:
                pvc.spec.resources.requests = {}
            
            pvc.spec.resources.requests['storage'] = new_size
            self.core_v1.patch_namespaced_persistent_volume_claim(pvc_name, namespace, pvc)
            
            return True, f"Successfully requested expansion of PVC '{pvc_name}' to '{new_size}'"
        except ApiException as e:
            logger.error(f"Kubernetes API error expanding PVC: {e}")
            return False, f"Kubernetes API error: {e.reason} - {e.body}"
        except Exception as e:
            logger.error(f"Failed to expand volume '{pvc_name}': {e}")
            return False, f"Error: {str(e)}"