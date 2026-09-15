import logging
import functools
import json
import os
import subprocess
import threading
from contextlib import contextmanager

import hau_pb2
import hau_pb2_grpc
from core.database.database import get_db_session
from core.io_handlers.sql_reader import SQLReader
from core.io_handlers.sql_writer import SQLWriter
from core.orchestrators.inventory_orchestrator import InventoryOrchestrator
from core.orchestrators.changelog_orchestrator import ChangelogOrchestrator
from core.orchestrators.release_orchestrator import ReleaseOrchestrator
from core.orchestrators.delete_orchestrator import DeleteOrchestrator

import datetime

logger = logging.getLogger(__name__)

def extract_client_id(context) -> str:
    if context:
        metadata = dict(context.invocation_metadata())
        return metadata.get('x-client-id', 'UNKNOWN')
    return 'UNKNOWN'

def handle_rpc(response_class):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(self, request, context):
            client_id = extract_client_id(context)
            
            target = ""
            if getattr(request, 'project_name', ""):
                target = request.project_name
            elif getattr(request, 'tenant_slug', ""):
                target = request.tenant_slug
            elif getattr(request, 'target', ""):
                target = request.target
            elif getattr(request, 'id', ""):
                target = f"id:{request.id}"
                
            target_info = f" (target='{target}')" if target else ""
            logger.info(f"[{client_id}] RPC '{func.__name__}' invoked{target_info}.")
            try:
                res = func(self, request, context)
                import inspect
                if inspect.isgenerator(res):
                    def stream_wrapper():
                        try:
                            has_error = False
                            for item in res:
                                if hasattr(item, 'success') and not item.success:
                                    logger.error(f"[{client_id}] RPC '{func.__name__}' yielded failure{target_info}: {getattr(item, 'message', 'Unknown error')}")
                                    has_error = True
                                yield item
                            if not has_error:
                                logger.info(f"[{client_id}] RPC '{func.__name__}' stream completed successfully{target_info}.")
                        except Exception as e:
                            logger.error(f"[{client_id}] RPC '{func.__name__}' streaming failed{target_info}: {e}")
                            yield response_class(success=False, message=str(e))
                    return stream_wrapper()
                
                if hasattr(res, 'success'):
                    if res.success:
                        logger.info(f"[{client_id}] RPC '{func.__name__}' completed successfully{target_info}.")
                    else:
                        logger.error(f"[{client_id}] RPC '{func.__name__}' failed{target_info}: {getattr(res, 'message', 'Unknown error')}")
                else:
                    logger.info(f"[{client_id}] RPC '{func.__name__}' completed successfully{target_info}.")
                    
                return res
            except Exception as e:
                logger.error(f"[{client_id}] RPC '{func.__name__}' failed{target_info}: {e}")
                return response_class(success=False, message=str(e))
        return wrapper
    return decorator

class DependencyProviderMixin:
    @contextmanager
    def _get_db_session(self, write=False):
        with get_db_session(read_only=not write) as session:
            yield session

class HauServiceServicer(hau_pb2_grpc.HauServiceServicer, DependencyProviderMixin):
    def __init__(self, config):
        self.config = config
        
        self.vault_client = None
        if 'vault_paths' in config and 'rancher_admin' in config['vault_paths']:
            try:
                from core.clients.vault_client import VaultClient
                self.vault_client = VaultClient(config['external_services']['vault'])
                path_template = config['vault_paths']['rancher_admin']
                locations = config.get('rancher_clusters', {}).keys()
                clusters = self.vault_client.get_rancher_tokens(path_template=path_template, locations=locations)
                if clusters:
                    for region, data in clusters.items():
                        if region in self.config.get('rancher_clusters', {}):
                            self.config['rancher_clusters'][region].update(data)
                    logger.info("Successfully loaded Rancher cluster tokens from Vault on startup.")
            except Exception as e:
                logger.error(f"Failed to load Rancher tokens from Vault: {e}")

        from core.managers.gitlab_manager import GitlabManager
        if 'external_services' in config and 'gitlab' in config['external_services']:
            self.gitlab_manager = GitlabManager(config['external_services']['gitlab'])
        else:
            logger.warning("Gitlab configuration not found in external_services.")
            self.gitlab_manager = None

    @handle_rpc(hau_pb2.GitContainersResponse)
    def GitContainers(self, request, context):
        try:
            with self._get_db_session(write=False) as session:
                if not session:
                    return hau_pb2.GitContainersResponse(success=False, message="Database not available.", result_json="[]")
                reader = SQLReader(session)
                all_tags = reader.get_git_containers()
            return hau_pb2.GitContainersResponse(success=True, message="Tags fetched from DB", result_json=json.dumps(all_tags))
        except Exception as e:
            logger.error(f"[GitContainers] DB fetch failed: {e}")
            return hau_pb2.GitContainersResponse(success=False, message=str(e), result_json="[]")

    @handle_rpc(hau_pb2.GitSyncResponse)
    def GitSync(self, request, context):
        if not self.gitlab_manager:
            return hau_pb2.GitSyncResponse(success=False, message="GitlabManager is not initialized.")
        
        if request.target == 'templates':
            project_path = "ai/gitlab-ci-templates"
            local_base = os.path.dirname(self.config['external_services']['gitlab']['local_clone_path'])
            local_path = os.path.join(local_base, 'gitlab-ci-templates')
            result = self.gitlab_manager.sync_local_repo(project_path, local_path)
        else:
            branch_override = getattr(request, 'branch', None)
            result = self.gitlab_manager.sync_group_cache(branch_override=branch_override)
            
        return hau_pb2.GitSyncResponse(success=True, message=result)

    @handle_rpc(hau_pb2.GitListCacheResponse)
    def GitListCache(self, request, context):
        if not self.gitlab_manager:
            return hau_pb2.GitListCacheResponse(success=False, message="GitlabManager is not initialized.", result_json="[]")
        
        result = self.gitlab_manager.list_group_cache()
        return hau_pb2.GitListCacheResponse(success=True, message="Success", result_json=result)

    @handle_rpc(hau_pb2.GitPushResponse)
    def GitPush(self, request, context):
        if not self.gitlab_manager:
            return hau_pb2.GitPushResponse(success=False, message="GitlabManager is not initialized.")
        
        result = self.gitlab_manager.push_group_cache(request.commit_message)
        return hau_pb2.GitPushResponse(success=True, message=result)

    @handle_rpc(hau_pb2.GitCheckoutResponse)
    def GitCheckout(self, request, context):
        if not self.gitlab_manager:
            return hau_pb2.GitCheckoutResponse(success=False, message="GitlabManager is not initialized.")
        
        result = self.gitlab_manager.checkout_project_branch(request.project_name, request.branch_name)
        return hau_pb2.GitCheckoutResponse(success=True, message=result)

    @handle_rpc(hau_pb2.InventorySyncResponse)
    def InventorySync(self, request, context):
        with self._get_db_session(write=True) as session:
            if not session:
                return hau_pb2.InventorySyncResponse(success=False, message="Database configuration is missing.")
            
            sql_writer = SQLWriter(session)
            orchestrator = InventoryOrchestrator(self.config, sql_writer, vault_client=self.vault_client)
            orchestrator.sync_inventory()
            
            return hau_pb2.InventorySyncResponse(success=True, message="Inventory sync complete.")

    @handle_rpc(hau_pb2.InventoryListResponse)
    def InventoryList(self, request, context):
        with self._get_db_session(write=False) as session:
            if not session:
                return hau_pb2.InventoryListResponse(success=False, message="Database configuration is missing.", result_json="{}")
            
            sql_reader = SQLReader(session)
            result = sql_reader.get_all_inventory(
                tenant_namespace=request.tenant_namespace,
                tenant=request.tenant,
                env=request.env
            )
            
            return hau_pb2.InventoryListResponse(success=True, message="Fetched inventory", result_json=json.dumps(result))

    @handle_rpc(hau_pb2.TenantListResponse)
    def TenantList(self, request, context):
        with self._get_db_session(write=False) as session:
            if not session:
                return hau_pb2.TenantListResponse(success=False, message="Database configuration is missing.")
            
            sql_reader = SQLReader(session)
            db_tenants = sql_reader.get_all_tenants(
                tenant_namespace=request.tenant_namespace,
                tenant=request.tenant,
                env=request.env
            )
            
            tenants_out = []
            for t in db_tenants:
                info = hau_pb2.TenantInfo(
                    id=t.id or "",
                    tenant_namespace=t.tenant_namespace or "",
                    tenant_acronym=t.tenant_acronym or "",
                    tenant_environment=t.tenant_environment or "",
                    target_cluster=t.target_cluster or "",
                    netbox_slug=t.netbox_slug or "",
                    tenant_category=t.customization.tenant_category if t.customization else "CUSTOMER",
                    tenant_tier=t.customization.tenant_tier if t.customization else "UNKNOWN",
                    update_policy=t.customization.update_policy if t.customization else "MANUAL_ONLY",
                    owner=t.customization.owner if t.customization else "UNASSIGNED",
                    purpose=t.customization.purpose if t.customization else "",
                    maintenance_window=t.customization.maintenance_window if t.customization else "",
                    url=t.url or "",
                    cmd_tenant_id=t.cmd_tenant_id or "",
                    cmd_group_id=t.cmd_group_id or "",
                    netbox_id=t.netbox_id or 0,
                    tenant_name=t.tenant_name or "",
                    tenant_group=t.tenant_group or "",
                    halo_version=t.halo_version or "",
                    lifecycle_state=t.lifecycle_state.value if t.lifecycle_state else "",
                    created_at=t.created_at.isoformat() if t.created_at else "",
                    updated_at=t.updated_at.isoformat() if t.updated_at else ""
                )
                tenants_out.append(info)
                
            return hau_pb2.TenantListResponse(success=True, message=f"Fetched {len(tenants_out)} tenants.", tenants=tenants_out)

    @handle_rpc(hau_pb2.InventoryDeleteOrphanedResponse)
    def InventoryDeleteOrphaned(self, request, context):
        with self._get_db_session(write=True) as session:
            if not session:
                return hau_pb2.InventoryDeleteOrphanedResponse(success=False, message="Database configuration is missing.")
            
            sql_writer = SQLWriter(session)
            count = sql_writer.delete_orphaned_tenants()
            
            return hau_pb2.InventoryDeleteOrphanedResponse(success=True, message=f"Deleted {count} orphaned/decommissioned tenants.")

    @handle_rpc(hau_pb2.UpdateTenantCustomizationResponse)
    def UpdateTenantCustomization(self, request, context):
        with self._get_db_session(write=True) as session:
            if not session:
                return hau_pb2.UpdateTenantCustomizationResponse(success=False, message="Database configuration is missing.")
            
            sql_writer = SQLWriter(session)
            kwargs = {
                "tenant_category": getattr(request, 'tenant_category', ""),
                "tenant_tier": getattr(request, 'tenant_tier', ""),
                "update_policy": getattr(request, 'update_policy', ""),
                "owner": getattr(request, 'owner', ""),
                "purpose": getattr(request, 'purpose', ""),
                "maintenance_window": getattr(request, 'maintenance_window', ""),
                "configuration_payload": getattr(request, 'configuration_payload', ""),
            }
            sql_reader = SQLReader(session)
            try:
                db_tenant = sql_reader.get_tenant(request.tenant_namespace, request.tenant, request.env)
            except ValueError as ve:
                return hau_pb2.UpdateTenantCustomizationResponse(success=False, message=str(ve))
                
            if not db_tenant:
                return hau_pb2.UpdateTenantCustomizationResponse(success=False, message="Tenant not found.")
                
            success, message = sql_writer.update_tenant_customization(db_tenant.tenant_namespace, **kwargs)
            return hau_pb2.UpdateTenantCustomizationResponse(success=success, message=message)

    @handle_rpc(hau_pb2.GenerateChangelogResponse)
    def GenerateChangelog(self, request, context):
        if not self.gitlab_manager:
            return hau_pb2.GenerateChangelogResponse(success=False, message="GitlabManager is not initialized.", changelog_yaml="")
            
        checkout_res = self.gitlab_manager.checkout_project_branch(request.project_name, request.branch_name)
        if "Failed" in checkout_res:
            return hau_pb2.GenerateChangelogResponse(success=False, message=checkout_res, changelog_yaml="")
            
        local_base = self.config['external_services']['gitlab']['local_clone_path']
        repo_local_path = self.gitlab_manager.resolve_local_repo_path(request.project_name, local_base)
        
        try:
            orchestrator = ChangelogOrchestrator(config=self.config)
            final_yaml = orchestrator.generate_from_branch(repo_local_path, request.branch_name, request.project_name)
            
            if not final_yaml:
                return hau_pb2.GenerateChangelogResponse(
                    success=True, 
                    message="No significant code changes or features detected.", 
                    changelog_yaml=""
                )
                
            return hau_pb2.GenerateChangelogResponse(
                success=True, 
                message="Changelog generated successfully.", 
                changelog_yaml=final_yaml
            )
        except Exception as e:
            return hau_pb2.GenerateChangelogResponse(
                success=False, 
                message=f"LLM generation failed: {str(e)}", 
                changelog_yaml=""
            )

    @handle_rpc(hau_pb2.GitBackfillResponse)
    def GitBackfillChangelog(self, request, context):
        config = self.config
        local_base = config['external_services']['gitlab']['local_clone_path']
        
        if not self.gitlab_manager:
            yield hau_pb2.GitBackfillResponse(success=False, message="GitlabManager is not initialized.", changelog_yaml="")
            return
            
        repo_local_path = self.gitlab_manager.resolve_local_repo_path(request.project_name, local_base)
            
        checkout_res = self.gitlab_manager.checkout_project_branch(request.project_name, request.branch_name)
        if "Failed" in checkout_res:
            yield hau_pb2.GitBackfillResponse(success=False, message=checkout_res, changelog_yaml="")
            return
            
        if not os.path.exists(repo_local_path):
            yield hau_pb2.GitBackfillResponse(
                success=False,
                message=f"Repository not found at {repo_local_path}",
                changelog_yaml=""
            )
            return
            
        orchestrator = ChangelogOrchestrator(config=self.config)
        start_version = request.start_version if request.start_version else "0.1.0"
        start_commit = request.start_commit if request.start_commit else None
        start_date = request.start_date if request.start_date else None
        
        try:
            for item in orchestrator.run_backfill(repo_local_path, request.branch_name, start_version, start_commit, start_date):
                if isinstance(item, dict):
                    if "incremental_yaml" in item:
                        yield hau_pb2.GitBackfillResponse(
                            success=True,
                            message="Incremental changelog update.",
                            changelog_yaml=item["incremental_yaml"]
                        )
                    elif "final_yaml" in item:
                        yield hau_pb2.GitBackfillResponse(
                            success=True,
                            message="Backfill complete.",
                            changelog_yaml=item["final_yaml"]
                        )
                else:
                    yield hau_pb2.GitBackfillResponse(
                        success=True,
                        message=str(item),
                        changelog_yaml=""
                    )
        except Exception as e:
            yield hau_pb2.GitBackfillResponse(
                success=False,
                message=f"Backfill failed: {str(e)}",
                changelog_yaml=""
            )

    @handle_rpc(hau_pb2.GitReleaseResponse)
    def GitRelease(self, request, context):
        if not self.gitlab_manager:
            yield hau_pb2.GitReleaseResponse(success=False, message="GitlabManager is not initialized.")
            return

        orchestrator = ReleaseOrchestrator(self.config, self.gitlab_manager)
        
        try:
            generator = orchestrator.run_release(
                project_name=request.project_name,
                source_branch=request.source_branch,
                target_branch=request.target_branch,
                skip_changelog=request.skip_changelog_generation,
                keep_branch=request.keep_branch,
                debug=request.debug,
                author=request.author,
                dry_run=request.dry_run
            )
            for item in generator:
                if isinstance(item, dict):
                    if "success" in item:
                        yield hau_pb2.GitReleaseResponse(success=item["success"], message=item["message"])
                    else:
                        yield hau_pb2.GitReleaseResponse(success=True, message=str(item))
                elif isinstance(item, str):
                    yield hau_pb2.GitReleaseResponse(success=True, message=item)
        except Exception as e:
            logger.error(f"[GitRelease] Orchestrator failed: {e}")
            yield hau_pb2.GitReleaseResponse(success=False, message=f"Release failed: {e}")

    @handle_rpc(hau_pb2.GitRetryResponse)
    def GitRetry(self, request, context):
        try:
            logger.info(f"Received GitRetry request for pipeline {request.pipeline_id} / MR {request.merge_id} on {request.project_name}")
            orchestrator = ReleaseOrchestrator(self.config, self.gitlab_manager)
            generator = orchestrator.run_retry(
                project_name=request.project_name,
                pipeline_id=request.pipeline_id,
                merge_id=request.merge_id,
                skip_warnings=request.skip_warnings,
                debug=request.debug,
                author=request.author
            )
            for item in generator:
                if isinstance(item, dict):
                    if "success" in item:
                        yield hau_pb2.GitRetryResponse(success=item["success"], message=item["message"])
                    else:
                        yield hau_pb2.GitRetryResponse(success=True, message=str(item))
                elif isinstance(item, str):
                    yield hau_pb2.GitRetryResponse(success=True, message=item)
        except Exception as e:
            logger.error(f"[GitRetry] Orchestrator failed: {e}")
            yield hau_pb2.GitRetryResponse(success=False, message=f"Retry failed: {e}")

    @handle_rpc(hau_pb2.GitAuditResponse)
    def GitAudit(self, request, context):
        try:
            with self._get_db_session(write=True) as session:
                if not session:
                    return hau_pb2.GitAuditResponse(success=False, message="Database not configured")
                    
                if getattr(request, 'delete', False) and request.id:
                    writer = SQLWriter(session)
                    success = writer.delete_git_audit_log(request.id)
                    if success:
                        return hau_pb2.GitAuditResponse(success=True, message=f"Deleted audit log {request.id}")
                    else:
                        return hau_pb2.GitAuditResponse(success=False, message=f"Audit log {request.id} not found")

                reader = SQLReader(session)
                result = reader.get_git_audit_logs(
                    limit=50,
                    audit_id=request.id if request.id else None,
                    project_name=request.project_name if request.project_name else None
                )
                    
                return hau_pb2.GitAuditResponse(
                    success=True, 
                    message=f"Found {len(result)} audit logs", 
                    result_json=json.dumps(result)
                )
        except Exception as e:
            logger.error(f"[GitAudit] Failed to process audit logs: {e}")
            return hau_pb2.GitAuditResponse(success=False, message=str(e))

    # Notice: Removing @handle_rpc because this is now a streaming RPC
    def GitInventorySync(self, request, context):
        from core.managers.git_inventory_manager import GitInventoryManager
        inventory_manager = GitInventoryManager(self.config)
        
        if not inventory_manager.url or not inventory_manager.token:
            yield hau_pb2.GitInventorySyncResponse(success=False, message="GitLab configuration is missing.")
            return
            
        import queue
        import threading
        q = queue.Queue()
        
        def cb(msg):
            q.put(msg)
            
        def run_sync():
            try:
                with self._get_db_session(write=True) as session:
                    if not session:
                        q.put(Exception("Database not available."))
                        return
                    reader = SQLReader(session)
                    writer = SQLWriter(session)
                    inventory_manager.sync_database_inventory(reader, writer, request.project_name, progress_cb=cb)
                q.put(True)
            except Exception as e:
                logger.error(f"[GitInventorySync] Failed: {e}")
                q.put(e)
                
        t = threading.Thread(target=run_sync)
        t.start()
        
        while True:
            item = q.get()
            if item is True:
                yield hau_pb2.GitInventorySyncResponse(success=True, message="Successfully synced Git Inventory to DB.")
                break
            elif isinstance(item, Exception):
                yield hau_pb2.GitInventorySyncResponse(success=False, message=str(item))
                break
            else:
                yield hau_pb2.GitInventorySyncResponse(success=True, message=str(item))

    @handle_rpc(hau_pb2.GitInventoryResponse)
    def GitInventory(self, request, context):
        try:
            with self._get_db_session(write=False) as session:
                if not session:
                    return hau_pb2.GitInventoryResponse(success=False, message="Database not available.", result_json="[]")
                reader = SQLReader(session)
                result = reader.get_git_inventory(request.project_name)
            return hau_pb2.GitInventoryResponse(success=True, message="Fetched from DB", result_json=json.dumps({"projects": result}))
        except Exception as e:
            logger.error(f"[GitInventory] DB fetch failed: {e}")
            return hau_pb2.GitInventoryResponse(success=False, message=str(e), result_json="[]")

    @handle_rpc(hau_pb2.GetChangelogResponse)
    def GetChangelog(self, request, context):
        if not self.gitlab_manager:
            return hau_pb2.GetChangelogResponse(success=False, message="GitlabManager not init.")
        try:
            project = request.project_name
            try:
                file_path = f"docs/{project}/CHANGELOG.yaml"
                raw_yaml = self.gitlab_manager.fetch_raw_yaml("ai/halo/deployment", file_path)
            except Exception as e:
                if "404" in str(e):
                    normalized_project = project.lower().replace(" ", "-")
                    file_path = f"docs/{normalized_project}/CHANGELOG.yaml"
                    raw_yaml = self.gitlab_manager.fetch_raw_yaml("ai/halo/deployment", file_path)
                else:
                    raise e
            return hau_pb2.GetChangelogResponse(success=True, message="Fetched changelog", raw_yaml_changelog=raw_yaml)
        except Exception as e:
            logger.error(f"Failed to fetch changelog for {request.project_name}: {e}")
            return hau_pb2.GetChangelogResponse(success=False, message=str(e))

    @handle_rpc(hau_pb2.GetDocumentationResponse)
    def GetDocumentation(self, request, context):
        if not self.gitlab_manager:
            return hau_pb2.GetDocumentationResponse(success=False, message="GitlabManager not init.")
            
        try:
            docs = self.gitlab_manager.fetch_documentation(request.project_name)
            doc_msgs = [hau_pb2.Document(filename=name, raw_markdown=content) for name, content in docs.items()]
            return hau_pb2.GetDocumentationResponse(success=True, message="Fetched docs", documents=doc_msgs)
        except Exception as e:
            logger.error(f"Failed to fetch documentation for {request.project_name}: {e}")
            return hau_pb2.GetDocumentationResponse(success=False, message=str(e))

    def _sync_halo_cache(self):
        try:
            cache_dir = os.path.join(self.config.get("paths", {}).get("git_cache_dir", "/ai/utilities/halo_admin_utility/cache"), "halo", "deployment")
            import subprocess
            subprocess.run(["git", "pull", "origin", "main"], cwd=cache_dir, check=True)
            logger.info("Successfully synced halo documentation cache.")
        except Exception as e:
            logger.error(f"Background git pull failed in {cache_dir}: {e}")

    @handle_rpc(hau_pb2.GetHaloDocumentationTreeResponse)
    def GetHaloDocumentationTree(self, request, context):
        try:
            cache_dir = os.path.join(self.config.get("paths", {}).get("git_cache_dir", "/ai/utilities/halo_admin_utility/cache"), "halo", "deployment", "docs")
            
            docs_list = []
            if self.gitlab_manager:
                docs_list = self.gitlab_manager.parse_local_documentation_tree(cache_dir)
            
            import hau_pb2
            doc_msgs = []
            for doc in docs_list:
                doc_msgs.append(hau_pb2.HaloDocument(**doc))

            threading.Thread(target=self._sync_halo_cache).start()
            
            return hau_pb2.GetHaloDocumentationTreeResponse(success=True, message="Fetched halo docs tree", documents=doc_msgs)
        except Exception as e:
            logger.error(f"Failed to fetch halo documentation tree: {e}")
            return hau_pb2.GetHaloDocumentationTreeResponse(success=False, message=str(e))

    @handle_rpc(hau_pb2.GitDeleteResponse)
    def GitDelete(self, request, context):
        if not self.gitlab_manager:
            return hau_pb2.GitDeleteResponse(success=False, message="GitlabManager is not initialized.")
        from core.managers.container_registry_manager import ContainerRegistryManager
        registry_manager = ContainerRegistryManager(self.config)
        
        project_name = request.project_name
        branch_name = getattr(request, 'branch_name', None)
        container_tag = getattr(request, 'container_tag', None)
        
        actor_name = getattr(request, 'author', None)
        if not actor_name or actor_name == "Unknown":
            actor_name = extract_client_id(context)
            
        with self._get_db_session(write=True) as session:
            if not session:
                return hau_pb2.GitDeleteResponse(success=False, message="Database not available.")
            sql_writer = SQLWriter(session)
            sql_reader = SQLReader(session)
            
            orchestrator = DeleteOrchestrator(self.config, self.gitlab_manager, registry_manager, self.vault_client)
            success, message = orchestrator.run_delete(project_name, branch_name, container_tag, actor_name, sql_reader, sql_writer)
            
            return hau_pb2.GitDeleteResponse(success=success, message=message)

    def GitCleanup(self, request, context):
        if not self.gitlab_manager:
            yield hau_pb2.GitCleanupResponse(success=False, message="GitlabManager is not initialized.")
            return
            
        import queue
        import threading
        q = queue.Queue()
        
        def cb(msg):
            q.put(msg)
            
        def run_cleanup():
            try:
                with self._get_db_session(write=True) as session:
                    if not session:
                        q.put(Exception("Database not available."))
                        return
                    
                    from core.orchestrators.delete_orchestrator import DeleteOrchestrator
                    from core.managers.container_registry_manager import ContainerRegistryManager
                    registry_manager = ContainerRegistryManager(self.config)
                    sql_reader = SQLReader(session)
                    sql_writer = SQLWriter(session)
                    
                    orchestrator = DeleteOrchestrator(self.config, self.gitlab_manager, registry_manager, self.vault_client)
                    orchestrator.run_cleanup(request.project_name, request.execute, sql_reader, sql_writer, cb)
                    
                q.put(True)
            except Exception as e:
                logger.error(f"[GitCleanup] Failed: {e}", exc_info=True)
                q.put(e)
                
        t = threading.Thread(target=run_cleanup)
        t.start()
        
        while True:
            item = q.get()
            if item is True:
                yield hau_pb2.GitCleanupResponse(success=True, message="Cleanup completed successfully.")
                break
            elif isinstance(item, Exception):
                yield hau_pb2.GitCleanupResponse(success=False, message=str(item))
                break
            else:
                yield hau_pb2.GitCleanupResponse(success=True, message=str(item))

    @handle_rpc(hau_pb2.ListFeaturesResponse)
    def ListFeatures(self, request, context):
        try:
            with self._get_db_session(write=False) as session:
                if not session:
                    return hau_pb2.ListFeaturesResponse(success=False, message="Database not available.", features=[])
                reader = SQLReader(session)
                features = reader.get_feature_catalog()
                
                feature_entries = []
                for f in features:
                    entry = hau_pb2.FeatureCatalogEntry(
                        id=f.id,
                        feature_name=f.feature_name,
                        description=f.description or "",
                        product_category=f.product_category or "",
                        ui_grouping=f.ui_grouping or "",
                        env_variable=f.env_variable,
                        gitops_dependencies_json=json.dumps(f.gitops_dependencies),
                        pricing_tiers_json=json.dumps(f.pricing_tiers) if f.pricing_tiers else "{}",
                        is_paid_addon=f.is_paid_addon,
                        enabled_by_default=f.enabled_by_default
                    )
                    feature_entries.append(entry)
                
            return hau_pb2.ListFeaturesResponse(success=True, message="Fetched features from DB", features=feature_entries)
        except Exception as e:
            logger.error(f"[ListFeatures] DB fetch failed: {e}")
            return hau_pb2.ListFeaturesResponse(success=False, message=str(e), features=[])

    @handle_rpc(hau_pb2.UpsertFeatureResponse)
    def UpsertFeature(self, request, context):
        try:
            with self._get_db_session(write=True) as session:
                if not session:
                    return hau_pb2.UpsertFeatureResponse(success=False, message="Database not available.")
                writer = SQLWriter(session)
                
                gitops_deps = {}
                if request.gitops_dependencies_json:
                    try:
                        gitops_deps = json.loads(request.gitops_dependencies_json)
                    except json.JSONDecodeError:
                        return hau_pb2.UpsertFeatureResponse(success=False, message="Invalid JSON for gitops_dependencies_json")
                
                pricing = {}
                if getattr(request, 'pricing_tiers_json', None):
                    try:
                        pricing = json.loads(request.pricing_tiers_json)
                    except json.JSONDecodeError:
                        return hau_pb2.UpsertFeatureResponse(success=False, message="Invalid JSON for pricing_tiers_json")
                
                f = writer.upsert_feature(
                    feature_name=request.feature_name,
                    env_variable=request.env_variable,
                    description=request.description,
                    product_category=request.product_category,
                    ui_grouping=request.ui_grouping,
                    gitops_dependencies=gitops_deps,
                    pricing_tiers=pricing,
                    is_paid_addon=request.is_paid_addon,
                    enabled_by_default=request.enabled_by_default
                )
                
                entry = hau_pb2.FeatureCatalogEntry(
                    id=f.id,
                    feature_name=f.feature_name,
                    description=f.description or "",
                    product_category=f.product_category or "",
                    ui_grouping=f.ui_grouping or "",
                    env_variable=f.env_variable,
                    gitops_dependencies_json=json.dumps(f.gitops_dependencies),
                    pricing_tiers_json=json.dumps(f.pricing_tiers) if f.pricing_tiers else "{}",
                    is_paid_addon=f.is_paid_addon,
                    enabled_by_default=f.enabled_by_default
                )
                
            return hau_pb2.UpsertFeatureResponse(success=True, message="Successfully upserted feature", feature=entry)
        except Exception as e:
            logger.error(f"[UpsertFeature] DB upsert failed: {e}")
            return hau_pb2.UpsertFeatureResponse(success=False, message=str(e))

    @handle_rpc(hau_pb2.NetboxAuditTenantResponse)
    def NetboxAuditTenant(self, request, context):
        try:
            from core.managers.netbox_audit_manager import NetboxAuditManager
            
            with self._get_db_session(write=False) as session:
                if not session:
                    return hau_pb2.NetboxAuditTenantResponse(success=False, message="Database not available.")
                sql_reader = SQLReader(session)
                try:
                    db_tenant = sql_reader.get_tenant(request.tenant_namespace, request.tenant, request.env)
                except ValueError as ve:
                    return hau_pb2.NetboxAuditTenantResponse(success=False, message=str(ve))
                    
                if not db_tenant:
                    return hau_pb2.NetboxAuditTenantResponse(success=False, message="Tenant not found.")
                
                target_slug = db_tenant.netbox_slug or db_tenant.tenant_acronym
            
            manager = NetboxAuditManager(self.config)
            result = manager.audit_tenant(target_slug, request.ip_audit)
            
            return hau_pb2.NetboxAuditTenantResponse(
                success=True,
                message="Audit completed",
                result_json=json.dumps(result)
            )
        except Exception as e:
            logger.error(f"[NetboxAuditTenant] Failed: {e}")
            return hau_pb2.NetboxAuditTenantResponse(success=False, message=str(e))

    @handle_rpc(hau_pb2.DeployTenantScaffoldResponse)
    def DeployTenantScaffold(self, request, context):
        try:
            with self._get_db_session(write=True) as session:
                if not session:
                    yield hau_pb2.DeployTenantScaffoldResponse(success=False, message="Database not available.")
                    return
                
                sql_writer = SQLWriter(session)
                from core.orchestrators.scaffold_orchestrator import ScaffoldOrchestrator
                orchestrator = ScaffoldOrchestrator(self.config, sql_writer)
                
                image_selections = dict(request.image_selections) if request.image_selections else {}
                variables = dict(request.variables) if request.variables else {}
                
                for msg in orchestrator.scaffold_tenant(
                    tenant=request.tenant,
                    env=request.env,
                    region=request.region,
                    target_cluster=request.target_cluster,
                    image_selections=image_selections,
                    variables=variables,
                    is_internal=request.is_internal,
                    netbox_slug=request.netbox_slug
                ):
                    if msg.startswith("__DONE__:"):
                        repo_path = msg.replace("__DONE__:", "")
                        yield hau_pb2.DeployTenantScaffoldResponse(
                            success=True,
                            message=f"Successfully scaffolded {request.tenant} into {repo_path}"
                        )
                    else:
                        yield hau_pb2.DeployTenantScaffoldResponse(
                            success=True,
                            message=msg
                        )
        except Exception as e:
            logger.error(f"Failed to scaffold tenant: {e}", exc_info=True)
            yield hau_pb2.DeployTenantScaffoldResponse(
                success=False,
                message=f"Scaffolding failed: {str(e)}"
            )

    @handle_rpc(hau_pb2.DecommissionTenantResponse)
    def DecommissionTenant(self, request, context):
        try:
            with self._get_db_session(write=True) as session:
                if not session:
                    yield hau_pb2.DecommissionTenantResponse(success=False, message="Database not available.")
                    return
                
                sql_writer = SQLWriter(session)
                from core.orchestrators.decommission_orchestrator import DecommissionOrchestrator
                orchestrator = DecommissionOrchestrator(self.config, sql_writer)
                
                for msg in orchestrator.decommission_tenant(
                    tenant=request.tenant,
                    env=request.env,
                    region=request.region
                ):
                    if msg == "__DONE__":
                        yield hau_pb2.DecommissionTenantResponse(
                            success=True,
                            message=f"Successfully decommissioned {request.tenant}"
                        )
                    else:
                        yield hau_pb2.DecommissionTenantResponse(
                            success=True,
                            message=msg
                        )
        except Exception as e:
            logger.error(f"Failed to decommission tenant: {e}", exc_info=True)
            yield hau_pb2.DecommissionTenantResponse(
                success=False,
                message=f"Decommission failed: {str(e)}"
            )

    @handle_rpc(hau_pb2.GetBaseSchemaResponse)
    def GetBaseSchema(self, request, context):
        try:
            import yaml
            import os
            
            # For now we only care about backend and redis
            is_vendor = (request.component == 'redis')
            base_dir = "vendor" if is_vendor else "halo"
            
            repo_path = self.config.get('git_workspace', '/ai/utilities/halo_admin_utility/cache/halo/deployment')
            schema_path = os.path.join(repo_path, 'base', base_dir, request.component, 'schema.yaml')
            
            if not os.path.exists(schema_path):
                return hau_pb2.GetBaseSchemaResponse(success=False, message=f"Schema not found for component {request.component}")
                
            with open(schema_path, 'r') as f:
                schema_yaml = f.read()
                
            return hau_pb2.GetBaseSchemaResponse(
                success=True,
                message="Schema found",
                schema_yaml=schema_yaml
            )
        except Exception as e:
            logger.error(f"[GetBaseSchema] Failed: {e}")
            return hau_pb2.GetBaseSchemaResponse(success=False, message=str(e))