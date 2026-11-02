import requests
import json
import concurrent.futures
import gitlab
import logging
import urllib3
import base64
import yaml
import os
from requests.auth import HTTPBasicAuth
from core.io_handlers.sql_reader import SQLReader
from core.io_handlers.sql_writer import SQLWriter

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)

class GitInventoryManager:
    def __init__(self, config):
        self.config = config
        if 'external_services' in self.config and 'gitlab' in self.config['external_services']:
            gl_cfg = self.config['external_services']['gitlab']
            self.url = gl_cfg.get('url')
            self.token = gl_cfg.get('bot_token')
            self.project_paths = gl_cfg.get('project_paths') or [gl_cfg.get('project_path', 'ai/defense-halo')]
            self.ignored_projects = set(gl_cfg.get('ignored_projects', ['ai/defense-halo/k8s']))
        else:
            self.url = None
            self.token = None
            self.project_paths = ['ai/defense-halo', 'ai/halo']
            self.ignored_projects = {'ai/defense-halo/k8s'}

    def _discover_domain_services(self, gl_project, containers_nodes, default_branch="main", active_branches=None):
        """
        Inspects a GitLab project to determine if it is a multi-service domain monorepo.
        Returns a list of service dicts:
          [{"service_name": ..., "subpath": ..., "container_repo_name": ...}, ...]
        Returns an empty list if it is a standard single-service repository.
        """
        ref_to_check = 'dev' if (active_branches and 'dev' in active_branches) else default_branch
        root_ci_content = None
        for candidate_ref in [ref_to_check, default_branch, 'main', 'dev']:
            if not candidate_ref:
                continue
            try:
                f = gl_project.files.get(file_path='.gitlab-ci.yml', ref=candidate_ref)
                root_ci_content = base64.b64decode(f.content).decode('utf-8')
                ref_to_check = candidate_ref
                break
            except Exception:
                continue

        services = []
        if root_ci_content:
            try:
                ci_data = yaml.safe_load(root_ci_content) or {}
                triggers = []
                for job_name, job_cfg in ci_data.items():
                    if isinstance(job_cfg, dict) and 'trigger' in job_cfg and isinstance(job_cfg['trigger'], dict):
                        inc = job_cfg['trigger'].get('include')
                        if isinstance(inc, str) and inc.endswith('.gitlab-ci.yml'):
                            triggers.append((job_name, inc))
                if triggers:
                    for job_name, inc_path in triggers:
                        subpath = os.path.dirname(inc_path)
                        container_repo_name = job_name
                        has_container = False
                        try:
                            cf = gl_project.files.get(file_path=inc_path, ref=ref_to_check)
                            child_ci = yaml.safe_load(base64.b64decode(cf.content).decode('utf-8')) or {}
                            vars_block = child_ci.get('variables', {})
                            if isinstance(vars_block, dict):
                                if vars_block.get('CONTAINER_BUILD_NAME'):
                                    container_repo_name = str(vars_block['CONTAINER_BUILD_NAME']).strip()
                                    has_container = True
                                elif vars_block.get('CI_APPLICATION_REPOSITORY'):
                                    repo_var = str(vars_block['CI_APPLICATION_REPOSITORY']).strip()
                                    if '/' in repo_var:
                                        container_repo_name = repo_var.split('/')[-1]
                                        has_container = True
                        except Exception:
                            pass
                        services.append({
                            "service_name": container_repo_name if has_container else job_name,
                            "subpath": subpath,
                            "container_repo_name": container_repo_name
                        })
                    return services
            except Exception as e:
                logger.warning(f"Failed to parse .gitlab-ci.yml for {gl_project.path_with_namespace}: {e}")

        # Fallback: check if project has named sub-container repositories (excluding tmp/cache)
        valid_sub_repos = [
            c for c in (containers_nodes or [])
            if c.get('name') and c.get('name').lower() not in ('tmp', 'cache')
        ]
        if valid_sub_repos:
            for c in valid_sub_repos:
                c_name = c.get('name')
                services.append({
                    "service_name": c_name,
                    "subpath": c_name,
                    "container_repo_name": c_name
                })
            return services

        # Special case: domain repo without root .gitlab-ci.yml and without containers (e.g. ai/defense-halo/ingest)
        if gl_project.path_with_namespace.startswith("ai/defense-halo/") and gl_project.path_with_namespace != "ai/defense-halo/sentinel":
            try:
                tree = gl_project.repository_tree(ref=ref_to_check)
                dirs = [t['name'] for t in tree if t['type'] == 'tree' and not t['name'].startswith('.')]
                if dirs:
                    for d in dirs:
                        services.append({
                            "service_name": d,
                            "subpath": d,
                            "container_repo_name": d
                        })
                    return services
            except Exception:
                pass

        return []

    def sync_database_inventory(self, sql_reader: SQLReader, sql_writer: SQLWriter, project_name: str = None, progress_cb=None) -> str:
        def log_and_cb(msg):
            logger.info(msg)
            if progress_cb:
                progress_cb(msg)

        log_and_cb(f"Starting Git Inventory Sync for project: {project_name or 'all'}")
        audit_mapping = {'tags': {}, 'branches': {}}
        log_and_cb("Fetching ordered git releases from database for audit mapping...")
        logs = sql_reader.get_all_git_releases_ordered()
        for log in logs:
            if log.action == 'DELETE':
                continue
            if log.project_name:
                if log.project_name not in audit_mapping['tags']:
                    audit_mapping['tags'][log.project_name] = {}
                if log.project_name not in audit_mapping['branches']:
                    audit_mapping['branches'][log.project_name] = {}
                
                if log.version_tag and log.version_tag not in audit_mapping['tags'][log.project_name]:
                    audit_mapping['tags'][log.project_name][log.version_tag] = log.source_branch
                if log.target_branch and log.target_branch not in audit_mapping['branches'][log.project_name]:
                    audit_mapping['branches'][log.project_name][log.target_branch] = log.actor
                if log.source_branch and log.source_branch not in audit_mapping['branches'][log.project_name]:
                    audit_mapping['branches'][log.project_name][log.source_branch] = log.actor

        resolved_repo_path = None
        if project_name:
            resolved_proj = sql_reader.resolve_project_obj(project_name)
            if resolved_proj:
                resolved_repo_path = resolved_proj.repo_path or resolved_proj.project_path
            else:
                resolved_repo_path = sql_reader.resolve_project_path(project_name)

        log_and_cb(f"Resolved repository path: {resolved_repo_path or 'all configured groups'}. Initiating GitLab data fetch...")
        result_json = self.fetch_git_inventory_graphql(project_path=resolved_repo_path, audit_mapping=audit_mapping, progress_cb=progress_cb)
        
        log_and_cb("Parsing fetched GitLab data...")
        data = json.loads(result_json)
        
        log_and_cb(f"Upserting {len(data.get('projects', []))} projects/services into the database...")
        sql_writer.upsert_git_inventory(data)
        
        log_and_cb("Database upsert completed.")
        return "Successfully synced Git Inventory to DB."

    def fetch_git_inventory_graphql(self, group_path=None, project_path=None, audit_mapping=None, progress_cb=None):
        if not self.url or not self.token:
            raise RuntimeError("GitLab config with URL and token is missing.")
            
        def log_and_cb(msg):
            logger.info(msg)
            if progress_cb:
                progress_cb(msg)

        if audit_mapping is None:
            audit_mapping = {'tags': {}, 'branches': {}}
            
        gl = gitlab.Gitlab(self.url, private_token=self.token, ssl_verify=False)
        url = f"{self.url.rstrip('/')}/api/graphql"
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }
        
        all_projects = []

        if project_path:
            query = """
            query($projectPath: ID!) {
              project(fullPath: $projectPath) {
                id
                name
                fullPath
                repository {
                  rootRef
                  branchNames(searchPattern: "*", offset: 0, limit: 100)
                }
                releases(first: 50, sort: RELEASED_AT_DESC) {
                  nodes {
                    tagName
                  }
                }
                containerRepositories(first: 30) {
                  nodes {
                    id
                    name
                    path
                    tagsCount
                  }
                }
              }
            }
            """
            try:
                response = requests.post(
                    url, 
                    json={"query": query, "variables": {"projectPath": project_path}}, 
                    headers=headers,
                    verify=False
                )
                response.raise_for_status()
                data = response.json()
                
                if "errors" in data:
                    logger.error(f"GraphQL returned errors: {data['errors']}")
                    raise RuntimeError(f"GraphQL errors: {data['errors']}")
                    
                proj = data.get("data", {}).get("project")
                if proj:
                    all_projects.append(proj)
                elif '/' in project_path:
                    # Fallback in case project_path was a virtual service path (e.g. ai/defense-halo/core/backend)
                    parent_repo_path = "/".join(project_path.split('/')[:-1])
                    response2 = requests.post(
                        url,
                        json={"query": query, "variables": {"projectPath": parent_repo_path}},
                        headers=headers,
                        verify=False
                    )
                    if response2.status_code == 200:
                        proj2 = response2.json().get("data", {}).get("project")
                        if proj2:
                            all_projects.append(proj2)
            except Exception as e:
                logger.error(f"Failed to fetch single project via GraphQL: {e}")
                raise RuntimeError(f"Failed to fetch git inventory for project: {e}")

        else:
            groups_to_fetch = [group_path] if group_path else self.project_paths
            query = """
            query($groupPath: ID!, $afterCursor: String) {
              group(fullPath: $groupPath) {
                projects(includeSubgroups: true, first: 15, after: $afterCursor) {
                  pageInfo {
                    hasNextPage
                    endCursor
                  }
                  nodes {
                    id
                    name
                    fullPath
                    repository {
                      rootRef
                      branchNames(searchPattern: "*", offset: 0, limit: 100)
                    }
                    releases(first: 50, sort: RELEASED_AT_DESC) {
                      nodes {
                        tagName
                      }
                    }
                    containerRepositories(first: 30) {
                      nodes {
                        id
                        name
                        path
                        tagsCount
                      }
                    }
                  }
                }
              }
            }
            """
            
            for g_path in groups_to_fetch:
                try:
                    has_next_page = True
                    after_cursor = None
                    
                    while has_next_page:
                        response = requests.post(
                            url, 
                            json={"query": query, "variables": {"groupPath": g_path, "afterCursor": after_cursor}}, 
                            headers=headers,
                            verify=False
                        )
                        response.raise_for_status()
                        data = response.json()
                        
                        if "errors" in data:
                            logger.error(f"GraphQL returned errors for {g_path}: {data['errors']}")
                            break
                            
                        group_data = data.get("data", {}).get("group")
                        if not group_data:
                            break
                            
                        projects_page = group_data.get("projects", {})
                        for node in projects_page.get("nodes", []):
                            if node.get("fullPath") not in self.ignored_projects:
                                all_projects.append(node)
                        
                        page_info = projects_page.get("pageInfo", {})
                        has_next_page = page_info.get("hasNextPage", False)
                        after_cursor = page_info.get("endCursor")
                except Exception as e:
                    logger.error(f"Failed to fetch group {g_path} projects via GraphQL: {e}")
                    raise RuntimeError(f"Failed to fetch git inventory for group {g_path}: {e}")
                
        projects = all_projects
        log_and_cb(f"Successfully fetched {len(projects)} GitLab repositories via GraphQL.")
        
        registry_tokens = {}
        c_id_to_repo_path = {}
        log_and_cb("Fetching Docker Registry JWT tokens for container repositories...")
        for p in projects:
            full_path = p.get('fullPath')
            for c in p.get('containerRepositories', {}).get('nodes', []):
                c_name = c.get('name', '').lower()
                if c_name in ['tmp', 'cache']:
                    continue
                c_id = c.get('id')
                c_path = c.get('path') or (f"{full_path}/{c.get('name')}" if c.get('name') else full_path)
                if c_id and c_path:
                    c_id_to_repo_path[c_id] = c_path
                    if c.get('tagsCount', 0) > 0 and c_path not in registry_tokens:
                        auth_url = f"{self.url.rstrip('/')}/jwt/auth?service=container_registry&scope=repository:{c_path}:pull"
                        try:
                            res_auth = requests.get(auth_url, auth=HTTPBasicAuth('oauth2', self.token), verify=False)
                            if res_auth.status_code != 200:
                                res_auth = requests.get(auth_url, headers=headers, verify=False)
                            if res_auth.status_code == 200:
                                registry_tokens[c_path] = res_auth.json().get('token')
                            else:
                                logger.error(f"Failed to get registry token for {c_path}: {res_auth.status_code} {res_auth.text}")
                        except Exception as e:
                            logger.error(f"Exception getting registry token for {c_path}: {e}")

        def fetch_tag_list(proj_id_num, repo_id_num):
            try:
                res = requests.get(
                    f"{self.url.rstrip('/')}/api/v4/projects/{proj_id_num}/registry/repositories/{repo_id_num}/tags?per_page=100",
                    headers=headers, verify=False
                )
                if res.status_code == 200:
                    return proj_id_num, repo_id_num, res.json()
            except Exception:
                pass
            return proj_id_num, repo_id_num, []

        def fetch_tag_detail(proj_id_num, repo_id_num, tag_name, repo_registry_path, registry_token):
            try:
                res = requests.get(
                    f"{self.url.rstrip('/')}/api/v4/projects/{proj_id_num}/registry/repositories/{repo_id_num}/tags/{tag_name}",
                    headers=headers, verify=False
                )
                if res.status_code == 200:
                    tag_data = res.json()
                    revision = tag_data.get('revision')
                    if revision and registry_token and repo_registry_path:
                        domain = self.url.rstrip('/').replace("https://", "").replace("http://", "")
                        blob_url = f"https://{domain}:4567/v2/{repo_registry_path}/blobs/sha256:{revision}"
                        blob_headers = {"Authorization": f"Bearer {registry_token}"}
                        try:
                            blob_res = requests.get(blob_url, headers=blob_headers, verify=False)
                            if blob_res.status_code == 200:
                                blob = blob_res.json()
                                if blob.get('created'):
                                    tag_data['created_at'] = blob.get('created')
                            else:
                                logger.error(f"Failed to fetch blob for {repo_registry_path} {tag_name}: {blob_res.status_code} {blob_res.text}")
                        except Exception as e:
                            logger.error(f"Exception fetching blob for {repo_registry_path} {tag_name}: {e}")
                    return tag_data
            except Exception:
                pass
            return {"name": tag_name}
            
        def fetch_project_git_info(proj_id_num, containers_nodes, default_branch):
            try:
                project = gl.projects.get(proj_id_num)
                active_branches = {b.name: {"author_name": b.commit.get('author_name', 'Unknown'), "committed_date": b.commit.get('committed_date')} for b in project.branches.list(get_all=True)}
                active_git_tags = {gt.name: {"author_name": gt.commit.get('author_name', 'Unknown'), "committed_date": gt.commit.get('committed_date')} for gt in project.tags.list(get_all=True)}
                domain_services = self._discover_domain_services(project, containers_nodes, default_branch, active_branches)
                return proj_id_num, active_branches, active_git_tags, domain_services
            except Exception:
                return proj_id_num, {}, {}, []
            
        fetch_tasks = {}
        git_info_tasks = {}
        log_and_cb("Submitting tasks to fetch basic Git project information (branches, tags, domain services) and Container tag lists...")
        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
            for p in projects:
                proj_id = p.get('id', '').split('/')[-1]
                c_nodes = p.get('containerRepositories', {}).get('nodes', []) if p.get('containerRepositories') else []
                default_ref = (p.get('repository') or {}).get('rootRef') or 'main'
                git_info_tasks[executor.submit(fetch_project_git_info, proj_id, c_nodes, default_ref)] = proj_id
                for c in c_nodes:
                    c_name = c.get('name', '').lower()
                    if c_name in ['tmp', 'cache']:
                        continue
                        
                    if c.get('tagsCount', 0) > 0:
                        repo_id = c.get('id', '').split('/')[-1]
                        fetch_tasks[executor.submit(fetch_tag_list, proj_id, repo_id)] = c.get('id')
                        
            project_git_infos = {}
            for future in concurrent.futures.as_completed(git_info_tasks):
                proj_id, active_branches, active_git_tags, domain_services = future.result()
                project_git_infos[proj_id] = (active_branches, active_git_tags, domain_services)

            repo_tags = {}
            for future in concurrent.futures.as_completed(fetch_tasks):
                c_id = fetch_tasks[future]
                proj_id, repo_id, tags = future.result()
                repo_tags[c_id] = (proj_id, repo_id, tags)
        
        log_and_cb(f"Gathered tags for {len(repo_tags)} container repositories. Submitting detailed tag fetch tasks...")
        
        detail_tasks = {}
        tag_results = {}
        with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
            for c_id, (proj_id, repo_id, tags) in repo_tags.items():
                tag_results[c_id] = []
                repo_reg_path = c_id_to_repo_path.get(c_id)
                registry_token = registry_tokens.get(repo_reg_path) if repo_reg_path else None
                for t in tags:
                    tag_name = t.get('name')
                    if tag_name:
                        future = executor.submit(fetch_tag_detail, proj_id, repo_id, tag_name, repo_reg_path, registry_token)
                        detail_tasks[future] = c_id
                        
            for future in concurrent.futures.as_completed(detail_tasks):
                c_id = detail_tasks[future]
                tag_results[c_id].append(future.result())
        
        log_and_cb("All tag details fetched successfully. Constructing final inventory payload...")

        def build_enriched_container(c_node, active_branches, active_git_tags, native_release_tags, lookup_paths, service_prefix=None):
            c_name = c_node.get("name", "")
            c_path = c_node.get("path") or c_name
            c_id = c_node.get("id")
            tags = tag_results.get(c_id, [])
            try:
                tags = sorted(tags, key=lambda x: x.get('created_at', ''), reverse=True)
            except Exception:
                pass

            enriched_tags = []
            for t in tags:
                t_name = t.get("name")
                source_branch = "N/A"
                author = "Unknown"
                branch_exists = False
                is_git_tag = False

                for b_name, b_data in active_branches.items():
                    if t_name == b_name or t_name == b_name.replace('/', '-') or t_name == b_name.replace('.', '-'):
                        source_branch = b_name
                        author = b_data.get('author_name', 'Unknown')
                        branch_exists = True
                        break

                prefixed_t_dash = f"{service_prefix}-{t_name}" if service_prefix else None
                prefixed_t_slash = f"{service_prefix}/{t_name}" if service_prefix else None

                if not branch_exists:
                    for gt_name, gt_data in active_git_tags.items():
                        if (t_name == gt_name or t_name == gt_name.replace('/', '-') or
                            (prefixed_t_dash and gt_name == prefixed_t_dash) or
                            (prefixed_t_slash and gt_name == prefixed_t_slash)):
                            is_git_tag = True
                            author = gt_data.get('author_name', 'Unknown')
                            break

                for l_path in lookup_paths:
                    if l_path in audit_mapping.get('tags', {}):
                        for candidate_tag in [t_name, prefixed_t_dash, prefixed_t_slash]:
                            if candidate_tag and candidate_tag in audit_mapping['tags'][l_path]:
                                audit_source = audit_mapping['tags'][l_path][candidate_tag]
                                source_branch = audit_source
                                if audit_source in active_branches:
                                    branch_exists = True
                                    author = active_branches[audit_source].get('author_name', 'Unknown')
                                break

                if author.lower() in ['gia-ai', 'gia ai bot', 'unknown']:
                    for l_path in lookup_paths:
                        if l_path in audit_mapping.get('branches', {}) and source_branch in audit_mapping['branches'][l_path]:
                            author = audit_mapping['branches'][l_path][source_branch]
                            break

                has_native = (
                    t_name in native_release_tags or
                    (prefixed_t_dash and prefixed_t_dash in native_release_tags) or
                    (prefixed_t_slash and prefixed_t_slash in native_release_tags)
                )

                enriched_tags.append({
                    "name": t_name,
                    "created_at": t.get("created_at"),
                    "source_branch": source_branch,
                    "branch_exists": branch_exists,
                    "is_git_tag": is_git_tag,
                    "has_native_release": has_native,
                    "author": author
                })

            return {
                "name": c_path,
                "tags": enriched_tags
            }

        result = []
        for p in projects:
            proj_id = p.get('id', '').split('/')[-1]
            full_path = p.get("fullPath")
            active_branches, active_git_tags, domain_services = project_git_infos.get(proj_id, ({}, {}, []))
            native_release_tags = {r.get('tagName') for r in p.get('releases', {}).get('nodes', []) if r.get('tagName')}
            containers = p.get("containerRepositories", {}).get("nodes", []) if p.get("containerRepositories") else []

            def build_branch_list(lookup_paths):
                if active_branches:
                    b_list = []
                    for b, auth_data in active_branches.items():
                        author = auth_data.get('author_name', 'Unknown')
                        if author.lower() in ['gia-ai', 'gia ai bot', 'unknown']:
                            for l_path in lookup_paths:
                                if l_path in audit_mapping.get('branches', {}) and b in audit_mapping['branches'][l_path]:
                                    author = audit_mapping['branches'][l_path][b]
                                    break
                        b_list.append({"name": b, "author": author, "last_updated_at": auth_data.get('committed_date')})
                    return b_list
                else:
                    return [
                        {"name": b, "author": "Unknown"}
                        for b in (p.get("repository", {}).get("branchNames", []) if p.get("repository") else [])
                    ]

            if domain_services:
                # Multi-service Domain Monorepo: emit one virtual project per service
                c_by_name = {c.get("name"): c for c in containers if c.get("name")}
                for svc in domain_services:
                    svc_name = svc["service_name"]
                    subpath = svc["subpath"]
                    c_repo_name = svc["container_repo_name"]
                    virtual_full_path = f"{full_path}/{svc_name}"
                    lookup_paths = [virtual_full_path, full_path]

                    svc_containers = []
                    if c_repo_name in c_by_name:
                        c_node = c_by_name[c_repo_name]
                        if not c_node.get("path"):
                            c_node["path"] = f"{full_path}/{c_repo_name}"
                        svc_containers.append(
                            build_enriched_container(c_node, active_branches, active_git_tags, native_release_tags, lookup_paths, service_prefix=svc_name)
                        )

                    svc_native_releases = []
                    for rt in native_release_tags:
                        if rt.startswith(f"{svc_name}-"):
                            svc_native_releases.append(rt[len(svc_name) + 1:])
                        elif rt.startswith(f"{svc_name}/"):
                            svc_native_releases.append(rt[len(svc_name) + 1:])
                        elif len(domain_services) == 1:
                            svc_native_releases.append(rt)

                    result.append({
                        "name": svc_name,
                        "fullPath": virtual_full_path,
                        "repo_path": full_path,
                        "subpath": subpath,
                        "branches": build_branch_list(lookup_paths),
                        "native_releases": svc_native_releases,
                        "containers": svc_containers
                    })
            else:
                # Standard single-service repository
                lookup_paths = [full_path]
                proj_containers = []
                for c in containers:
                    c_name = c.get("name", "")
                    if c_name.lower() in ['tmp', 'cache']:
                        continue
                    if not c.get("path"):
                        c["path"] = f"{full_path}/{c_name}" if c_name else full_path
                    proj_containers.append(
                        build_enriched_container(c, active_branches, active_git_tags, native_release_tags, lookup_paths, service_prefix=None)
                    )

                result.append({
                    "name": p.get("name"),
                    "fullPath": full_path,
                    "repo_path": full_path,
                    "subpath": "",
                    "branches": build_branch_list(lookup_paths),
                    "native_releases": list(native_release_tags),
                    "containers": proj_containers
                })

        return json.dumps({"projects": result})