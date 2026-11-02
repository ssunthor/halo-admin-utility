import gitlab
import base64
import os
import re
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

    def _get_group_local_base(self, group_path: str, local_base: str = None) -> str:
        base_clone = local_base or self.config.get('local_clone_path', '/ai/utilities/halo_admin_utility/cache/halo')
        cache_root = self.config.get('local_cache_root') or os.path.dirname(base_clone.rstrip('/'))
        if group_path == 'ai/halo':
            return base_clone
        group_short = group_path.split('/')[-1]
        return os.path.join(cache_root, group_short)

    def resolve_local_repo_path(self, project_name: str, local_base: str = None) -> str:
        base_clone = local_base or self.config.get('local_clone_path', '/ai/utilities/halo_admin_utility/cache/halo')
        project_paths = self.config.get('project_paths') or [self.config.get('project_path', 'ai/halo')]
        
        candidate_dir = None
        for grp in project_paths:
            if project_name.startswith(grp + "/"):
                rel_path = project_name[len(grp) + 1:]
                grp_base = self._get_group_local_base(grp, base_clone)
                candidate_dir = os.path.join(grp_base, rel_path)
                break
                
        if not candidate_dir:
            project_path_cfg = self.config.get('project_path', 'ai/halo')
            grp_base = self._get_group_local_base(project_path_cfg, base_clone)
            candidate_dir = os.path.join(grp_base, project_name)
            
        # If candidate_dir is a virtual service subpath inside a domain monorepo, walk up to find .git root
        if not os.path.exists(os.path.join(candidate_dir, '.git')):
            parent_dir = os.path.dirname(candidate_dir)
            if os.path.exists(os.path.join(parent_dir, '.git')):
                return parent_dir
        return candidate_dir

    def parse_local_documentation_tree(self, cache_dir: str) -> list:
        docs_list = []
        if not os.path.exists(cache_dir):
            return docs_list
        for root, _, files in os.walk(cache_dir):
            for file in files:
                if file.endswith('.md'):
                    full_path = os.path.join(root, file)
                    rel_path = os.path.relpath(full_path, cache_dir)
                    project_name = rel_path.split(os.sep)[0] if os.sep in rel_path else "unknown"
                    with open(full_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    metadata = {
                        "doc_type": "Unknown",
                        "category": "Unknown",
                        "name": file,
                        "acronym": "",
                        "version": "",
                        "author": "",
                        "status": "",
                        "date": ""
                    }
                    
                    for line in content.split('\n')[:30]:
                        match = re.match(r'\*\*([A-Za-z_]+):\*\*\s*(.*)', line)
                        if match:
                            key, value = match.groups()
                            key_lower = key.lower()
                            if key_lower in metadata:
                                metadata[key_lower] = value.strip()
                                
                    if 'archive' in rel_path.split(os.sep):
                        metadata['doc_type'] = 'Archive'
                        metadata['category'] = 'Archive'
                    
                    docs_list.append({
                        "filename": file,
                        "raw_markdown": content,
                        "doc_type": metadata["doc_type"],
                        "category": metadata["category"],
                        "name": metadata["name"],
                        "acronym": metadata["acronym"],
                        "version": metadata["version"],
                        "author": metadata["author"],
                        "status": metadata["status"],
                        "date": metadata["date"],
                        "relative_path": rel_path,
                        "project_name": project_name
                    })
        return docs_list

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
        project_paths = self.config.get('project_paths') or [self.config.get('project_path', 'ai/halo')]
        ignored_projects = set(self.config.get('ignored_projects', []))
        local_path = self.config.get('local_clone_path')
        domain = self.url.replace('https://', '').replace('http://', '')
        
        gl = gitlab.Gitlab(self.url, private_token=token, ssl_verify=False)
        projects_with_grp = []
        seen_ids = set()
        for grp_path in project_paths:
            try:
                group = gl.groups.get(grp_path)
                grp_base = self._get_group_local_base(grp_path, local_path)
                os.makedirs(grp_base, exist_ok=True)
                for p in group.projects.list(include_subgroups=True, all=True):
                    if p.id not in seen_ids and p.path_with_namespace not in ignored_projects:
                        seen_ids.add(p.id)
                        projects_with_grp.append((p, grp_path, grp_base))
            except Exception as e:
                logger.warning(f"Failed to fetch projects for group {grp_path}: {e}")
        
        import concurrent.futures
        
        def sync_project(item):
            p, grp_path, grp_base = item
            repo_url = f"https://oauth2:{token}@{domain}/{p.path_with_namespace}.git"
            rel_path = p.path_with_namespace
            if rel_path.startswith(grp_path + "/"):
                rel_path = rel_path[len(grp_path) + 1:]
                
            repo_local_path = os.path.join(grp_base, rel_path)
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
                result = subprocess.run(['git', 'reset', '--hard', f'origin/{active_branch}'], cwd=repo_local_path, capture_output=True, text=True)
                subprocess.run(['git', 'clean', '-fd'], cwd=repo_local_path, capture_output=True)
                
                if result.returncode != 0:
                    return f"❌ Failed to sync {p.path_with_namespace} (branch: {active_branch}): {result.stderr.strip()}"
                else:
                    return f"✅ Synced {p.path_with_namespace} (branch: {active_branch})"

        logs = []
        if projects_with_grp:
            with concurrent.futures.ThreadPoolExecutor(max_workers=min(20, len(projects_with_grp))) as executor:
                future_to_project = {executor.submit(sync_project, item): item[0] for item in projects_with_grp}
                for future in concurrent.futures.as_completed(future_to_project):
                    try:
                        logs.append(future.result())
                    except Exception as e:
                        p = future_to_project[future]
                        logs.append(f"❌ Unhandled exception on {p.path_with_namespace}: {str(e)}")
        
        return "\n".join(logs)
        
    def list_group_cache(self):
        local_path = self.config.get('local_clone_path')
        project_paths = self.config.get('project_paths') or [self.config.get('project_path', 'ai/halo')]
        ignored_projects = set(self.config.get('ignored_projects', []))
            
        token = self.config.get('bot_token')
        domain = self.url.replace('https://', '').replace('http://', '')
        gl = gitlab.Gitlab(self.url, private_token=token, ssl_verify=False)
        
        projects = {}
        grp_bases = []
        for grp_path in project_paths:
            grp_base = self._get_group_local_base(grp_path, local_path)
            if os.path.exists(grp_base):
                grp_bases.append((grp_path, grp_base))
            try:
                group = gl.groups.get(grp_path)
                for p in group.projects.list(include_subgroups=True, all=True):
                    if p.path_with_namespace not in ignored_projects:
                        projects[p.path_with_namespace] = p
            except Exception:
                pass
                
        if not grp_bases:
            return "Cache directory does not exist. Run sync first."
            
        output = []
        for grp_path, grp_base in grp_bases:
            for root, dirs, files in os.walk(grp_base):
                if '.git' in dirs:
                    dirs.remove('.git')
                    repo_dir = root
                    
                    rel_dir = os.path.relpath(repo_dir, grp_base)
                    full_project_path = f"{grp_path}/{rel_dir}" if rel_dir != "." else grp_path
                    if full_project_path in ignored_projects:
                        continue
                    
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
            
        repo_dir = self.resolve_local_repo_path(project_name, local_path)
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
        project_paths = self.config.get('project_paths') or [self.config.get('project_path', 'ai/halo')]
        grp_bases = [self._get_group_local_base(g, local_path) for g in project_paths if os.path.exists(self._get_group_local_base(g, local_path))]
        if not grp_bases:
            raise RuntimeError("Cache directory does not exist. Run sync first.")
            
        author_name = self.config.get('bot_username', 'GIA AI Bot')
        author_email = "gia-ai@gtt.net"
            
        logs = []
        for grp_base in grp_bases:
            for root, dirs, files in os.walk(grp_base):
                if '.git' in dirs:
                    dirs.remove('.git')
                    repo_dir = root
                    rel_dir = os.path.relpath(repo_dir, grp_base)
                    
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

    def create_tag(self, project_path, tag_name, ref, message=None):
        gl = gitlab.Gitlab(self.url, private_token=self.token, ssl_verify=False)
        project = gl.projects.get(project_path)
        try:
            payload = {'tag_name': tag_name, 'ref': ref}
            if message:
                payload['message'] = message
            tag = project.tags.create(payload)
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