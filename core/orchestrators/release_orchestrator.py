import os
import logging
import subprocess
import yaml
import re
from packaging.version import parse as parse_version
from typing import Dict, Any, Generator
from datetime import datetime

from core.orchestrators.changelog_orchestrator import ChangelogOrchestrator
from core.llm_interface import vLLMClient
from prompts.git_commit_prompt import GIT_COMMIT_PROMPT
from core.database.database import get_engine, get_session_factory
from core.database.models import GitReleaseAuditLog

logger = logging.getLogger(__name__)

class ReleaseOrchestrator:
    def __init__(self, config: Dict[str, Any], gitlab_manager):
        self.config = config
        self.gitlab_manager = gitlab_manager
        db_config = self.config.get('database', {})
        dsn = db_config.get('write_dsn')
        self.Session = None
        if dsn:
            engine = get_engine(dsn)
            self.Session = get_session_factory(engine)

    def run_release(self, project_name: str, source_branch: str, target_branch: str, 
                    skip_changelog: bool, keep_branch: bool, debug: bool = False, author: str = None) -> Generator[Any, None, None]:
        
        if not self.gitlab_manager:
            raise RuntimeError("GitlabManager is not initialized.")
            
        audit_log = None
        session = None
        
        if self.Session:
            try:
                session = self.Session()
                active_lock = session.query(GitReleaseAuditLog).filter_by(
                    project_name=project_name, 
                    status="RUNNING"
                ).first()
                
                if active_lock:
                    msg = f"⚠️ WARNING: A release (Action: {active_lock.action}) is already currently running for {project_name} by {active_lock.actor}. Please wait for it to finish."
                    yield {"success": False, "message": msg}
                    session.close()
                    return
                    
                audit_log = GitReleaseAuditLog(
                    project_name=project_name,
                    action="GIT_RELEASE",
                    actor="gia-ai",
                    status="RUNNING",
                    source_branch=source_branch,
                    target_branch=target_branch,
                    changelog_generation_method="N/A",
                    merged_features_json={},
                    job_details_json={}
                )
                session.add(audit_log)
                session.commit()
            except Exception as e:
                logger.error(f"[GitRelease] Failed to acquire DB lock: {e}")
                if session:
                    session.rollback()

        try:
            for item in self._run_release_internal(project_name, source_branch, target_branch, skip_changelog, keep_branch, debug, audit_log, author, session):
                if isinstance(item, dict) and not item.get("success", True):
                    if audit_log:
                        audit_log.status = "FAILED"
                        audit_log.error_message = item.get("message", "Unknown error occurred.")
                        if session: session.commit()
                yield item
        except Exception as e:
            if audit_log:
                audit_log.status = "FAILED"
                audit_log.error_message = f"Unhandled Exception: {str(e)}"
                if session: session.commit()
            logger.error(f"[GitRelease] Unhandled Exception: {e}", exc_info=True)
            raise e
        finally:
            if session and audit_log:
                try:
                    if audit_log.status == "RUNNING":
                        audit_log.status = "FAILED"
                        audit_log.error_message = "Orchestration aborted unexpectedly or connection dropped."
                    session.commit()
                    session.close()
                except Exception:
                    pass

    def _run_release_internal(self, project_name, source_branch, target_branch, skip_changelog, keep_branch, debug, audit_log, author, session):
        yield f"Starting release: {source_branch} -> {target_branch}"
        
        if session:
            previous_release = session.query(GitReleaseAuditLog).filter_by(
                project_name=project_name,
                source_branch=source_branch,
                target_branch=target_branch,
                status="SUCCESS",
                action="GIT_RELEASE"
            ).order_by(GitReleaseAuditLog.timestamp.desc()).first()
            
            if previous_release:
                yield f"⚠️ WARNING: A successful release for '{source_branch}' -> '{target_branch}' was already recorded on {previous_release.timestamp.strftime('%Y-%m-%d %H:%M:%S')}. Proceeding anyway in case of new commits..."

        author_name = self.config.get('external_services', {}).get('gitlab', {}).get('bot_username', 'GIA AI Bot')
        author_email = "gia-ai@gtt.net"
        author_id = None
        if author:
            resolved = self.gitlab_manager.resolve_user(project_name, author)
            if resolved and 'name' in resolved:
                author_name = resolved['name']
                author_email = resolved.get('email', f"{resolved['username']}@gtt.net")
                author_id = resolved.get('id')
                yield f"✅ Mapped author override '{author}' to GitLab user: {author_name} ({author_email})"
            else:
                msg = f"❌ Could not resolve author '{author}' in GitLab project members or users."
                yield {"success": False, "message": msg}
                return
        
        try:
            import gitlab
            gl = gitlab.Gitlab(self.gitlab_manager.url, private_token=self.gitlab_manager.token, ssl_verify=False)
            project = gl.projects.get(project_name)
            
            try:
                compare = project.repository_compare(target_branch, source_branch)
                if not compare.get('commits'):
                    msg = f"❌ Aborting release: No new commits found in '{source_branch}' compared to '{target_branch}'. Branch is already merged."
                    logger.warning(f"[GitRelease] {msg}")
                    yield {"success": False, "message": msg}
                    return
            except Exception as e:
                logger.warning(f"[GitRelease] Failed to compare branches via API: {e}")

            running_pipelines = project.pipelines.list(status='running', ref=source_branch) + project.pipelines.list(status='running', ref=target_branch)
            pending_pipelines = project.pipelines.list(status='pending', ref=source_branch) + project.pipelines.list(status='pending', ref=target_branch)
            active = running_pipelines + pending_pipelines
            if active:
                msg = f"⚠️ WARNING: There are {len(active)} active pipeline(s) currently running for the source/target branches (IDs: {', '.join([str(p.id) for p in active])}). Please wait for them to finish before initiating a release to avoid auto-canceling them or creating merge conflicts."
                yield {"success": False, "message": msg}
                logger.warning(f"[GitRelease] {msg}")
                return
        except Exception as e:
            logger.warning(f"[GitRelease] Failed to check for active pipelines: {e}")
            
        target_version = "0.0.0"
        source_version = "0.0.0"
        top_entry_source = {}
        
        try:
            target_raw = self.gitlab_manager.fetch_raw_yaml(project_name, 'docs/CHANGELOG.yaml', branch=target_branch)
            parsed_target = yaml.safe_load(target_raw)
            if isinstance(parsed_target, list) and len(parsed_target) > 0:
                target_version = parsed_target[0].get('version', '0.0.0')
        except Exception:
            pass
            
        try:
            source_raw = self.gitlab_manager.fetch_raw_yaml(project_name, 'docs/CHANGELOG.yaml', branch=source_branch)
            parsed_source = yaml.safe_load(source_raw)
            if isinstance(parsed_source, list) and len(parsed_source) > 0:
                top_entry_source = parsed_source[0]
                source_version = top_entry_source.get('version', '0.0.0')
        except Exception:
            pass
            
        tv = parse_version(target_version)
        sv = parse_version(source_version)
        
        next_base = tv if tv >= sv else sv
        next_patch = next_base.micro + 1
        next_version = f"{next_base.major}.{next_base.minor}.{next_patch}"
        
        version = next_version
        
        if not skip_changelog:
            try:
                yield f"Syncing local cache for '{source_branch}'..."
                self.gitlab_manager.checkout_project_branch(project_name, source_branch)
                
                local_base = self.config['external_services']['gitlab']['local_clone_path']
                rel_path = project_name
                project_path = self.config['external_services']['gitlab']['project_path']
                if rel_path.startswith(project_path + "/"):
                    rel_path = rel_path[len(project_path) + 1:]
                repo_local_path = os.path.join(local_base, rel_path)
                
                if author:
                    try:
                        git_log_res = subprocess.run(['git', 'log', '--author', author_name, '--format=%ae', '-n', '1'], cwd=repo_local_path, capture_output=True, text=True)
                        if git_log_res.returncode == 0 and git_log_res.stdout.strip():
                            author_email = git_log_res.stdout.strip().split('\n')[0]
                    except Exception as e:
                        logger.warning(f"[GitRelease] Failed to extract true git email from history: {e}")
                
                subprocess.run(['git', 'config', 'user.name', author_name], cwd=repo_local_path)
                subprocess.run(['git', 'config', 'user.email', author_email], cwd=repo_local_path)
                
                yield f"Merging 'origin/{target_branch}' into '{source_branch}' locally..."
                merge_res = subprocess.run(['git', 'merge', f'origin/{target_branch}', '-m', f"Auto-sync from {target_branch} [skip ci]"], cwd=repo_local_path, capture_output=True, text=True)
                if merge_res.returncode != 0:
                    subprocess.run(['git', 'merge', '--abort'], cwd=repo_local_path)
                    err_msg = f"Merge conflict detected locally while syncing '{target_branch}' into '{source_branch}'. Please resolve locally and push."
                    logger.error(f"[GitRelease] {err_msg}")
                    yield {"success": False, "message": err_msg}
                    return

                cl_path = os.path.join(repo_local_path, 'docs', 'CHANGELOG.yaml')
                orchestrator = ChangelogOrchestrator(config=self.config)
                
                if not os.path.exists(cl_path):
                    yield "⚠️ 'docs/CHANGELOG.yaml' is missing. Initiating automatic full historical backfill..."
                    full_backfill_yaml = None
                    for item in orchestrator.run_backfill(repo_local_path, source_branch, start_version="0.1.0"):
                        if isinstance(item, dict) and "final_yaml" in item:
                            full_backfill_yaml = item["final_yaml"]
                        elif isinstance(item, str):
                            yield f"  {item}"
                            
                    if not full_backfill_yaml:
                        yield {"success": False, "message": "Failed to backfill missing CHANGELOG.yaml."}
                        return
                        
                    os.makedirs(os.path.dirname(cl_path), exist_ok=True)
                    with open(cl_path, 'w') as f:
                        f.write(full_backfill_yaml)
                        
                    try:
                        parsed_backfill = yaml.safe_load(full_backfill_yaml)
                        if isinstance(parsed_backfill, list) and len(parsed_backfill) > 0:
                            top_entry_source = parsed_backfill[0]
                            version = top_entry_source.get('version', '0.1.0')
                        if audit_log:
                            audit_log.changelog_generation_method = "AUTO_BACKFILLED_LLM"
                            audit_log.merged_features_json = {"raw_yaml": full_backfill_yaml}
                            if session: session.commit()
                    except Exception as e:
                        logger.error(f"[GitRelease] Failed to parse backfilled changelog: {e}")
                        
                    yield "Full changelog backfill complete. Committing and pushing docs/CHANGELOG.yaml..."
                else:
                    yield f"Checking changelog sync (Target: v{target_version}, Source: v{source_version}) -> Target Release: v{next_version}"
                    yield f"Generating semantic release notes for v{next_version}..."
                    
                    generator = orchestrator.generate_for_commits(
                        repo_local_path=repo_local_path,
                        start_commit=f'origin/{target_branch}',
                        end_commit='HEAD',
                        author=author_name,
                        date_str=datetime.now().strftime("%Y-%m-%d"),
                        version=next_version
                    )
                    
                    final_yaml = None
                    for item in generator:
                        if isinstance(item, dict) and "final_yaml" in item:
                            final_yaml = item["final_yaml"]
                        elif isinstance(item, str):
                            yield f"  {item}"
                            
                    if not final_yaml:
                        yield "No significant features detected by AI. Applying standard bugfix patch bump..."
                        final_yaml = "- category: '🐛 Bug Fixes & Resilience'\n  items:\n    - 'Minor system updates, refactoring, and targeted bug fixes.'"
                        
                    with open(cl_path, 'r') as f:
                        existing = f.read()
                    
                    lines_out = final_yaml.strip().split('\n')
                    formatted_yaml = ""
                    for i, line_out in enumerate(lines_out):
                        if i == 0:
                            if not line_out.startswith("-"):
                                formatted_yaml += f"- {line_out}\n"
                            else:
                                formatted_yaml += f"{line_out}\n"
                        else:
                            formatted_yaml += f"  {line_out}\n"
                    final_yaml = formatted_yaml
                        
                    existing_lines = existing.split('\n')
                    insert_idx = 0
                    for idx, line in enumerate(existing_lines):
                        stripped = line.strip()
                        if stripped == '' or stripped.startswith('#') or stripped == '---':
                            insert_idx = idx + 1
                        else:
                            break
                            
                    new_content = "\n".join(existing_lines[:insert_idx])
                    if new_content and not new_content.endswith('\n'):
                        new_content += "\n"
                    new_content += final_yaml + "\n\n"
                    new_content += "\n".join(existing_lines[insert_idx:])
                        
                    with open(cl_path, 'w') as f:
                        f.write(new_content)
                        
                    try:
                        parsed_new = yaml.safe_load(final_yaml)
                        if isinstance(parsed_new, list) and len(parsed_new) > 0:
                            top_entry_source = parsed_new[0]
                        if audit_log:
                            audit_log.changelog_generation_method = "AUTO_GENERATED_LLM"
                            audit_log.merged_features_json = {"raw_yaml": final_yaml}
                            if session: session.commit()
                    except Exception as e:
                        logger.error(f"[GitRelease] Failed to parse newly generated changelog for commit msg: {e}")
                        
                    yield f"Committing and pushing generated changelog (v{next_version})..."
                
                subprocess.run(['git', 'add', 'docs/CHANGELOG.yaml'], cwd=repo_local_path)
                commit_res = subprocess.run(['git', 'commit', '-m', f"chore(release): auto-generate changelog for v{version}"], cwd=repo_local_path, capture_output=True, text=True)
                if commit_res.returncode != 0 and "nothing to commit" not in commit_res.stdout:
                    yield {"success": False, "message": f"Failed to commit changelog: {commit_res.stderr}"}
                    return
                    
                push_res = subprocess.run(['git', 'push', '-o', 'ci.skip', 'origin', source_branch], cwd=repo_local_path, capture_output=True, text=True)
                if push_res.returncode != 0:
                    logger.warning(f"[GitRelease] Push rejected for {source_branch}. Attempting pull --rebase to resolve race condition...")
                    yield "Push rejected (likely concurrent update). Attempting pull --rebase..."
                    
                    rebase_res = subprocess.run(['git', 'pull', '--rebase', 'origin', source_branch], cwd=repo_local_path, capture_output=True, text=True)
                    if rebase_res.returncode != 0:
                        subprocess.run(['git', 'rebase', '--abort'], cwd=repo_local_path)
                        yield {"success": False, "message": f"Failed to rebase changelog: {rebase_res.stderr}"}
                        return
                        
                    push_res_2 = subprocess.run(['git', 'push', '-o', 'ci.skip', 'origin', source_branch], cwd=repo_local_path, capture_output=True, text=True)
                    if push_res_2.returncode != 0:
                        yield {"success": False, "message": f"Failed to push changelog after rebase: {push_res_2.stderr}"}
                        return
                    yield "Successfully rebased and pushed changelog."
                
                yield f"Syncing changelog to deployment docs repository..."
                try:
                    proj_basename = project_name.split('/')[-1]
                    self.gitlab_manager.commit_file_api(
                        project_path="ai/halo/deployment",
                        file_path=f"docs/{proj_basename}/CHANGELOG.yaml",
                        content=open(cl_path, 'r').read(),
                        branch="main",
                        commit_msg=f"chore(docs): sync changelog for {proj_basename} v{version}"
                    )
                    yield f"Successfully synced changelog to deployment/docs/{proj_basename}/CHANGELOG.yaml."
                except Exception as e:
                    logger.error(f"[GitRelease] Failed to push changelog to deployment repo: {e}")
                    yield f"Warning: Failed to sync changelog to deployment repo: {e}"
                        
            except Exception as e:
                logger.error(f"[GitRelease] Changelog generation/backfill failed: {e}")
                yield {"success": False, "message": f"Changelog generation/backfill failed: {e}"}
                return
        else:
            version = source_version
            
        try:
            llm_config = self.config.get('llm_engines', {}).get('primary')
            auth_config = self.config.get('auth')
            client = vLLMClient(config=llm_config, auth_cfg=auth_config)
            
            import json
            prompt = GIT_COMMIT_PROMPT.format(version=version, changelog_items=json.dumps(top_entry_source.get('changes', [])))
            messages = [{"role": "user", "content": prompt}]
            
            yield "Generating commit message via LLM..."
            llm_res = client.get_chat_completion(messages=messages, temperature=0.2, json_mode=False)
            commit_msg = llm_res.get('content', '').strip() if llm_res else f"[v{version}] Auto-merge {source_branch}"
            
            logger.info(f"[GitRelease] Commit message generated: {commit_msg}")
            yield f"Commit message generated: {commit_msg}"
            
        except Exception as e:
            logger.error(f"[GitRelease] Failed to generate commit message: {e}")
            yield {"success": False, "message": f"Failed to generate commit message: {e}"}
            return
            
        logger.info("[GitRelease] Triggering Merge via GitLab API...")
        yield "Triggering Merge via GitLab API..."
        success, mr_iid, msg = self.gitlab_manager.create_and_merge_mr(
            project_name, 
            source_branch, 
            target_branch, 
            commit_msg,
            keep_branch=keep_branch,
            assignee_id=author_id
        )
        if not success:
            logger.error(f"[GitRelease] Merge failed: {msg}")
            yield {"success": False, "message": msg}
            return
            
        yield f"Successfully queued merge for '{source_branch}' into '{target_branch}'."
        
        import gitlab
        gl = gitlab.Gitlab(self.gitlab_manager.url, private_token=self.gitlab_manager.token, ssl_verify=False)
        project = gl.projects.get(project_name)
        
        yield "Waiting for MR pipeline to pass before merge..."
        
        for update in self.gitlab_manager.monitor_pipeline(project_name, mr_iid=mr_iid, debug=debug):
            if isinstance(update, dict):
                if "telemetry" in update and audit_log:
                    audit_log.job_details_json = update["telemetry"]
                    if session: session.commit()
            yield update
            
        merged = False
        for _ in range(30):
            mr = project.mergerequests.get(mr_iid)
            try:
                mr = project.mergerequests.get(mr_iid)
                if mr.state == 'merged':
                    merged = True
                    break
                if mr.state == 'closed':
                    break
                    
                yield f"Merge in progress (State: {mr.state}, Status: {mr.detailed_merge_status})..."
            except Exception as e:
                logger.error(f"[GitRelease] Failed to check MR status: {e}")
                
            import time
            time.sleep(5)
            
        if not merged:
            yield f"❌ ❌ MR failed to merge. State: {mr.state}, Status: {mr.merge_status}. Aborting release."
            yield f"\nTo retry this release once the issue is fixed, run:"
            yield f"  python3 halo_admin_utility.py git retry --repo {project_name} --merge {mr.iid}"
            err_msg = f"MR failed to merge. State: {mr.state}, Status: {mr.detailed_merge_status}. Aborting release."
            logger.error(f"[GitRelease] {err_msg}")
            yield {"success": False, "message": err_msg}
            return
        
        target_version = version
        if target_branch == 'dev':
            if not target_version.endswith('-dev'):
                target_version += '-dev'
        if not target_version.startswith('v'):
            target_version = 'v' + target_version
            
        slug = re.sub(r'[^a-z0-9]+', '-', source_branch.lower()).strip('-')[:63]
        yield f"Retagging container from '{slug}' to '{target_version}'..."
        
        retag_success, retag_msg = self.gitlab_manager.retag_container(project_name, slug, target_version)
        if not retag_success:
            logger.warning(f"[GitRelease] Container retagging failed: {retag_msg}")
            yield f"⚠️ Pipeline merge complete, but container retagging failed: {retag_msg}"
            
        if audit_log:
            audit_log.status = "SUCCESS"
            audit_log.version_tag = target_version
            if session: session.commit()
            
        yield f"Release #MR-{mr_iid} completed successfully! ✅"

    def run_retry(self, project_name: str, pipeline_id: int = 0, merge_id: int = 0, skip_warnings: bool = False, debug: bool = False) -> Generator[Any, None, None]:
        if not self.gitlab_manager:
            raise RuntimeError("GitlabManager is not initialized.")
            
        audit_log = None
        session = None
        
        if self.Session:
            try:
                session = self.Session()
                active_lock = session.query(GitReleaseAuditLog).filter_by(
                    project_name=project_name, 
                    status="RUNNING"
                ).first()
                
                if active_lock:
                    msg = f"⚠️ WARNING: A release (Action: {active_lock.action}) is already currently running for {project_name} by {active_lock.actor}. Please wait for it to finish."
                    yield {"success": False, "message": msg}
                    session.close()
                    return
                    
                audit_log = GitReleaseAuditLog(
                    project_name=project_name,
                    action="GIT_RETRY",
                    actor="gia-ai",
                    status="RUNNING",
                    changelog_generation_method="N/A",
                    merged_features_json={},
                    job_details_json={}
                )
                session.add(audit_log)
                session.commit()
            except Exception as e:
                logger.error(f"[GitRetry] Failed to acquire DB lock: {e}")
                if session:
                    session.rollback()

        try:
            for item in self._run_retry_internal(project_name, pipeline_id, merge_id, skip_warnings, debug, audit_log, session):
                if isinstance(item, dict) and not item.get("success", True):
                    if audit_log:
                        audit_log.status = "FAILED"
                        audit_log.error_message = item.get("message", "Unknown error occurred.")
                        if session: session.commit()
                yield item
        except Exception as e:
            if audit_log:
                audit_log.status = "FAILED"
                audit_log.error_message = f"Unhandled Exception: {str(e)}"
                if session: session.commit()
            logger.error(f"[GitRetry] Unhandled Exception: {e}", exc_info=True)
            raise e
        finally:
            if session and audit_log:
                try:
                    if audit_log.status == "RUNNING":
                        audit_log.status = "FAILED"
                        audit_log.error_message = "Orchestration aborted unexpectedly or connection dropped."
                    session.commit()
                    session.close()
                except Exception:
                    pass

    def _run_retry_internal(self, project_name: str, pipeline_id: int, merge_id: int, skip_warnings: bool, debug: bool, audit_log, session) -> Generator[Any, None, None]:
            
        yield f"Initiating retry for pipeline #{pipeline_id} on project '{project_name}'..."
        
        try:
            import gitlab
            gl = gitlab.Gitlab(self.gitlab_manager.url, private_token=self.gitlab_manager.token, ssl_verify=False)
            project = gl.projects.get(project_name)
            
            if merge_id:
                mr = project.mergerequests.get(merge_id)
                pipelines = mr.pipelines.list(order_by='updated_at', sort='desc')
                if not pipelines:
                    yield f"No pipeline found for MR !{merge_id}. Creating one..."
                    new_p = mr.pipelines.create()
                    pipeline_id = new_p.id
                else:
                    pipeline_id = pipelines[0].id
                    yield f"Found latest pipeline #{pipeline_id} for MR !{merge_id}."
                    
                if audit_log:
                    audit_log.source_branch = mr.source_branch
                    audit_log.target_branch = mr.target_branch
                    if session: session.commit()

            p = project.pipelines.get(pipeline_id)
            
            yield f"Current pipeline status is: {p.status.upper()}"
            if p.status in ['running', 'pending', 'created']:
                yield "Pipeline is already active. Proceeding to monitor..."
            elif skip_warnings and p.status == 'success':
                yield "Pipeline is already successful (warnings skipped). Proceeding directly to monitor/merge..."
            else:
                yield "Triggering pipeline retry via GitLab API..."
                if p.status == 'skipped' and p.ref.startswith('refs/merge-requests/'):
                    mr_iid = int(p.ref.split('/')[2])
                    mr = project.mergerequests.get(mr_iid)
                    new_p = mr.pipelines.create()
                    pipeline_id = new_p.id
                    yield f"Created new MR pipeline #{pipeline_id} to replace the skipped one."
                else:
                    p.retry()
                import time
                time.sleep(2) 
                
        except Exception as e:
            msg = f"Failed to retry pipeline #{pipeline_id}: {e}"
            logger.error(f"[GitRetry] {msg}")
            yield {"success": False, "message": msg}
            return
            
        pipeline_success = False
        for update in self.gitlab_manager.monitor_pipeline(project_name, pipeline_id=pipeline_id, debug=debug):
            if isinstance(update, dict) and "pipeline_success" in update:
                pipeline_success = update.get("pipeline_success", False)
                if "telemetry" in update and audit_log:
                    audit_log.job_details_json = update["telemetry"]
                    if session: session.commit()
                continue
            yield update
            
        if not pipeline_success:
            yield {"success": False, "message": f"Pipeline #{pipeline_id} failed. Retry aborted."}
            return
            
        mr = None
        if p.ref and p.ref.startswith('refs/merge-requests/'):
            try:
                mr_iid_from_ref = int(p.ref.split('/')[2])
                mr = project.mergerequests.get(mr_iid_from_ref)
                if mr.state not in ['opened', 'merged']:
                    mr = None
            except Exception as e:
                logger.warning(f"[GitRetry] Failed to extract MR from ref '{p.ref}': {e}")
                
        if not mr:
            mrs = project.mergerequests.list(source_branch=p.ref, state='opened')
            if mrs:
                mr = mrs[0]
            else:
                mrs_merged = project.mergerequests.list(source_branch=p.ref, state='merged', order_by='updated_at', sort='desc')
                if mrs_merged:
                    mr = mrs_merged[0]
                    
        if mr and audit_log and not audit_log.source_branch:
            audit_log.source_branch = mr.source_branch
            audit_log.target_branch = mr.target_branch
            if session: session.commit()
                
        if not mr:
            yield {"success": True, "message": f"Pipeline #{pipeline_id} completed successfully. (No MR found to merge)."}
            return
            
        yield f"Pipeline is attached to MR !{mr.iid} ({mr.source_branch} -> {mr.target_branch}). Triggering merge..."
        
        try:
            merge_msg = f"{mr.title}\n\n[skip ci]"
            mr.merge(merge_commit_message=merge_msg, should_remove_source_branch=False)
        except gitlab.exceptions.GitlabMRClosedError:
            pass
        except Exception as e:
            if "Merge Request is not mergeable" not in str(e):
                logger.warning(f"[GitRetry] Error triggering merge: {e}")
                
        yield "Checking merge status..."
        
        merged = False
        for _ in range(30):
            try:
                mr = project.mergerequests.get(mr.iid)
                if mr.state == 'merged':
                    merged = True
                    break
                if mr.state == 'closed':
                    break
                    
                yield f"Merge in progress (State: {mr.state}, Status: {mr.detailed_merge_status})..."
            except Exception as e:
                logger.error(f"[GitRetry] Failed to check MR status: {e}")
            import time
            time.sleep(5)
            
        if not merged:
            err_msg = f"MR failed to merge. State: {mr.state}, Status: {mr.detailed_merge_status}."
            yield {"success": False, "message": err_msg}
            return
            
        yield "Pipeline merge complete!"
        
        target_version = "0.0.0"
        try:
            import yaml
            import base64
            f = project.files.get(file_path='docs/CHANGELOG.yaml', ref=mr.target_branch)
            changelog_content = base64.b64decode(f.content).decode('utf-8')
            changelog_data = yaml.safe_load(changelog_content)
            if isinstance(changelog_data, list) and len(changelog_data) > 0:
                target_version = str(changelog_data[0].get('version', '0.0.0'))
        except Exception as e:
            logger.warning(f"[GitRetry] Could not parse version from changelog for retagging: {e}")
            
        if target_version != "0.0.0":
            if mr.target_branch == 'dev' and not target_version.endswith('-dev'):
                target_version += '-dev'
            if not target_version.startswith('v'):
                target_version = 'v' + target_version
                
            slug = re.sub(r'[^a-z0-9]+', '-', mr.source_branch.lower()).strip('-')[:63]
            yield f"Retagging container from '{slug}' to '{target_version}'..."
            
            retag_success, retag_msg = self.gitlab_manager.retag_container(project_name, slug, target_version)
            if not retag_success:
                yield f"⚠️ Pipeline merge complete, but container retagging failed: {retag_msg}"
                
        if audit_log:
            audit_log.status = "SUCCESS"
            audit_log.version_tag = target_version
            if session: session.commit()
                
        yield {"success": True, "message": f"Retry and Release of MR !{mr.iid} completed successfully! ✅"}