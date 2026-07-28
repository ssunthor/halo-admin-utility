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
        """Fetches the raw file content from GitLab API without parsing it."""
        token = self.token
        
        try:
            gl = gitlab.Gitlab(self.url, private_token=token, ssl_verify=False)
            project = gl.projects.get(project_path)
            f = project.files.get(file_path=file_path, ref=branch)
            
            # GitLab returns base64 encoded content via the API
            return base64.b64decode(f.content).decode('utf-8')
        except Exception as e:
            raise RuntimeError(f"Failed to fetch {file_path} via API: {e}")

    def fetch_repository_tree(self, project_path, path=''):
        """Fetches the repository tree structure from GitLab API."""
        token = self.token
        
        try:
            import json
            gl = gitlab.Gitlab(self.url, private_token=token, ssl_verify=False)
            project = gl.projects.get(project_path)
            tree = project.repository_tree(path=path, ref='main', recursive=True, get_all=True)
            # Return JSON string representing the file tree
            tree_data = [item.attributes if hasattr(item, 'attributes') else item for item in tree]
            return json.dumps(tree_data)
        except Exception as e:
            raise RuntimeError(f"Failed to fetch repository tree via API: {e}")

    def sync_local_repo(self, project_path, local_path):
        """Syncs the local repository by cloning or pulling."""
        token = self.token
        
        # Format the oauth2 url for cloning
        domain = self.url.replace('https://', '').replace('http://', '')
        repo_url = f"https://oauth2:{token}@{domain}/{project_path}.git"

        # Ensure parent directory exists
        os.makedirs(os.path.dirname(local_path), exist_ok=True)

        if not os.path.exists(os.path.join(local_path, '.git')):
            logger.info(f"Cloning {project_path} into {local_path} (shallow)...")
            # Capture output so it is returned to the gRPC client instead of nakedly printed to the systemd journal
            result = subprocess.run(['git', 'clone', '--depth', '1', repo_url, local_path], capture_output=True, text=True)
            if result.returncode != 0:
                raise RuntimeError(f"Git clone failed with exit code {result.returncode}\n{result.stderr}")
            output = (result.stdout + "\n" + result.stderr).strip()
            return f"Successfully cloned {project_path} to {local_path}.\n{output}"
        else:
            logger.info(f"Pulling latest changes for {project_path} in {local_path} (shallow)...")
            # Always update the remote url to ensure the latest token is used in case it was rotated
            subprocess.run(['git', 'remote', 'set-url', 'origin', repo_url], cwd=local_path)
            
            result = subprocess.run(['git', 'pull', '--depth', '1', 'origin', 'main'], cwd=local_path, capture_output=True, text=True)
            if result.returncode != 0:
                raise RuntimeError(f"Git pull failed with exit code {result.returncode}\n{result.stderr}")
            output = (result.stdout + "\n" + result.stderr).strip()
            return f"Successfully pulled latest changes for {project_path} in {local_path}.\n{output}"

    def push_local_repo(self, project_path, local_path, commit_msg, branch='main'):
        """Commits all local changes and pushes them to GitLab."""
        token = self.token
        
        if not os.path.exists(os.path.join(local_path, '.git')):
            raise RuntimeError(f"No git repository found at {local_path}. Run sync first.")
            
        # git add .
        add_res = subprocess.run(['git', 'add', '.'], cwd=local_path, capture_output=True, text=True)
        if add_res.returncode != 0:
            raise RuntimeError(f"Git add failed: {add_res.stderr}")
            
        # check if there's anything to commit
        status_res = subprocess.run(['git', 'status', '--porcelain'], cwd=local_path, capture_output=True, text=True)
        if not status_res.stdout.strip():
            return "No changes to commit."

        # Configure git author dynamically from settings or default
        author_name = self.config.get('author_name', 'HAU Auto Sync')
        author_email = self.config.get('author_email', 'sera-ai@gtt.net')
        subprocess.run(['git', 'config', 'user.name', author_name], cwd=local_path)
        subprocess.run(['git', 'config', 'user.email', author_email], cwd=local_path)

        # git commit -m "..."
        commit_res = subprocess.run(['git', 'commit', '-m', commit_msg], cwd=local_path, capture_output=True, text=True)
        if commit_res.returncode != 0:
            raise RuntimeError(f"Git commit failed: {commit_res.stderr}")
            
        # Update remote to ensure token is valid
        domain = self.url.replace('https://', '').replace('http://', '')
        repo_url = f"https://oauth2:{token}@{domain}/{project_path}.git"
        subprocess.run(['git', 'remote', 'set-url', 'origin', repo_url], cwd=local_path)
            
        # git push origin main
        logger.info(f"Pushing changes to origin {branch}... (this may take a while)")
        push_res = subprocess.run(['git', 'push', 'origin', branch], cwd=local_path, capture_output=True, text=True)
        if push_res.returncode != 0:
            raise RuntimeError(f"Git push failed with exit code {push_res.returncode}\n{push_res.stderr}")
            
        output = (push_res.stdout + "\n" + push_res.stderr).strip()
        return f"Successfully pushed changes: {commit_msg}\n{output}"

    def fetch_container_tags(self, path, repository_id=None):
        """Fetches the available container registry tags for a project or group."""
        token = self.token
        try:
            import json
            gl = gitlab.Gitlab(self.url, private_token=token, ssl_verify=False)
            
            all_tags = []
            
            # Try to get it as a group first
            try:
                group = gl.groups.get(path)
                projects = group.projects.list(include_subgroups=True, all=True)
            except Exception:
                projects = []
                
            if projects:
                for p in projects:
                    try:
                        project = gl.projects.get(p.id)
                        
                        # Pre-fetch active branches and git tags
                        try:
                            active_branches = {b.name: b.commit['author_name'] for b in project.branches.list(get_all=True)}
                        except Exception:
                            active_branches = {}
                            
                        try:
                            active_git_tags = {gt.name: gt.commit['author_name'] for gt in project.tags.list(get_all=True)}
                        except Exception:
                            active_git_tags = {}
                            
                        repos = project.repositories.list()
                        for r in repos:
                            tags = r.tags.list(get_all=True)
                            for t in tags:
                                try:
                                    full_tag = r.tags.get(id=t.name)
                                    created_at = full_tag.attributes.get('created_at', 'unknown')
                                except Exception:
                                    created_at = 'unknown'
                                    
                                author = active_branches.get(t.name) or active_git_tags.get(t.name) or 'Unknown'
                                    
                                # Create a distinguished path name for group aggregates
                                distinguished_path = f"{project.path_with_namespace}/{r.name}" if r.name else project.path_with_namespace
                                all_tags.append({
                                    "name": t.name,
                                    "path": f"{distinguished_path}:{t.name}",
                                    "project": project.path_with_namespace,
                                    "branch_exists": t.name in active_branches,
                                    "author": author,
                                    "created_at": created_at
                                })
                    except Exception as e:
                        logger.error(f"Skipping or failed to fetch tags for project {p.id}: {e}")
            else:
                # Fallback to single project
                project = gl.projects.get(path)
                
                try:
                    active_branches = {b.name: b.commit['author_name'] for b in project.branches.list(get_all=True)}
                except Exception:
                    active_branches = {}
                    
                try:
                    active_git_tags = {gt.name: gt.commit['author_name'] for gt in project.tags.list(get_all=True)}
                except Exception:
                    active_git_tags = {}
                    
                repos = project.repositories.list()
                if not repos:
                    return "[]"
                    
                repo = repos[0] if not repository_id else project.repositories.get(repository_id)
                tags = repo.tags.list(get_all=True)
                for t in tags:
                    try:
                        full_tag = repo.tags.get(id=t.name)
                        created_at = full_tag.attributes.get('created_at', 'unknown')
                    except Exception:
                        created_at = 'unknown'
                        
                    author = active_branches.get(t.name) or active_git_tags.get(t.name) or 'Unknown'
                        
                    all_tags.append({
                        "name": t.name,
                        "path": t.path,
                        "project": project.path_with_namespace,
                        "branch_exists": t.name in active_branches,
                        "author": author,
                        "created_at": created_at
                    })
            
        except Exception as e:
            raise RuntimeError(f"Failed to fetch container tags via API: {e}")
            
        return json.dumps(all_tags)
    def sync_group_cache(self, default_branch='dev'):
        """Syncs all repositories in the group to the local cache path."""
        token = self.config['bot_token']
        project_path = self.config['project_path']
        local_path = self.config['local_clone_path']
        
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
            
            if not os.path.exists(os.path.join(repo_local_path, '.git')):
                # Check if default_branch ('dev') exists remotely without using GitLab API
                ls_remote = subprocess.run(['git', 'ls-remote', '--heads', repo_url, default_branch], capture_output=True, text=True)
                if ls_remote.stdout.strip():
                    target_branch = default_branch
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
                # Update remote URL
                subprocess.run(['git', 'remote', 'set-url', 'origin', repo_url], cwd=repo_local_path)
                
                curr_res = subprocess.run(['git', 'branch', '--show-current'], cwd=repo_local_path, capture_output=True, text=True)
                active_branch = curr_res.stdout.strip()
                if not active_branch:
                    active_branch = p.default_branch or 'main'
                    subprocess.run(['git', 'checkout', active_branch], cwd=repo_local_path, capture_output=True)
                
                logger.info(f"Pulling {p.path_with_namespace} in {repo_local_path} (branch: {active_branch})...")
                result = subprocess.run(['git', 'pull', 'origin', active_branch], cwd=repo_local_path, capture_output=True, text=True)
                if result.returncode != 0:
                    return f"❌ Failed to pull {p.path_with_namespace} (branch: {active_branch}): {result.stderr.strip()}"
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
        """Lists locally cloned repositories and their branches."""
        local_path = self.config.get('local_clone_path')
        if not local_path or not os.path.exists(local_path):
            return "Cache directory does not exist. Run sync first."
            
        token = self.config['bot_token']
        project_path = self.config['project_path']
        domain = self.url.replace('https://', '').replace('http://', '')
        gl = gitlab.Gitlab(self.url, private_token=token, ssl_verify=False)
        group = gl.groups.get(project_path)
        projects = {p.path_with_namespace: p for p in group.projects.list(include_subgroups=True, all=True)}
            
        output = []
        for root, dirs, files in os.walk(local_path):
            if '.git' in dirs:
                dirs.remove('.git') # don't recurse into .git
                repo_dir = root
                
                # Reconstruct the project path from the folder path
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
                
                repo_data = {
                    "repository": full_project_path,
                    "active_branch": active_branch,
                    "default_branch": default_branch,
                    "branches": branches
                }
                output.append(repo_data)
                
        import json
        return json.dumps(output)

    def checkout_project_branch(self, project_name, branch_name):
        """Checks out a specific branch for a project in the local cache."""
        local_path = self.config.get('local_clone_path')
        if not local_path:
            raise RuntimeError("local_clone_path is not defined in configuration.")
            
        project_path = self.config['project_path']
        rel_path = project_name
        if rel_path.startswith(project_path + "/"):
            rel_path = rel_path[len(project_path) + 1:]
            
        repo_dir = os.path.join(local_path, rel_path)
        if not os.path.exists(os.path.join(repo_dir, '.git')):
            raise RuntimeError(f"Project '{project_name}' is not cloned locally. Run sync first.")
            
        subprocess.run(['git', 'fetch', 'origin'], cwd=repo_dir, capture_output=True)
        result = subprocess.run(['git', 'checkout', branch_name], cwd=repo_dir, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"Failed to checkout branch '{branch_name}' for '{project_name}': {result.stderr}")
            
        pull_result = subprocess.run(['git', 'pull', 'origin', branch_name], cwd=repo_dir, capture_output=True, text=True)
        return f"Successfully checked out and pulled '{branch_name}' for '{project_name}'\n{pull_result.stdout.strip()}"

    def push_group_cache(self, commit_msg):
        """Commits and pushes all changes in all local repos."""
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

    def commit_file_api(self, project_path, file_path, branch, content, commit_msg):
        """Commits a single file directly via the GitLab API."""
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
        
        try:
            # Try to update existing
            project.commits.create(data)
        except gitlab.exceptions.GitlabCreateError as e:
            if "A file with this name doesn't exist" in str(e):
                # Create instead
                data['actions'][0]['action'] = 'create'
                project.commits.create(data)
            else:
                raise e
        return f"Successfully committed {file_path} to {branch} via API."

    def create_and_merge_mr(self, project_path, source_branch, target_branch, commit_message, keep_branch=False):
        """Creates an MR and attempts to merge it."""
        try:
            import gitlab
            gl = gitlab.Gitlab(self.url, private_token=self.token, ssl_verify=False)
            project = gl.projects.get(project_path)
            
            # Check for existing MR
            mrs = project.mergerequests.list(source_branch=source_branch, target_branch=target_branch, state='opened')
            if mrs:
                mr = mrs[0]
            else:
                mr = project.mergerequests.create({
                    'source_branch': source_branch,
                    'target_branch': target_branch,
                    'title': f"HAU Auto-Release: {source_branch} -> {target_branch}",
                    'description': commit_message
                })
            
            import time
            
            # Wait for MR to finish checking mergeability and spawn pipeline
            active_pipeline = False
            for _ in range(20):
                mr = project.mergerequests.get(mr.iid)
                mr_pipelines = mr.pipelines.list()
                
                if mr_pipelines and mr_pipelines[0].status in ['running', 'pending', 'created']:
                    active_pipeline = True
                    
                if mr.detailed_merge_status != "checking":
                    if mr.detailed_merge_status == "mergeable":
                        break
                    if mr.detailed_merge_status == "ci_still_running" or mr.detailed_merge_status == "ci_must_pass":
                        if active_pipeline:
                            break
                            
                time.sleep(1)
                
            remove_source = not keep_branch
            merge_msg = f"{commit_message}\n\n[skip ci]"
            
            try:
                if mr.detailed_merge_status == "mergeable" and not active_pipeline:
                    mr.merge(merge_commit_message=merge_msg, should_remove_source_branch=remove_source)
                else:
                    mr.merge(merge_commit_message=merge_msg, should_remove_source_branch=remove_source, merge_when_pipeline_succeeds=True)
            except gitlab.exceptions.GitlabError as e:
                # If we get a 405, it could mean the pipeline was skipped or it has conflicts.
                mr = project.mergerequests.get(mr.iid)
                status = mr.detailed_merge_status
                if status == "conflict":
                    return False, mr.iid, f"Merge conflicts exist. Please resolve them on GitLab."
                return False, mr.iid, f"GitLab rejected merge (405). Detailed MR Status: '{status}'. Raw Error: {str(e)}"
                
            return True, mr.iid, f"Successfully queued merge for '{source_branch}' into '{target_branch}'."
            
        except Exception as e:
            return False, None, f"{str(e)}"

    def monitor_pipeline(self, project_path, ref=None, mr_iid=None, pipeline_id=None, debug=False):
        gl = gitlab.Gitlab(self.url, private_token=self.token, ssl_verify=False)
        project = gl.projects.get(project_path)
        
        import time
        from datetime import datetime, timezone, timedelta
        
        pipeline = None
        if pipeline_id:
            pipeline = project.pipelines.get(pipeline_id)
        else:
            for _ in range(15):
                if mr_iid:
                    mr = project.mergerequests.get(mr_iid)
                    pipelines = mr.pipelines.list()
                    if pipelines:
                        latest_pipeline = pipelines[0]
                        created_at = datetime.fromisoformat(latest_pipeline.created_at.replace('Z', '+00:00'))
                        if (datetime.now(timezone.utc) - created_at) < timedelta(seconds=30) or latest_pipeline.status in ['running', 'pending', 'created']:
                            pipeline = project.pipelines.get(latest_pipeline.id)
                            break
                elif ref:
                    pipelines = project.pipelines.list(ref=ref, order_by='id', sort='desc')
                    if pipelines:
                        latest_pipeline = pipelines[0]
                        created_at = datetime.fromisoformat(latest_pipeline.created_at.replace('Z', '+00:00'))
                        if (datetime.now(timezone.utc) - created_at) < timedelta(seconds=30) or latest_pipeline.status in ['running', 'pending', 'created']:
                            pipeline = project.pipelines.get(latest_pipeline.id)
                            break
            time.sleep(1)
            
        if not pipeline:
            yield "No active pipeline found after 15 seconds."
            return
            
        yield f"Monitoring Pipeline #{pipeline.id} on '{pipeline.ref}' (Web: {pipeline.web_url})..."
        
        job_states = {}
        job_trace_offsets = {}
        job_start_times = {}
        
        while pipeline.status in ['running', 'pending', 'created']:
            jobs = pipeline.jobs.list(all=True)
            active_jobs = 0
            for job in jobs:
                prev_status = job_states.get(job.name)
                
                if job.status == 'running' and prev_status != 'running':
                    job_start_times[job.name] = time.time()
                
                is_terminal_transition = (job.status in ['success', 'failed', 'canceled'] and prev_status not in ['success', 'failed', 'canceled'])
                is_slow_running = (job.status == 'running' and time.time() - job_start_times.get(job.name, time.time()) > 5)
                
                if debug and (is_slow_running or is_terminal_transition):
                    try:
                        p_job = project.jobs.get(job.id)
                        trace_bytes = p_job.trace()
                        if trace_bytes:
                            trace_str = trace_bytes.decode('utf-8', errors='replace')
                            lines = trace_str.split('\n')
                            last_offset = job_trace_offsets.get(job.name, 0)
                            if len(lines) > last_offset:
                                for line in lines[last_offset:]:
                                    if line.strip():
                                        yield f"      [{job.name}] {line.strip()}"
                                job_trace_offsets[job.name] = len(lines)
                    except Exception:
                        pass
                
                if prev_status != job.status:
                    if job.status == 'success':
                        duration_val = getattr(job, 'duration', None)
                        if duration_val is not None:
                            duration = float(duration_val)
                        else:
                            duration = time.time() - job_start_times.get(job.name, time.time())
                        yield f"  ✅ Job '{job.name}' (Stage: {job.stage}) completed successfully in {duration:.1f}s."
                    elif job.status == 'failed':
                        yield f"  ❌ Job '{job.name}' (Stage: {job.stage}) failed."
                        try:
                            p_job = project.jobs.get(job.id)
                            trace_bytes = p_job.trace()
                            if trace_bytes:
                                trace_str = trace_bytes.decode('utf-8', errors='replace')
                                lines = trace_str.split('\n')
                                yield f"    --- Last 50 lines of trace for {job.name} ---"
                                for line in lines[-50:]:
                                    if line.strip():
                                        yield f"      {line.strip()}"
                                yield f"    ----------------------------------------"
                        except Exception as e:
                            yield f"      (Could not fetch trace: {e})"
                    elif job.status == 'running':
                        yield f"  ▶️ Job '{job.name}' (Stage: {job.stage}) is now RUNNING..."
                    job_states[job.name] = job.status
                    
                if job.status in ['running', 'pending']:
                    active_jobs += 1
                            
            if active_jobs == 0 and not debug:
                yield f"Pipeline Status: {pipeline.status.upper()} (Transitioning stages or finalizing...)"
                
            time.sleep(5)
            pipeline = project.pipelines.get(pipeline.id)
            
        if pipeline.status == 'success':
            yield f"Pipeline #{pipeline.id} completed successfully! ✅"
            jobs = pipeline.jobs.list(all=True)
            for job in jobs:
                if job.status == 'failed':
                    yield f"  ⚠️ Note: Job '{job.name}' (Stage: {job.stage}) failed but was allowed to fail. (Web: {job.web_url})"
                    try:
                        p_job = project.jobs.get(job.id)
                        trace_bytes = p_job.trace()
                        if trace_bytes:
                            trace_str = trace_bytes.decode('utf-8', errors='replace')
                            lines = trace_str.split('\n')
                            yield f"    --- Last 50 lines of trace for {job.name} ---"
                            for line in lines[-50:]:
                                if line.strip():
                                    yield f"      {line.strip()}"
                            yield f"    ----------------------------------------"
                    except Exception as e:
                        yield f"      (Could not fetch trace: {e})"
            
            # Fetch container footprint size
            try:
                repos = project.repositories.list()
                if repos:
                    tags = repos[0].tags.list(get_all=True)
                    if tags:
                        import re
                        expected_tag_name = None
                        if pipeline.ref.startswith('refs/merge-requests/'):
                            try:
                                mr_iid_from_ref = int(pipeline.ref.split('/')[2])
                                mr_obj = project.mergerequests.get(mr_iid_from_ref)
                                expected_tag_name = re.sub(r'[^a-z0-9]+', '-', mr_obj.source_branch.lower()).strip('-')[:63]
                            except Exception:
                                pass
                        else:
                            expected_tag_name = re.sub(r'[^a-z0-9]+', '-', pipeline.ref.lower()).strip('-')[:63]
                            
                        target_tag = None
                        if expected_tag_name:
                            for t in tags:
                                if t.name == expected_tag_name:
                                    target_tag = repos[0].tags.get(id=t.name)
                                    break
                                    
                        if not target_tag:
                            tags.sort(key=lambda t: getattr(t, 'created_at', ''), reverse=True)
                            target_tag = repos[0].tags.get(id=tags[0].name)
                            
                        total_size_bytes = target_tag.attributes.get('total_size', 0)
                        if total_size_bytes:
                            size_mb = total_size_bytes / (1024 * 1024)
                            yield f"  📦 Container '{target_tag.name}' footprint: {size_mb:.2f} MB"
            except Exception as e:
                yield f"  (Could not fetch container size: {e})"
                
            yield {"pipeline_success": True}
        else:
            yield f"Pipeline #{pipeline.id} failed with status: {pipeline.status.upper()} ❌"
            jobs = pipeline.jobs.list(all=True)
            for job in jobs:
                if job.status == 'failed':
                    yield f"  - Failed Job: {job.name} (Stage: {job.stage}) (Web: {job.web_url})"
                    try:
                        p_job = project.jobs.get(job.id)
                        trace_bytes = p_job.trace()
                        if trace_bytes:
                            trace_str = trace_bytes.decode('utf-8', errors='replace')
                            lines = trace_str.split('\n')
                            yield f"    --- Last 50 lines of trace for {job.name} ---"
                            for line in lines[-50:]:
                                if line.strip():
                                    yield f"      {line.strip()}"
                            yield f"    ----------------------------------------"
                    except Exception as e:
                        yield f"      (Could not fetch trace: {e})"
            yield {"pipeline_success": False, "pipeline_id": pipeline.id}

    def create_tag(self, project_path, tag_name, ref):
        """Creates a Git tag via the API."""
        gl = gitlab.Gitlab(self.url, private_token=self.token, ssl_verify=False)
        project = gl.projects.get(project_path)
        
        try:
            tag = project.tags.create({'tag_name': tag_name, 'ref': ref})
            return True, f"Successfully created tag {tag.name} from {ref}."
        except Exception as e:
            return False, f"Failed to create tag: {str(e)}"

    def retag_container(self, project_path, old_tag, new_tag):
        """Retags a container image in the GitLab Container Registry using the Docker V2 API."""
        import requests
        
        # 1. Get JWT Token for registry authentication
        auth_url = f"{self.url.rstrip('/')}/jwt/auth"
        service = "container_registry"
        scope = f"repository:{project_path}:pull,push"
        
        # Authenticate with PAT
        token_res = requests.get(
            auth_url,
            params={"service": service, "scope": scope},
            auth=("__token__", self.token),
            verify=False
        )
        if token_res.status_code != 200:
            return False, f"Failed to authenticate with registry: {token_res.text}"
            
        token = token_res.json().get("token")
        
        # 2. Get Manifest of the old tag
        from urllib.parse import urlparse
        parsed_url = urlparse(self.url)
        registry_url = f"https://{parsed_url.netloc}:4567"
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.docker.distribution.manifest.v2+json, application/vnd.oci.image.manifest.v1+json"
        }
        
        manifest_url = f"{registry_url}/v2/{project_path.lower()}/manifests/{old_tag}"
        res = requests.get(manifest_url, headers=headers, verify=False)
        if res.status_code != 200:
            return False, f"Failed to get manifest for {old_tag}: {res.status_code} - {res.text}"
            
        manifest = res.text
        content_type = res.headers.get("Content-Type")
        
        # 3. Put Manifest to the new tag
        put_headers = headers.copy()
        put_headers["Content-Type"] = content_type
        
        put_url = f"{registry_url}/v2/{project_path.lower()}/manifests/{new_tag}"
        put_res = requests.put(put_url, headers=put_headers, data=manifest, verify=False)
        
        if put_res.status_code in [201, 202]:
            return True, f"Successfully retagged container image '{old_tag}' to '{new_tag}'"
        else:
            return False, f"Failed to push new tag {new_tag}: {put_res.status_code} - {put_res.text}"
