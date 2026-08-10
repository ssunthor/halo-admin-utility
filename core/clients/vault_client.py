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

    def get_rancher_tokens(self, path="rancher/system/gia_ai", mount_point="secret"):
        """Fetches the Rancher tokens for clusters."""
        try:
            response = self.client.secrets.kv.v2.read_secret_version(
                mount_point=mount_point, 
                path=path
            )
            data = response['data']['data']
            
            if 'clusters' not in data:
                raise KeyError(f"Key 'clusters' not found at Vault path '{path}'")
                
            logger.debug(f"Successfully retrieved Rancher tokens from Vault.")
            return data.get('clusters')
        except hvac.exceptions.InvalidPath:
            logger.error(f"Vault path '{mount_point}/{path}' does not exist.")
            raise
        except Exception as e:
            logger.error(f"Error retrieving Rancher tokens from Vault: {e}")
            raise