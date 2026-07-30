import logging
import functools
import json
import os
import subprocess
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
            logger.info(f"[{client_id}] RPC '{func.__name__}' invoked.")
            try:
                res = func(self, request, context)
                import inspect
                if inspect.isgenerator(res):
                    def stream_wrapper():
                        try:
                            yield from res
                        except Exception as e:
                            logger.error(f"[{client_id}] RPC '{func.__name__}' streaming failed: {e}")
                            yield response_class(success=False, message=str(e))
                    return stream_wrapper()
                return res
            except Exception as e:
                logger.error(f"[{client_id}] RPC '{func.__name__}' failed: {e}")
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
            result = self.gitlab_manager.sync_group_cache()
            
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
            orchestrator = InventoryOrchestrator(self.config, sql_writer)
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

    @handle_rpc(hau_pb2.SetTenantInternalResponse)
    def SetTenantInternal(self, request, context):
        from core.database.models import HaloTenant
        with self._get_db_session(write=True) as session:
            if not session:
                return hau_pb2.SetTenantInternalResponse(success=False, message="Database configuration is missing.")
            
            tenant = session.query(HaloTenant).filter_by(slug_name=request.tenant_slug).first()
            if not tenant:
                return hau_pb2.SetTenantInternalResponse(success=False, message=f"Tenant '{request.tenant_slug}' not found.")
            
            tenant.is_internal = request.is_internal
            tenant.is_internal_overridden = True
            
            return hau_pb2.SetTenantInternalResponse(success=True, message=f"Successfully set {request.tenant_slug} is_internal={request.is_internal}")

    @handle_rpc(hau_pb2.GenerateChangelogResponse)
    def GenerateChangelog(self, request, context):
        if not self.gitlab_manager:
            return hau_pb2.GenerateChangelogResponse(success=False, message="GitlabManager is not initialized.", changelog_yaml="")
            
        project_name = request.project_name
        branch_name = request.branch_name
        
        checkout_res = self.gitlab_manager.checkout_project_branch(project_name, branch_name)
        if "Failed" in checkout_res:
            return hau_pb2.GenerateChangelogResponse(success=False, message=checkout_res, changelog_yaml="")
            
        local_base = self.config['external_services']['gitlab']['local_clone_path']
        project_path = self.config['external_services']['gitlab']['project_path']
        rel_path = project_name
        if rel_path.startswith(project_path + "/"):
            rel_path = rel_path[len(project_path) + 1:]
            
        repo_local_path = os.path.join(local_base, rel_path)
        
        try:
            date_res = subprocess.run(
                ['git', 'log', '-1', '--format=%ad', '--date=short', 'HEAD'], 
                cwd=repo_local_path, capture_output=True, text=True
            )
            merge_date = date_res.stdout.strip() if date_res.returncode == 0 else "UNKNOWN"
            
            author_res = subprocess.run(
                ['git', 'log', '-1', '--format=%an', 'HEAD'], 
                cwd=repo_local_path, capture_output=True, text=True
            )
            merge_author = author_res.stdout.strip() if author_res.returncode == 0 else "UNKNOWN"
            
            if merge_author == "Gemini Agent":
                merge_author = "Scott Chrestman"
            if merge_author.endswith(" ADM"):
                merge_author = merge_author[:-4]
            elif merge_author.endswith(" PRV"):
                merge_author = merge_author[:-4]

            orchestrator = ChangelogOrchestrator(config=self.config)
            generator = orchestrator.generate_for_commits(
                repo_local_path=repo_local_path,
                start_commit='HEAD^1',
                end_commit='HEAD',
                author=merge_author,
                date_str=merge_date,
                version="UNKNOWN"
            )
            
            final_yaml = None
            for item in generator:
                if isinstance(item, dict) and "final_yaml" in item:
                    final_yaml = item["final_yaml"]
            
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
        
        try:
            for item in orchestrator.run_backfill(repo_local_path, request.branch_name, start_version, start_commit):
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
                author=request.author
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
                debug=request.debug
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
        if not self.gitlab_manager:
            return hau_pb2.GitInventorySyncResponse(success=False, message="GitlabManager is not initialized.")
            
        try:
            audit_mapping = {}
            with self._get_db_session(write=False) as session:
                if session:
                    reader = SQLReader(session)
                    logs = reader.get_successful_git_releases()
                    for log in logs:
                        if log.version_tag and log.project_name:
                            if log.project_name not in audit_mapping:
                                audit_mapping[log.project_name] = {}
                            audit_mapping[log.project_name][log.version_tag] = log.source_branch

            # Fetch live from Gitlab
            result_json = self.gitlab_manager.fetch_git_inventory_graphql(group_path="ai/halo", audit_mapping=audit_mapping)
            data = json.loads(result_json)
            
            # Upsert to DB
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
            import gitlab
            gl = gitlab.Gitlab(self.gitlab_manager.url, private_token=self.gitlab_manager.token, ssl_verify=False)
            project_client = gl.projects.get("ai/halo/deployment")
            
            project_name = request.project_name
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
                    import base64
                    docs[item['name']] = base64.b64decode(f.content).decode('utf-8')
            
            doc_msgs = [hau_pb2.Document(filename=name, raw_markdown=content) for name, content in docs.items()]
            return hau_pb2.GetDocumentationResponse(success=True, message="Fetched docs", documents=doc_msgs)
        except Exception as e:
            logger.error(f"Failed to fetch documentation for {request.project_name}: {e}")
            return hau_pb2.GetDocumentationResponse(success=False, message=str(e))