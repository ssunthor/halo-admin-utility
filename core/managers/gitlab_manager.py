import gitlab
import base64
import os
import subprocess
import logging
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)

class GitlabManager:
    def __init__(self, config):
        self.config = config
        self.url = self.config['url']
        self.token = self.config.get('bot_token')

    def fetch_raw_yaml(self, project_path, file_path, branch='main'):
        token = self.token
        
        try:
            gl = gitlab.Gitlab(self.url, private_token=token, ssl_verify=False)
            project = gl.projects.get(project_path)
            f = project.files.get(file_path=file_path, ref=branch)
            
            return base64.b64decode(f.content).decode('utf-8')
        except Exception as e:
            raise RuntimeError(f"Failed to fetch {file_path} via API: {e}")

    def fetch_repository_tree(self, project_path, path=''):
        token = self.token
        
        try:
            import json
            gl = gitlab.Gitlab(self.url, private_token=token, ssl_verify=False)
            project = gl.projects.get(project_path)
            tree = project.repository_tree(path=path, ref='main', recursive=True, get_all=True)
            tree_data = [item.attributes if hasattr(item, 'attributes') else item for item in tree]
            return json.dumps(tree_data)
        except Exception as e:
            raise RuntimeError(f"Failed to fetch repository tree via API: {e}")

    def fetch_documentation(self, project_name):
        gl = gitlab.Gitlab(self.url, private_token=self.token, ssl_verify=False)
        project_client = gl.projects.get("ai/halo/deployment")
        
        doc_path = f"docs/{project_name}"
        
        try:
            tree = project_client.repository_tree(path=doc_path, ref='main')
        except gitlab.exceptions.GitlabGetError as e:
            if e.response_code == 404:
                normalized_project = project_name.lower().replace(" ", "-")
                doc_path = f"docs/{normalized_project}"
                tree = project_client.repository_tree(path=doc_path, ref='main')
            else:
                raise e

        docs = {}
        for item in tree:
            if item['type'] == 'blob' and item['name'].endswith('.md'):
                f = project_client.files.get(file_path=item['path'], ref='main')
                docs[item['name']] = base64.b64decode(f.content).decode('utf-8')
        
        return docs

    def sync_local_repo(self, project_path, local_path):
        token = self.token
        
        domain = self.url.replace('https://', '').replace('http://', '')
        repo_url = f"https://oauth2:{token}@{domain}/{project_path}.git"

        os.makedirs(os.path.dirname(local_path), exist_ok=True)

        if not os.path.exists(os.path.join(local_path, '.git')):
            logger.info(f"Cloning {project_path} into {local_path} (shallow)...")
            result = subprocess.run(['git', 'clone', '--depth', '1', repo_url, local_path], capture_output=True, text=True)
            if result.returncode != 0:
                raise RuntimeError(f"Git clone failed with exit code {result.returncode}\n{result.stderr}")
            output = (result.stdout + "\n" + result.stderr).strip()
            return f"Successfully cloned {project_path} to {local_path}.\n{output}"
        else:
            logger.info(f"Pulling latest changes for {project_path} in {local_path} (shallow)...")
            subprocess.run(['git', 'remote', 'set-url', 'origin', repo_url], cwd=local_path)
            
            result = subprocess.run(['git', 'pull', '--depth', '1', 'origin', 'main'], cwd=local_path, capture_output=True, text=True)
            if result.returncode != 0:
                raise RuntimeError(f"Git pull failed with exit code {result.returncode}\n{result.stderr}")
            output = (result.stdout + "\n" + result.stderr).strip()
            return f"Successfully pulled latest changes for {project_path} in {local_path}.\n{output}"

    def sync_group_cache(self, branch_override=None):
        token = self.config.get('bot_token')
        project_path = self.config.get('project_path')
        local_path = self.config.get('local_clone_path')
        
        domain = self.url.replace('https://', '').replace('http://', '')
        
        gl = gitlab.Gitlab(self.url, private_token=token, ssl_verify=False)
        group = gl.groups.get(project_path)
        projects = group.projects.list(include_subgroups=True, all=True)
        
        os.makedirs(local_path, exist_ok=True)
        
        import concurrent.futures
        
        def sync_project(p):
            repo_url = f"https://oauth2:{token}@{domain}/{p.path_with_namespace}.git"
            
            rel_path = p.path_with_namespace
            if rel_path.startswith(project_path + "/"):
                rel_path = rel_path[len(project_path) + 1:]
                
            repo_local_path = os.path.join(local_path, rel_path)
            
            target_pref = branch_override if branch_override else 'dev'
            if not os.path.exists(os.path.join(repo_local_path, '.git')):
                ls_remote = subprocess.run(['git', 'ls-remote', '--heads', repo_url, target_pref], capture_output=True, text=True)
                if ls_remote.stdout.strip():
                    target_branch = target_pref
                else:
                    target_branch = p.default_branch or 'main'
                    
                os.makedirs(os.path.dirname(repo_local_path), exist_ok=True)
                logger.info(f"Cloning {p.path_with_namespace} (branch: {target_branch}) into {repo_local_path}...")
                result = subprocess.run(['git', 'clone', '-b', target_branch, repo_url, repo_local_path], capture_output=True, text=True)
                if result.returncode != 0:
                    return f"❌ Failed to clone {p.name}: {result.stderr.strip()}"
                else:
                    return f"✅ Cloned {p.path_with_namespace} (branch: {target_branch})"
            else:
                subprocess.run(['git', 'remote', 'set-url', 'origin', repo_url], cwd=repo_local_path)
                subprocess.run(['git', 'fetch', 'origin'], cwd=repo_local_path, capture_output=True)
                
                # Pre-clean working directory to avoid checkout errors
                subprocess.run(['git', 'reset', '--hard'], cwd=repo_local_path, capture_output=True)
                subprocess.run(['git', 'clean', '-fd'], cwd=repo_local_path, capture_output=True)
                
                if branch_override:
                    res = subprocess.run(['git', 'rev-parse', '--verify', f'origin/{branch_override}'], cwd=repo_local_path, capture_output=True)
                    if res.returncode == 0:
                        active_branch = branch_override
                    else:
                        active_branch = p.default_branch or 'main'
                    subprocess.run(['git', 'checkout', active_branch], cwd=repo_local_path, capture_output=True)
                else:
                    curr_res = subprocess.run(['git', 'branch', '--show-current'], cwd=repo_local_path, capture_output=True, text=True)
                    active_branch = curr_res.stdout.strip()
                    if not active_branch:
                        active_branch = p.default_branch or 'main'
                        subprocess.run(['git', 'checkout', active_branch], cwd=repo_local_path, capture_output=True)
                
                logger.info(f"Syncing {p.path_with_namespace} in {repo_local_path} (branch: {active_branch})...")
                # Hard reset to remote and clean untracked files to ensure pristine cache state
                result = subprocess.run(['git', 'reset', '--hard', f'origin/{active_branch}'], cwd=repo_local_path, capture_output=True, text=True)
                subprocess.run(['git', 'clean', '-fd'], cwd=repo_local_path, capture_output=True)
                
                if result.returncode != 0:
                    return f"❌ Failed to sync {p.path_with_namespace} (branch: {active_branch}): {result.stderr.strip()}"
                else:
                    return f"✅ Synced {p.path_with_namespace} (branch: {active_branch})"

        logs = []
        if projects:
            with concurrent.futures.ThreadPoolExecutor(max_workers=min(20, len(projects))) as executor:
                future_to_project = {executor.submit(sync_project, p): p for p in projects}
                for future in concurrent.futures.as_completed(future_to_project):
                    try:
                        logs.append(future.result())
                    except Exception as e:
                        p = future_to_project[future]
                        logs.append(f"❌ Unhandled exception on {p.path_with_namespace}: {str(e)}")
        
        return "\n".join(logs)
        
    def list_group_cache(self):
        local_path = self.config.get('local_clone_path')
        if not local_path or not os.path.exists(local_path):
            return "Cache directory does not exist. Run sync first."
            
        token = self.config.get('bot_token')
        project_path = self.config.get('project_path')
        domain = self.url.replace('https://', '').replace('http://', '')
        gl = gitlab.Gitlab(self.url, private_token=token, ssl_verify=False)
        group = gl.groups.get(project_path)
        projects = {p.path_with_namespace: p for p in group.projects.list(include_subgroups=True, all=True)}
            
        output = []
        for root, dirs, files in os.walk(local_path):
            if '.git' in dirs:
                dirs.remove('.git')
                repo_dir = root
                
                rel_dir = os.path.relpath(repo_dir, local_path)
                full_project_path = f"{project_path}/{rel_dir}" if rel_dir != "." else project_path
                
                curr_res = subprocess.run(['git', 'branch', '--show-current'], cwd=repo_dir, capture_output=True, text=True)
                active_branch = curr_res.stdout.strip()
                
                repo_url = f"https://oauth2:{token}@{domain}/{full_project_path}.git" if full_project_path in projects else None
                if repo_url:
                    subprocess.run(['git', 'remote', 'set-url', 'origin', repo_url], cwd=repo_dir, capture_output=True)
                subprocess.run(['git', 'fetch', 'origin'], cwd=repo_dir, capture_output=True)
                
                branch_res = subprocess.run(['git', 'branch', '-r'], cwd=repo_dir, capture_output=True, text=True)
                branches = [b.strip().replace('origin/', '') for b in branch_res.stdout.split('\n') if b.strip() and '->' not in b]
                branches = sorted(list(set(branches)))
                
                default_branch = projects[full_project_path].default_branch if full_project_path in projects else 'main'
                
                protected_branches = []
                if full_project_path in projects:
                    try:
                        p = projects[full_project_path]
                        real_p = gl.projects.get(p.id, lazy=True)
                        protected_branches = [pb.name for pb in real_p.protectedbranches.list()]
                    except Exception as e:
                        pass
                
                repo_data = {
                    "repository": full_project_path,
                    "active_branch": active_branch,
                    "default_branch": default_branch,
                    "branches": branches,
                    "protected_branches": protected_branches
                }
                output.append(repo_data)
                
        import json
        return json.dumps(output)

    def checkout_project_branch(self, project_name, branch_name):
        local_path = self.config.get('local_clone_path')
        if not local_path:
            raise RuntimeError("local_clone_path is not defined in configuration.")
            
        project_path = self.config.get('project_path')
        rel_path = project_name
        if rel_path.startswith(project_path + "/"):
            rel_path = rel_path[len(project_path) + 1:]
            
        repo_dir = os.path.join(local_path, rel_path)
        if not os.path.exists(os.path.join(repo_dir, '.git')):
            raise RuntimeError(f"Project '{project_name}' is not cloned locally. Run sync first.")
            
        subprocess.run(['git', 'fetch', 'origin'], cwd=repo_dir, capture_output=True)
        subprocess.run(['git', 'reset', '--hard', 'HEAD'], cwd=repo_dir, capture_output=True)
        subprocess.run(['git', 'clean', '-fd'], cwd=repo_dir, capture_output=True)
        result = subprocess.run(['git', 'checkout', branch_name], cwd=repo_dir, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"Failed to checkout branch '{branch_name}' for '{project_name}': {result.stderr}")
            
        pull_result = subprocess.run(['git', 'pull', 'origin', branch_name], cwd=repo_dir, capture_output=True, text=True)
        return f"Successfully checked out and pulled '{branch_name}' for '{project_name}'\n{pull_result.stdout.strip()}"

    def push_group_cache(self, commit_msg):
        local_path = self.config.get('local_clone_path')
        if not local_path or not os.path.exists(local_path):
            raise RuntimeError("Cache directory does not exist. Run sync first.")
            
        author_name = self.config.get('bot_username', 'GIA AI Bot')
        author_email = "gia-ai@gtt.net"
            
        logs = []
        for root, dirs, files in os.walk(local_path):
            if '.git' in dirs:
                dirs.remove('.git')
                repo_dir = root
                rel_dir = os.path.relpath(repo_dir, local_path)
                
                status_res = subprocess.run(['git', 'status', '--porcelain'], cwd=repo_dir, capture_output=True, text=True)
                if status_res.stdout.strip():
                    subprocess.run(['git', 'config', 'user.name', author_name], cwd=repo_dir)
                    subprocess.run(['git', 'config', 'user.email', author_email], cwd=repo_dir)
                    subprocess.run(['git', 'add', '.'], cwd=repo_dir)
                    
                    commit_res = subprocess.run(['git', 'commit', '-m', commit_msg], cwd=repo_dir, capture_output=True, text=True)
                    if commit_res.returncode != 0:
                        logs.append(f"❌ Failed to commit {rel_dir}: {commit_res.stderr.strip()}")
                        continue
                        
                    curr_res = subprocess.run(['git', 'branch', '--show-current'], cwd=repo_dir, capture_output=True, text=True)
                    active_branch = curr_res.stdout.strip()
                    
                    push_res = subprocess.run(['git', 'push', 'origin', active_branch], cwd=repo_dir, capture_output=True, text=True)
                    if push_res.returncode != 0:
                        logs.append(f"❌ Failed to push {rel_dir} (branch: {active_branch}): {push_res.stderr.strip()}")
                    else:
                        logs.append(f"✅ Pushed {rel_dir} (branch: {active_branch})")
                else:
                    logs.append(f"ℹ️ No changes in {rel_dir}")
                    
        return "\n".join(logs)

    def commit_file_api(self, project_path, file_path, branch, content, commit_msg, author_name=None, author_email=None):
        gl = gitlab.Gitlab(self.url, private_token=self.token, ssl_verify=False)
        project = gl.projects.get(project_path)
        
        data = {
            'branch': branch,
            'commit_message': commit_msg,
            'actions': [
                {
                    'action': 'update',
                    'file_path': file_path,
                    'content': content
                }
            ]
        }
        if author_name:
            data['author_name'] = author_name
        if author_email:
            data['author_email'] = author_email
        
        try:
            project.commits.create(data)
        except gitlab.exceptions.GitlabCreateError as e:
            if "A file with this name doesn't exist" in str(e):
                data['actions'][0]['action'] = 'create'
                project.commits.create(data)
            else:
                raise e
        return f"Successfully committed {file_path} to {branch} via API."

    def delete_branch(self, project_path, branch_name):
        gl = gitlab.Gitlab(self.url, private_token=self.token, ssl_verify=False)
        try:
            project = gl.projects.get(project_path)
            project.branches.delete(branch_name)
            return True, f"Successfully deleted branch '{branch_name}'."
        except gitlab.exceptions.GitlabDeleteError as e:
            if e.response_code == 404:
                return True, f"Branch '{branch_name}' does not exist (or already deleted)."
            return False, f"Failed to delete branch '{branch_name}': {e}"
        except Exception as e:
            return False, f"Failed to delete branch '{branch_name}': {e}"

    def create_tag(self, project_path, tag_name, ref):
        gl = gitlab.Gitlab(self.url, private_token=self.token, ssl_verify=False)
        project = gl.projects.get(project_path)
        
        try:
            tag = project.tags.create({'tag_name': tag_name, 'ref': ref})
            return True, f"Successfully created tag {tag.name} from {ref}."
        except Exception as e:
            return False, f"Failed to create tag: {str(e)}"

    def create_release(self, project_path, tag_name, description):
        gl = gitlab.Gitlab(self.url, private_token=self.token, ssl_verify=False)
        project = gl.projects.get(project_path)
        
        try:
            release = project.releases.create({
                'name': f'Release {tag_name}',
                'tag_name': tag_name,
                'description': description
            })
            return True, f"Successfully created GitLab Release for {tag_name}."
        except Exception as e:
            return False, f"Failed to create GitLab Release: {str(e)}"

    def resolve_user(self, project_path, search_str):
        token = self.token
        try:
            gl = gitlab.Gitlab(self.url, private_token=token, ssl_verify=False)
            project = gl.projects.get(project_path)
            
            members = project.members_all.list(all=True)
            search_lower = search_str.lower()
            matched_member = None
            
            search_normalized = search_lower.replace('.', ' ')
            for m in members:
                username = getattr(m, 'username', '').lower()
                name = getattr(m, 'name', '').lower()
                
                name_normalized = name.replace('.', ' ')
                username_normalized = username.replace('.', ' ')
                
                if search_normalized in username_normalized or search_normalized in name_normalized:
                    matched_member = m
                    break
                    
            if not matched_member:
                users = gl.users.list(search=search_str)
                if users:
                    matched_member = users[0]
                    
            if matched_member:
                raw_name = matched_member.name
                if '@' in raw_name:
                    parts = raw_name.split('@')[0].split('.')
                    formatted_name = ' '.join(p.capitalize() for p in parts)
                else:
                    formatted_name = raw_name
                    
                fallback_email = f"{formatted_name.lower().replace(' ', '.')}@gtt.net"
                return {
                    'id': matched_member.id,
                    'name': formatted_name,
                    'username': matched_member.username,
                    'email': getattr(matched_member, 'email', fallback_email)
                }
            return None
        except Exception as e:
            logger.error(f"Failed to resolve user '{search_str}' in {project_path}: {e}")
            return None