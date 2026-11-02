import logging
from typing import Dict, Any, Tuple
from core.orchestrators.inventory_orchestrator import InventoryOrchestrator
from core.io_handlers.sql_reader import SQLReader
from core.io_handlers.sql_writer import SQLWriter
from core.managers.git_inventory_manager import GitInventoryManager

logger = logging.getLogger(__name__)

class DeleteOrchestrator:
    def __init__(self, config: Dict[str, Any], gitlab_manager, registry_manager, vault_client=None):
        self.config = config
        self.gitlab_manager = gitlab_manager
        self.registry_manager = registry_manager
        self.vault_client = vault_client
        self.inventory_manager = GitInventoryManager(config)

    def run_delete(self, project_name: str, branch_name: str, container_tag: str, actor_name: str, sql_reader: SQLReader, sql_writer: SQLWriter) -> Tuple[bool, str]:
        if branch_name and not container_tag:
            container_tag = branch_name.replace('/', '-')

        if not branch_name and not container_tag:
            return False, "Must specify either branch_name or container_tag to delete."

        logger.info("Syncing inventory before deletion checks...")
        inv_orchestrator = InventoryOrchestrator(self.config, sql_writer, vault_client=self.vault_client)
        inv_orchestrator.sync_inventory()

        projects = sql_reader.get_git_project_by_name(project_name)

        if not projects:
            return False, f"Project '{project_name}' not found in local inventory."

        if len(projects) > 1:
            matched_paths = [p.project_path for p in projects]
            return False, f"Ambiguous project name '{project_name}'. Matched {len(projects)} projects: {', '.join(matched_paths)}. Please provide the full project path."

        full_project_path = projects[0].project_path
        repo_path = projects[0].repo_path or full_project_path
        project_id = projects[0].id

        if branch_name:
            branch_in_db = sql_reader.get_git_branch(project_id, branch_name)
            if not branch_in_db and '-' in branch_name:
                alt_name = branch_name.replace('-', '/', 1)
                alt_branch = sql_reader.get_git_branch(project_id, alt_name)
                if alt_branch:
                    branch_name = alt_name

        if container_tag:
            active_counts = sql_reader.get_active_deployments_counts()
            short_container_name = full_project_path.split('/')[-1]
            short_image = f"{short_container_name}:{container_tag}"
            full_image = f"{full_project_path}:{container_tag}"

            deploy_info = active_counts.get(full_image)
            if deploy_info is None and full_project_path.startswith("ai/halo/"):
                deploy_info = active_counts.get(short_image, {})
            deploy_info = deploy_info or {}
            if deploy_info.get('count', 0) > 0:
                ns = ", ".join(deploy_info.get('namespaces', []))
                msg = f"SAFETY ABORT: Container '{full_image}' is actively deployed in namespaces: {ns}."

                log = sql_writer.create_git_release_audit_log(
                    project_name=full_project_path,
                    action="DELETE",
                    actor=actor_name,
                    status="FAILED",
                    source_branch=branch_name,
                    target_branch=None,
                    merge_request_id=None,
                    version_tag=container_tag
                )
                sql_writer.update_git_release_audit_log(log.id, error_message=msg)
                return False, msg

            logger.info(f"Verified container '{full_image}' is not actively deployed. Proceeding with deletion.")

        messages = []
        overall_success = True

        if container_tag:
            full_image = f"{full_project_path}:{container_tag}"
            messages.append(f"Safety Check: Verified container '{full_image}' is inactive.")

        if branch_name:
            success, msg = self.gitlab_manager.delete_branch(repo_path, branch_name)
            messages.append(f"Branch: {msg}")
            if not success:
                overall_success = False

        if container_tag:
            success, msg = self.registry_manager.delete_container_tag(full_project_path, container_tag, repo_path=repo_path)
            messages.append(f"Container: {msg}")
            if not success:
                overall_success = False

        final_msg = "\n".join(messages)

        log = sql_writer.create_git_release_audit_log(
            project_name=full_project_path,
            action="DELETE",
            actor=actor_name,
            status="SUCCESS" if overall_success else "FAILED",
            source_branch=branch_name,
            target_branch=None,
            merge_request_id=None,
            version_tag=container_tag
        )
        if not overall_success:
            sql_writer.update_git_release_audit_log(log.id, error_message=final_msg)

        if overall_success:
            try:
                logger.info("Triggering post-delete Git Inventory Sync...")
                self.inventory_manager.sync_database_inventory(sql_reader, sql_writer, project_name)
                final_msg += "\nInventory: Successfully synced post-deletion."
            except Exception as e:
                logger.error(f"Failed to trigger post-delete inventory sync: {e}")
                final_msg += f"\nInventory Sync Warning: {e}"

        return overall_success, final_msg

    def run_cleanup(self, project_name: str, execute: bool, sql_reader: SQLReader, sql_writer: SQLWriter, progress_cb) -> None:
        def log_and_cb(msg):
            logger.info(msg)
            if progress_cb:
                progress_cb(msg)

        log_and_cb("Starting Git Cleanup automation...")
        log_and_cb(f"Syncing Git Inventory for '{project_name or 'all projects'}' to ensure fresh data...")
        try:
            self.inventory_manager.sync_database_inventory(sql_reader, sql_writer, project_name, progress_cb=progress_cb)
        except Exception as e:
            log_and_cb(f" ⚠️ Warning: Pre-cleanup Git Inventory sync failed: {e}")
            
        log_and_cb("Syncing K8s Inventory to accurately check active deployments...")
        inv_orchestrator = InventoryOrchestrator(self.config, sql_writer, vault_client=self.vault_client)
        inv_orchestrator.sync_inventory()
        
        log_and_cb("Fetching Git Inventory from database...")
        projects = sql_reader.get_git_inventory(project_name)
        if not projects:
            log_and_cb(f"No projects found for '{project_name}'.")
            return
            
        import gitlab
        gl = gitlab.Gitlab(self.gitlab_manager.url, private_token=self.gitlab_manager.token, ssl_verify=False)
        active_counts = sql_reader.get_active_deployments_counts()
        
        cleanup_performed = False
        
        for p in projects:
            p_name = p.get('name')
            p_path = p.get('path')
            repo_path = p.get('repo_path') or p_path
            subpath = p.get('subpath') or ""
            log_and_cb(f"\nAnalyzing project: {p_name} ({p_path})")
            
            try:
                gl_project = gl.projects.get(repo_path)
            except Exception as e:
                log_and_cb(f"Failed to fetch GitLab project {repo_path}: {e}")
                continue
                
            items_to_check = []
            
            for item in p.get('inventory', {}).get('features', []):
                items_to_check.append({
                    'type': 'feature',
                    'branch': item.get('branch'),
                    'tag': item.get('container_tag'),
                    'deployments': item.get('active_deployments', 0),
                    'timestamp': item.get('branch_last_updated') or item.get('container_created', 'unknown')
                })
                
            for item in p.get('inventory', {}).get('standalone_features', []):
                items_to_check.append({
                    'type': 'standalone container',
                    'branch': None,
                    'tag': item.get('tag'),
                    'deployments': item.get('active_deployments', 0),
                    'timestamp': item.get('created_at', 'unknown')
                })
                
            for item in p.get('inventory', {}).get('active_branches_without_containers', []):
                items_to_check.append({
                    'type': 'branch',
                    'branch': item.get('branch'),
                    'tag': None,
                    'deployments': 0,
                    'timestamp': item.get('last_updated_at', 'unknown')
                })
                
            for item in items_to_check:
                branch_name = item['branch']
                tag_name = item['tag']
                deployments = item['deployments']
                i_type = item['type']
                ts = item['timestamp']
                # Truncate timestamp to just the date (YYYY-MM-DD)
                short_ts = ts.split('T')[0] if 'T' in ts else ts
                
                check_name = branch_name or tag_name
                if not check_name: continue
                
                if deployments > 0:
                    log_and_cb(f" 🛡️ Skipping {i_type} '{check_name}' (Updated: {short_ts}): Actively deployed ({deployments} deployments).")
                    continue
                    
                # Search MRs
                mrs = []
                try:
                    mrs = gl_project.mergerequests.list(source_branch=check_name, state='merged', get_all=False)
                    if not mrs and '-' in check_name and not branch_name:
                        # Try with slash if it's a standalone container tag
                        alt_name = check_name.replace('-', '/', 1)
                        mrs = gl_project.mergerequests.list(source_branch=alt_name, state='merged', get_all=False)
                except Exception as e:
                    log_and_cb(f" ⚠️ Error checking MRs for {check_name}: {e}")
                    continue
                    
                if not mrs:
                    log_and_cb(f" 👻 Skipping {i_type} '{check_name}' (Updated: {short_ts}): No merged MR found.")
                    continue
                    
                mr = mrs[0]
                target_b = mr.target_branch
                merged_at = mr.merged_at
                
                # Check for new commits on the branch after the MR was merged
                if branch_name:
                    try:
                        branch = gl_project.branches.get(branch_name)
                        last_commit_at = branch.commit['created_at']
                        if last_commit_at > merged_at:
                            log_and_cb(f" 👻 Skipping {i_type} '{check_name}' (Updated: {short_ts}): Branch has new commits after it was merged to '{target_b}'.")
                            continue
                    except Exception as e:
                        # If we can't fetch the branch (maybe it was deleted), we assume it's safe if it has an MR
                        pass
                        
                action_str = "Would delete" if not execute else "Deleting"
                target_desc = []
                if branch_name: target_desc.append(f"branch '{branch_name}'")
                if tag_name: target_desc.append(f"container '{tag_name}'")
                
                log_and_cb(f" 🗑️ {action_str} {' and '.join(target_desc)} (Merged to {target_b} at {merged_at})")
                
                if execute:
                    overall_success = True
                    msg = []
                    if branch_name:
                        success, m = self.gitlab_manager.delete_branch(repo_path, branch_name)
                        if not success: overall_success = False
                        msg.append(f"Branch: {m}")
                    if tag_name:
                        success, m = self.registry_manager.delete_container_tag(p_path, tag_name, repo_path=repo_path)
                        if not success: overall_success = False
                        msg.append(f"Container: {m}")
                        
                    log = sql_writer.create_git_release_audit_log(
                        project_name=p_path,
                        action="DELETE",
                        actor="GitCleanupAutomation",
                        status="SUCCESS" if overall_success else "FAILED",
                        source_branch=branch_name,
                        version_tag=tag_name
                    )
                    if not overall_success:
                        sql_writer.update_git_release_audit_log(log.id, error_message=" | ".join(msg))
                        
                    cleanup_performed = True

        if execute and cleanup_performed:
            log_and_cb("Syncing Git Inventory post-cleanup...")
            self.inventory_manager.sync_database_inventory(sql_reader, sql_writer, project_name, progress_cb=progress_cb)
            
        log_and_cb("Cleanup completed successfully.")