import requests
import json
import concurrent.futures
import gitlab
import logging
import urllib3
from core.io_handlers.sql_reader import SQLReader
from core.io_handlers.sql_writer import SQLWriter

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)

class GitInventoryManager:
    def __init__(self, config):
        self.config = config
        if 'external_services' in self.config and 'gitlab' in self.config['external_services']:
            self.url = self.config['external_services']['gitlab'].get('url')
            self.token = self.config['external_services']['gitlab'].get('bot_token')
        else:
            self.url = None
            self.token = None

    def sync_database_inventory(self, sql_reader: SQLReader, sql_writer: SQLWriter, project_name: str = None) -> str:
        audit_mapping = {'tags': {}, 'branches': {}}
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

        resolved_project_name = sql_reader.resolve_project_path(project_name) if project_name else None
        result_json = self.fetch_git_inventory_graphql(project_path=resolved_project_name, audit_mapping=audit_mapping)
        data = json.loads(result_json)
        sql_writer.upsert_git_inventory(data)
        return "Successfully synced Git Inventory to DB."

    def fetch_git_inventory_graphql(self, group_path="ai/halo", project_path=None, audit_mapping=None):
        if not self.url or not self.token:
            raise RuntimeError("GitLab config with URL and token is missing.")
            
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
                  branchNames(searchPattern: "*", offset: 0, limit: 50)
                }
                releases(first: 20, sort: RELEASED_AT_DESC) {
                  nodes {
                    tagName
                  }
                }
                containerRepositories(first: 5) {
                  nodes {
                    id
                    name
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
            except Exception as e:
                logger.error(f"Failed to fetch single project via GraphQL: {e}")
                raise RuntimeError(f"Failed to fetch git inventory for project: {e}")

        else:
            query = """
            query($groupPath: ID!, $afterCursor: String) {
              group(fullPath: $groupPath) {
                projects(includeSubgroups: true, first: 10, after: $afterCursor) {
                  pageInfo {
                    hasNextPage
                    endCursor
                  }
                  nodes {
                    id
                    name
                    fullPath
                    repository {
                      branchNames(searchPattern: "*", offset: 0, limit: 50)
                    }
                    releases(first: 20, sort: RELEASED_AT_DESC) {
                      nodes {
                        tagName
                      }
                    }
                    containerRepositories(first: 5) {
                      nodes {
                        id
                        name
                        tagsCount
                      }
                    }
                  }
                }
              }
            }
            """
            
            try:
                has_next_page = True
                after_cursor = None
                
                while has_next_page:
                    response = requests.post(
                        url, 
                        json={"query": query, "variables": {"groupPath": group_path, "afterCursor": after_cursor}}, 
                        headers=headers,
                        verify=False
                    )
                    response.raise_for_status()
                    data = response.json()
                    
                    if "errors" in data:
                        logger.error(f"GraphQL returned errors: {data['errors']}")
                        raise RuntimeError(f"GraphQL errors: {data['errors']}")
                        
                    group_data = data.get("data", {}).get("group")
                    if not group_data:
                        break
                        
                    projects_page = group_data.get("projects", {})
                    all_projects.extend(projects_page.get("nodes", []))
                    
                    page_info = projects_page.get("pageInfo", {})
                    has_next_page = page_info.get("hasNextPage", False)
                    after_cursor = page_info.get("endCursor")
            except Exception as e:
                logger.error(f"Failed to fetch group projects via GraphQL: {e}")
                raise RuntimeError(f"Failed to fetch git inventory for group: {e}")
                
        projects = all_projects
        
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

        def fetch_tag_detail(proj_id_num, repo_id_num, tag_name):
            try:
                res = requests.get(
                    f"{self.url.rstrip('/')}/api/v4/projects/{proj_id_num}/registry/repositories/{repo_id_num}/tags/{tag_name}",
                    headers=headers, verify=False
                )
                if res.status_code == 200:
                    return res.json()
            except Exception:
                pass
            return {"name": tag_name}
            
        def fetch_project_git_info(proj_id_num):
            try:
                project = gl.projects.get(proj_id_num)
                active_branches = {b.name: {"author_name": b.commit.get('author_name', 'Unknown'), "committed_date": b.commit.get('committed_date')} for b in project.branches.list(get_all=True)}
                active_git_tags = {gt.name: {"author_name": gt.commit.get('author_name', 'Unknown'), "committed_date": gt.commit.get('committed_date')} for gt in project.tags.list(get_all=True)}
                return proj_id_num, active_branches, active_git_tags
            except Exception:
                return proj_id_num, {}, {}
            
        fetch_tasks = {}
        git_info_tasks = {}
        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
            for p in projects:
                proj_id = p.get('id', '').split('/')[-1]
                git_info_tasks[executor.submit(fetch_project_git_info, proj_id)] = proj_id
                for c in p.get('containerRepositories', {}).get('nodes', []):
                    if c.get('tagsCount', 0) > 0:
                        repo_id = c.get('id', '').split('/')[-1]
                        fetch_tasks[executor.submit(fetch_tag_list, proj_id, repo_id)] = c.get('id')
                        
            project_git_infos = {}
            for future in concurrent.futures.as_completed(git_info_tasks):
                proj_id, active_branches, active_git_tags = future.result()
                project_git_infos[proj_id] = (active_branches, active_git_tags)

            repo_tags = {}
            for future in concurrent.futures.as_completed(fetch_tasks):
                c_id = fetch_tasks[future]
                proj_id, repo_id, tags = future.result()
                repo_tags[c_id] = (proj_id, repo_id, tags)
        
        detail_tasks = {}
        tag_results = {}
        with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
            for c_id, (proj_id, repo_id, tags) in repo_tags.items():
                tag_results[c_id] = []
                for t in tags:
                    tag_name = t.get('name')
                    if tag_name:
                        future = executor.submit(fetch_tag_detail, proj_id, repo_id, tag_name)
                        detail_tasks[future] = c_id
                        
            for future in concurrent.futures.as_completed(detail_tasks):
                c_id = detail_tasks[future]
                tag_results[c_id].append(future.result())
        
        result = []
        for p in projects:
            proj_id = p.get('id', '').split('/')[-1]
            active_branches, active_git_tags = project_git_infos.get(proj_id, ({}, {}))
            native_release_tags = {r.get('tagName') for r in p.get('releases', {}).get('nodes', []) if r.get('tagName')}
            
            if active_branches:
                branch_list = []
                for b, auth_data in active_branches.items():
                    author = auth_data.get('author_name', 'Unknown')
                    if author.lower() in ['gia-ai', 'gia ai bot', 'unknown']:
                        if p.get("fullPath") in audit_mapping.get('branches', {}) and b in audit_mapping['branches'][p.get("fullPath")]:
                            author = audit_mapping['branches'][p.get("fullPath")][b]
                    branch_list.append({"name": b, "author": author, "last_updated_at": auth_data.get('committed_date')})
            else:
                branch_list = [
                    {"name": b, "author": "Unknown"}
                    for b in (p.get("repository", {}).get("branchNames", []) if p.get("repository") else [])
                ]
                
            proj_info = {
                "name": p.get("name"),
                "fullPath": p.get("fullPath"),
                "branches": branch_list,
                "native_releases": list(native_release_tags),
                "containers": []
            }
            
            containers = p.get("containerRepositories", {}).get("nodes", []) if p.get("containerRepositories") else []
            for c in containers:
                c_name = c.get("name", "")
                c_id = c.get("id")
                
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
                        if t_name == b_name or t_name == b_name.replace('/', '-'):
                            source_branch = b_name
                            author = b_data.get('author_name', 'Unknown')
                            branch_exists = True
                            break
                            
                    if not branch_exists:
                        for gt_name, gt_data in active_git_tags.items():
                            if t_name == gt_name or t_name == gt_name.replace('/', '-'):
                                is_git_tag = True
                                author = gt_data.get('author_name', 'Unknown')
                                break
                                
                    full_path = p.get("fullPath")
                    if full_path in audit_mapping.get('tags', {}) and t_name in audit_mapping['tags'][full_path]:
                        audit_source = audit_mapping['tags'][full_path][t_name]
                        source_branch = audit_source
                        if audit_source in active_branches:
                            branch_exists = True
                            author = active_branches[audit_source].get('author_name', 'Unknown')
                            
                    if author.lower() in ['gia-ai', 'gia ai bot', 'unknown']:
                        if full_path in audit_mapping.get('branches', {}) and source_branch in audit_mapping['branches'][full_path]:
                            author = audit_mapping['branches'][full_path][source_branch]
                            
                    enriched_tags.append({
                        "name": t_name, 
                        "created_at": t.get("created_at"),
                        "source_branch": source_branch,
                        "branch_exists": branch_exists,
                        "is_git_tag": is_git_tag,
                        "has_native_release": t_name in native_release_tags,
                        "author": author
                    })
                    
                proj_info["containers"].append({
                    "name": c_name,
                    "tags": enriched_tags
                })
                
            result.append(proj_info)
            
        return json.dumps({"projects": result})