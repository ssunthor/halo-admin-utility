import hvac
import logging
import requests

logger = logging.getLogger(__name__)

class VaultClient:
    def __init__(self, config):
        self.url = config.get('url')
        self.role_id = config.get('role_id')
        self.secret_id = config.get('secret_id')
        self.verify = config.get('verify_ssl', False)
        
        if not self.verify:
            import urllib3
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            
        session = requests.Session()
        session.proxies = {"http": None, "https": None}
        session.verify = self.verify

        self.client = self._authenticate(session)
        self._secret_cache = {}

    def _authenticate(self, session):
        try:
            client = hvac.Client(url=self.url, verify=self.verify, session=session)
            client.auth.approle.login(role_id=self.role_id, secret_id=self.secret_id)
            if not client.is_authenticated():
                raise PermissionError("Failed to authenticate with Vault via AppRole.")
            logger.info("Successfully authenticated with Vault.")
            return client
        except Exception as e:
            logger.error(f"Vault authentication failed: {e}")
            raise

    def get_secret(self, path: str, mount_point: str = "secret") -> dict:
        """Fetch secret data from Vault KV v2."""
        cache_key = f"{mount_point}:{path}"
        if cache_key in self._secret_cache:
            return self._secret_cache[cache_key]

        try:
            response = self.client.secrets.kv.v2.read_secret_version(
                mount_point=mount_point,
                path=path
            )
            data = response.get('data', {}).get('data', {})
            self._secret_cache[cache_key] = data
            return data
        except Exception as e:
            logger.error(f"Failed to fetch secret from Vault at '{mount_point}/{path}': {e}")
            raise

    def get_netbox_token(self, path: str = "netbox/external/shared/gia_ai", mount_point: str = "secret") -> str:
        """Fetch NetBox API token from Vault."""
        data = self.get_secret(path, mount_point=mount_point)
        token = data.get('token')
        if not token:
            raise ValueError(f"Vault secret at '{mount_point}/{path}' does not contain 'token'")
        return token

    def get_rancher_tokens(self, path_template, locations, mount_point="secret"):
        """Fetches the Rancher tokens for clusters across multiple locations dynamically."""
        clusters_data = {}
        for loc in locations:
            path = path_template.format(loc=loc)
            try:
                response = self.client.secrets.kv.v2.read_secret_version(
                    mount_point=mount_point, 
                    path=path
                )
                clusters_data[loc] = response['data']['data']
            except Exception as e:
                pass
        return clusters_data