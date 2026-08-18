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

            deploy_info = active_counts.get(short_image, {})
            if deploy_info.get('count', 0) > 0:
                ns = ", ".join(deploy_info.get('namespaces', []))
                msg = f"SAFETY ABORT: Container '{short_image}' is actively deployed in namespaces: {ns}."

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

            logger.info(f"Verified container '{short_image}' is not actively deployed. Proceeding with deletion.")

        messages = []
        overall_success = True

        if container_tag:
            short_container_name = full_project_path.split('/')[-1]
            short_image = f"{short_container_name}:{container_tag}"
            messages.append(f"Safety Check: Verified container '{short_image}' is inactive.")

        if branch_name:
            success, msg = self.gitlab_manager.delete_branch(full_project_path, branch_name)
            messages.append(f"Branch: {msg}")
            if not success:
                overall_success = False

        if container_tag:
            success, msg = self.registry_manager.delete_container_tag(full_project_path, container_tag)
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