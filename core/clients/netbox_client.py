import requests
import urllib3
import logging

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)

class NetboxClient:
    def __init__(self, url: str, token: str, verify_ssl: bool = False):
        self.url = url.rstrip('/')
        self.token = token
        self.verify_ssl = verify_ssl
        self.headers = {
            "Authorization": f"Token {self.token}",
            "Accept": "application/json"
        }

    def _paginate(self, endpoint: str, params: dict):
        results = []
        url = f"{self.url}{endpoint}"
        
        # We need to ensure limit is set, otherwise Netbox defaults to 50
        if params is None:
            params = {}
        if 'limit' not in params:
            params['limit'] = 100
            
        current_params = params
        
        while url:
            res = requests.get(url, headers=self.headers, verify=self.verify_ssl, params=current_params)
            if res.status_code == 200:
                data = res.json()
                results.extend(data.get("results", []))
                url = data.get("next")
                current_params = None  # 'next' URL already contains all parameters including limit/offset
            else:
                logger.error(f"Failed to fetch {endpoint}: {res.status_code} - {res.text}")
                break
        return results

    def get_vms(self, search_query: str = None, tenant: str = None, **kwargs):
        try:
            params = {}
            if search_query:
                params['q'] = search_query
            if tenant:
                params['tenant'] = tenant
            params.update(kwargs)
            
            return self._paginate("/api/virtualization/virtual-machines/", params)
        except Exception as e:
            logger.error(f"Failed to fetch VMs: {e}")
            raise Exception(f"Failed to fetch VMs: {e}")

    def get_devices(self, search_query: str = None, tenant: str = None, **kwargs):
        try:
            params = {}
            if search_query:
                params['q'] = search_query
            if tenant:
                params['tenant'] = tenant
            params.update(kwargs)
                
            return self._paginate("/api/dcim/devices/", params)
        except Exception as e:
            logger.error(f"Failed to fetch Devices: {e}")
            raise Exception(f"Failed to fetch Devices: {e}")

    def get_ips(self, tenant: str = None, **kwargs):
        try:
            params = {}
            if tenant:
                params['tenant'] = tenant
            params.update(kwargs)
            
            return self._paginate("/api/ipam/ip-addresses/", params)
        except Exception as e:
            logger.error(f"Failed to fetch IP Addresses: {e}")
            raise Exception(f"Failed to fetch IP Addresses: {e}")

    def get_device_interfaces(self, device_ids: list):
        results = []
        chunk_size = 50
        for i in range(0, len(device_ids), chunk_size):
            chunk = device_ids[i:i + chunk_size]
            params = [("device_id", str(did)) for did in chunk]
            try:
                # _paginate doesn't inherently handle list of tuples for params cleanly if we append 'limit' later
                # We can just manually paginate or adjust params
                params.append(("limit", "100"))
                url = f"{self.url}/api/dcim/interfaces/"
                while url:
                    res = requests.get(url, headers=self.headers, verify=self.verify_ssl, params=params)
                    if res.status_code == 200:
                        data = res.json()
                        results.extend(data.get("results", []))
                        url = data.get("next")
                        params = None  # next url has all params
                    else:
                        logger.error(f"Failed to fetch device interfaces: {res.status_code}")
                        break
            except Exception as e:
                logger.error(f"Failed to fetch device interfaces chunk: {e}")
        return results

    def get_vm_interfaces(self, vm_ids: list):
        results = []
        chunk_size = 50
        for i in range(0, len(vm_ids), chunk_size):
            chunk = vm_ids[i:i + chunk_size]
            params = [("virtual_machine_id", str(vid)) for vid in chunk]
            try:
                params.append(("limit", "100"))
                url = f"{self.url}/api/virtualization/interfaces/"
                while url:
                    res = requests.get(url, headers=self.headers, verify=self.verify_ssl, params=params)
                    if res.status_code == 200:
                        data = res.json()
                        results.extend(data.get("results", []))
                        url = data.get("next")
                        params = None
                    else:
                        logger.error(f"Failed to fetch vm interfaces: {res.status_code}")
                        break
            except Exception as e:
                logger.error(f"Failed to fetch vm interfaces chunk: {e}")
        return results

    def get_device_ips(self, device_ids: list):
        results = []
        chunk_size = 50
        for i in range(0, len(device_ids), chunk_size):
            chunk = device_ids[i:i + chunk_size]
            params = [("device_id", str(did)) for did in chunk]
            try:
                params.append(("limit", "100"))
                url = f"{self.url}/api/ipam/ip-addresses/"
                while url:
                    res = requests.get(url, headers=self.headers, verify=self.verify_ssl, params=params)
                    if res.status_code == 200:
                        data = res.json()
                        results.extend(data.get("results", []))
                        url = data.get("next")
                        params = None
                    else:
                        logger.error(f"Failed to fetch device IPs: {res.status_code}")
                        break
            except Exception as e:
                logger.error(f"Failed to fetch device IPs chunk: {e}")
        return results

    def get_vm_ips(self, vm_ids: list):
        results = []
        chunk_size = 50
        for i in range(0, len(vm_ids), chunk_size):
            chunk = vm_ids[i:i + chunk_size]
            params = [("virtual_machine_id", str(vid)) for vid in chunk]
            try:
                params.append(("limit", "100"))
                url = f"{self.url}/api/ipam/ip-addresses/"
                while url:
                    res = requests.get(url, headers=self.headers, verify=self.verify_ssl, params=params)
                    if res.status_code == 200:
                        data = res.json()
                        results.extend(data.get("results", []))
                        url = data.get("next")
                        params = None
                    else:
                        logger.error(f"Failed to fetch VM IPs: {res.status_code}")
                        break
            except Exception as e:
                logger.error(f"Failed to fetch VM IPs chunk: {e}")
        return results

