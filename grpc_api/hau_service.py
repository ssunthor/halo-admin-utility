import logging
import functools
import json
import os
import subprocess
import re
import threading
from contextlib import contextmanager

import hau_pb2
import hau_pb2_grpc
from core.database.database import get_engine, get_session_factory
from core.io_handlers.sql_reader import SQLReader
from core.io_handlers.sql_writer import SQLWriter
from core.orchestrators.inventory_orchestrator import InventoryOrchestrator
from core.orchestrators.changelog_orchestrator import ChangelogOrchestrator
from core.orchestrators.release_orchestrator import ReleaseOrchestrator

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
        db_config = self.config.get('database', {})
        dsn = db_config.get('write_dsn') if write else db_config.get('read_dsn')
        if not dsn:
            yield None
        else:
            engine = get_engine(dsn)
            SessionFactory = get_session_factory(engine)
            session = SessionFactory()
            try:
                yield session
                if write:
                    session.commit()
            except Exception:
                if write:
                    session.rollback()
                raise
            finally:
                session.close()

class HauServiceServicer(hau_pb2_grpc.HauServiceServicer, DependencyProviderMixin):
    def __init__(self, config):
        self.config = config
        
        # Initialize Vault client and fetch Rancher tokens
        self.vault_client = None
        if 'vault_paths' in config and 'rancher_system' in config['vault_paths']:
            try:
                from core.clients.vault_client import VaultClient
                self.vault_client = VaultClient(config['external_services']['vault'])
                path = config['vault_paths']['rancher_system']
                clusters = self.vault_client.get_rancher_tokens(path=path)
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
            result = sql_reader.get_all_inventory(tenant_slug=request.tenant_slug)
            
            return hau_pb2.InventoryListResponse(success=True, message="Fetched inventory", result_json=json.dumps(result))

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
            success, message = sql_writer.update_tenant_customization(request.tenant_slug, **kwargs)
            return hau_pb2.UpdateTenantCustomizationResponse(success=success, message=message)

    @handle_rpc(hau_pb2.GenerateChangelogResponse)
    def GenerateChangelog(self, request, context):
        if not self.gitlab_manager:
            return hau_pb2.GenerateChangelogResponse(success=False, message="GitlabManager is not initialized.", changelog_yaml="")
            
        checkout_res = self.gitlab_manager.checkout_project_branch(request.project_name, request.branch_name)
        if "Failed" in checkout_res:
            return hau_pb2.GenerateChangelogResponse(success=False, message=checkout_res, changelog_yaml="")
            
        local_base = self.config['external_services']['gitlab']['local_clone_path']
        project_path = self.config['external_services']['gitlab']['project_path']
        rel_path = request.project_name
        if rel_path.startswith(project_path + "/"):
            rel_path = rel_path[len(project_path) + 1:]
            
        repo_local_path = os.path.join(local_base, rel_path)
        
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
        project_path = config['external_services']['gitlab']['project_path']
        
        rel_path = request.project_name
        if rel_path.startswith(project_path + "/"):
            rel_path = rel_path[len(project_path) + 1:]
            
        repo_local_path = os.path.join(local_base, rel_path)
        
        if not self.gitlab_manager:
            yield hau_pb2.GitBackfillResponse(success=False, message="GitlabManager is not initialized.", changelog_yaml="")
            return
            
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
                if isinstance(item, dict) and "final_yaml" in item:
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
            with self._get_db_session(write=False) as session:
                if not session:
                    return hau_pb2.GitAuditResponse(success=False, message="Database not configured")
                    
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
            logger.error(f"[GitAudit] Failed to fetch audit logs: {e}")
            return hau_pb2.GitAuditResponse(success=False, message=str(e))

    @handle_rpc(hau_pb2.GitInventorySyncResponse)
    def GitInventorySync(self, request, context):
        from core.managers.git_inventory_manager import GitInventoryManager
        inventory_manager = GitInventoryManager(self.config)
        
        if not inventory_manager.url or not inventory_manager.token:
            return hau_pb2.GitInventorySyncResponse(success=False, message="GitLab configuration is missing.")
            
        try:
            audit_mapping = {'tags': {}, 'branches': {}}
            with self._get_db_session(write=False) as session:
                if session:
                    reader = SQLReader(session)
                    logs = reader.get_successful_git_releases()
                    for log in logs:
                        if log.project_name:
                            if log.project_name not in audit_mapping['tags']:
                                audit_mapping['tags'][log.project_name] = {}
                            if log.project_name not in audit_mapping['branches']:
                                audit_mapping['branches'][log.project_name] = {}
                            
                            if log.version_tag and log.version_tag not in audit_mapping['tags'][log.project_name]:
                                audit_mapping['tags'][log.project_name][log.version_tag] = log.source_branch
                            if log.target_branch and log.target_branch not in audit_mapping['branches'][log.project_name]:
                                audit_mapping['branches'][log.project_name][log.target_branch] = log.actor

                    project_name = request.project_name if request.project_name else None
                    if project_name:
                        from core.database.models import GitProject
                        proj_in_db = session.query(GitProject).filter(
                            (GitProject.project_name == project_name) | 
                            (GitProject.project_path == project_name) |
                            (GitProject.project_path.like(f"%/{project_name}"))
                        ).first()
                        if proj_in_db:
                            project_name = proj_in_db.project_path
            result_json = inventory_manager.fetch_git_inventory_graphql(group_path="ai/halo", project_path=project_name, audit_mapping=audit_mapping)
            data = json.loads(result_json)
            
            with self._get_db_session(write=True) as session:
                if not session:
                    return hau_pb2.GitInventorySyncResponse(success=False, message="Database not available.")
                writer = SQLWriter(session)
                writer.upsert_git_inventory(data)
                
            return hau_pb2.GitInventorySyncResponse(success=True, message="Successfully synced Git Inventory to DB.")
        except Exception as e:
            logger.error(f"[GitInventorySync] Failed: {e}")
            return hau_pb2.GitInventorySyncResponse(success=False, message=str(e))


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
            
            if os.path.exists(cache_dir):
                for root, _, files in os.walk(cache_dir):
                    for file in files:
                        if file.endswith('.md'):
                            full_path = os.path.join(root, file)
                            rel_path = os.path.relpath(full_path, cache_dir)
                            project_name = rel_path.split(os.sep)[0] if os.sep in rel_path else "unknown"
                            with open(full_path, 'r', encoding='utf-8') as f:
                                content = f.read()
                            
                            # Parse frontmatter
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
                            
                            doc_msg = hau_pb2.HaloDocument(
                                filename=file,
                                raw_markdown=content,
                                doc_type=metadata["doc_type"],
                                category=metadata["category"],
                                name=metadata["name"],
                                acronym=metadata["acronym"],
                                version=metadata["version"],
                                author=metadata["author"],
                                status=metadata["status"],
                                date=metadata["date"],
                                relative_path=rel_path,
                                project_name=project_name
                            )
                            docs_list.append(doc_msg)
            else:
                logger.warning(f"Halo docs cache dir not found at {cache_dir}")

            # Fire and forget cache sync
            threading.Thread(target=self._sync_halo_cache).start()
            
            return hau_pb2.GetHaloDocumentationTreeResponse(success=True, message="Fetched halo docs tree", documents=docs_list)
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
        
        if branch_name and not container_tag:
            container_tag = branch_name.replace('/', '-')
        
        if not branch_name and not container_tag:
            return hau_pb2.GitDeleteResponse(success=False, message="Must specify either branch_name or container_tag to delete.")
            
        with self._get_db_session(write=True) as session:
            if not session:
                return hau_pb2.GitDeleteResponse(success=False, message="Database not available.")
            sql_writer = SQLWriter(session)
            
            logger.info("Syncing inventory before deletion checks...")
            orchestrator = InventoryOrchestrator(self.config, sql_writer, vault_client=self.vault_client)
            orchestrator.sync_inventory()
            
            from core.database.models import GitProject
            projects = session.query(GitProject).filter(
                (GitProject.project_path == project_name) | 
                (GitProject.project_path.like(f"%/{project_name}")) |
                (GitProject.project_name == project_name)
            ).all()
            
            if not projects:
                return hau_pb2.GitDeleteResponse(success=False, message=f"Project '{project_name}' not found in local inventory.")
                
            if len(projects) > 1:
                matched_paths = [p.project_path for p in projects]
                return hau_pb2.GitDeleteResponse(
                    success=False, 
                    message=f"Ambiguous project name '{project_name}'. Matched {len(projects)} projects: {', '.join(matched_paths)}. Please provide the full project path."
                )
                
            full_project_path = projects[0].project_path
            project_id = projects[0].id
            
            if branch_name:
                from core.database.models import GitBranch
                branch_in_db = session.query(GitBranch).filter_by(project_id=project_id, name=branch_name).first()
                if not branch_in_db and '-' in branch_name:
                    alt_name = branch_name.replace('-', '/', 1)
                    alt_branch = session.query(GitBranch).filter_by(project_id=project_id, name=alt_name).first()
                    if alt_branch:
                        branch_name = alt_name
            
            if container_tag:
                sql_reader = SQLReader(session)
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
                        actor=extract_client_id(context),
                        status="FAILED",
                        source_branch=branch_name,
                        target_branch=None,
                        merge_request_id=None
                    )
                    log.error_message = msg
                    session.commit()
                    return hau_pb2.GitDeleteResponse(success=False, message=msg)
                
                logger.info(f"Verified container '{short_image}' is not actively deployed. Proceeding with deletion.")
                    
        messages = []
        overall_success = True
        
        if container_tag:
            messages.append(f"Safety Check: Verified container '{short_image}' is inactive.")
        
        if branch_name:
            success, msg = self.gitlab_manager.delete_branch(full_project_path, branch_name)
            messages.append(f"Branch: {msg}")
            if not success:
                overall_success = False
                
        if container_tag:
            success, msg = registry_manager.delete_container_tag(full_project_path, container_tag)
            messages.append(f"Container: {msg}")
            if not success:
                overall_success = False
                
        final_msg = "\n".join(messages)
        
        with self._get_db_session(write=True) as session:
            sql_writer = SQLWriter(session)
            log = sql_writer.create_git_release_audit_log(
                project_name=full_project_path,
                action="DELETE",
                actor=extract_client_id(context),
                status="SUCCESS" if overall_success else "FAILED",
                source_branch=branch_name,
                target_branch=None,
                merge_request_id=None
            )
            if not overall_success:
                log.error_message = final_msg
            session.commit()
            
        if overall_success:
            try:
                logger.info("Triggering post-delete Git Inventory Sync...")
                sync_req = hau_pb2.GitInventorySyncRequest(project_name=request.project_name)
                sync_resp = self.GitInventorySync(sync_req, context)
                if sync_resp.success:
                    final_msg += "\nInventory: Successfully synced post-deletion."
                else:
                    final_msg += f"\nInventory Sync Warning: {sync_resp.message}"
            except Exception as e:
                logger.error(f"Failed to trigger post-delete inventory sync: {e}")
                final_msg += f"\nInventory Sync Warning: Failed to trigger sync ({e})"
                
        return hau_pb2.GitDeleteResponse(success=overall_success, message=final_msg)