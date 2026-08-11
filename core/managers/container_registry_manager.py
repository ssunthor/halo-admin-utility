import requests
import time
from urllib.parse import urlparse
import logging

logger = logging.getLogger(__name__)

class ContainerRegistryManager:
    def __init__(self, config):
        self.config = config
        if 'external_services' in self.config and 'gitlab' in self.config['external_services']:
            self.url = self.config['external_services']['gitlab'].get('url')
            self.token = self.config['external_services']['gitlab'].get('bot_token')
        else:
            self.url = None
            self.token = None

    def retag_container(self, project_path, old_tag, new_tag):
        if not self.url or not self.token:
            return False, "GitLab config with URL and token is missing."

        auth_url = f"{self.url.rstrip('/')}/jwt/auth"
        service = "container_registry"
        scope = f"repository:{project_path}:pull,push"
        
        token_res = requests.get(
            auth_url,
            params={"service": service, "scope": scope},
            auth=("__token__", self.token),
            verify=False
        )
        if token_res.status_code != 200:
            return False, f"Failed to authenticate with registry: {token_res.text}"
            
        token = token_res.json().get("token")
        
        parsed_url = urlparse(self.url)
        registry_url = f"https://{parsed_url.netloc}:4567"
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.docker.distribution.manifest.v2+json, application/vnd.oci.image.manifest.v1+json"
        }
        
        manifest_url = f"{registry_url}/v2/{project_path.lower()}/manifests/{old_tag}"
        res = None
        for attempt in range(12):
            res = requests.get(manifest_url, headers=headers, verify=False)
            if res.status_code == 200:
                break
            time.sleep(5)
        else:
            return False, f"Failed to get manifest for {old_tag}: {res.status_code if res else 'Unknown'} - {res.text if res else 'Timeout'}"
            
        manifest = res.text
        content_type = res.headers.get("Content-Type")
        
        put_headers = headers.copy()
        put_headers["Content-Type"] = content_type
        
        put_url = f"{registry_url}/v2/{project_path.lower()}/manifests/{new_tag}"
        put_res = requests.put(put_url, headers=put_headers, data=manifest, verify=False)
        
        if put_res.status_code in [201, 202]:
            return True, f"Successfully retagged container image '{old_tag}' to '{new_tag}'"
        else:
            return False, f"Failed to push new tag {new_tag}: {put_res.status_code} - {put_res.text}"

    def delete_container_tag(self, project_path, tag_name):
        if not self.url or not self.token:
            return False, "GitLab config with URL and token is missing."
        
        import gitlab
        try:
            gl = gitlab.Gitlab(self.url, private_token=self.token, ssl_verify=False)
            project = gl.projects.get(project_path)
            repos = project.repositories.list(get_all=True)
            if not repos:
                return False, f"No container repositories found for project '{project_path}'."
                
            deleted = False
            for repo in repos:
                try:
                    repo.tags.delete(tag_name)
                    deleted = True
                except gitlab.exceptions.GitlabDeleteError as e:
                    if e.response_code not in (403, 404):
                        return False, f"Failed to delete tag '{tag_name}' in repository {repo.id}: {e}"
                except Exception as e:
                    return False, f"Error deleting tag '{tag_name}' in repository {repo.id}: {e}"
                    
            if deleted:
                return True, f"Successfully deleted container tag '{tag_name}'."
            else:
                return True, f"Container tag '{tag_name}' not found (or already deleted)."
        except Exception as e:
            return False, f"Failed to access GitLab for project '{project_path}': {e}"