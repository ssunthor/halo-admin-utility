import requests
import logging

logger = logging.getLogger(__name__)

class PrometheusManager:
    def __init__(self, cluster_url, token):
        self.cluster_url = cluster_url
        self.token = token
        self.prom_base_url = f"{self.cluster_url}/api/v1/namespaces/cattle-monitoring-system/services/http:rancher-monitoring-prometheus:9090/proxy/api/v1/query"

    def get_pvc_usage_bytes(self, namespace, pvc_name) -> float:
        promql = f'kubelet_volume_stats_used_bytes{{namespace="{namespace}", persistentvolumeclaim="{pvc_name}"}}'
        try:
            resp = requests.get(
                self.prom_base_url,
                params={'query': promql},
                headers={'Authorization': f"Bearer {self.token}"},
                verify=False,
                timeout=5
            )
            if resp.status_code == 200:
                data = resp.json().get('data', {}).get('result', [])
                if data:
                    return float(data[0].get('value', [None, "0"])[1])
        except Exception as e:
            logger.warning(f"Could not fetch usage from Prometheus for {namespace}/{pvc_name}: {e}")
        return None

    def get_all_pvc_usage_bytes(self) -> dict:
        promql = 'kubelet_volume_stats_used_bytes'
        results = {}
        try:
            resp = requests.get(
                self.prom_base_url,
                params={'query': promql},
                headers={'Authorization': f"Bearer {self.token}"},
                verify=False,
                timeout=5
            )
            if resp.status_code == 200:
                data = resp.json().get('data', {}).get('result', [])
                for item in data:
                    metric = item.get('metric', {})
                    ns = metric.get('namespace')
                    pvc = metric.get('persistentvolumeclaim')
                    val = item.get('value', [None, "0"])[1]
                    if ns and pvc:
                        results[(ns, pvc)] = float(val)
        except Exception as e:
            logger.warning(f"Could not fetch bulk PVC usage from Prometheus: {e}")
        return results