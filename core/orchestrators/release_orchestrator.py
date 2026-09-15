import os
import logging
import subprocess
import yaml
import re
import copy
from packaging.version import parse as parse_version
from typing import Dict, Any, Generator
from datetime import datetime

from core.orchestrators.changelog_orchestrator import ChangelogOrchestrator
from core.llm_interface import vLLMClient
from prompts.git_commit_prompt import GIT_COMMIT_PROMPT
from core.database.database import get_db_session
from core.io_handlers.sql_reader import SQLReader
from core.io_handlers.sql_writer import SQLWriter
from core.managers.git_pipeline_manager import GitPipelineManager
from core.managers.container_registry_manager import ContainerRegistryManager
from core.managers.git_inventory_manager import GitInventoryManager

logger = logging.getLogger(__name__)

class ReleaseOrchestrator:
    def __init__(self, config: Dict[str, Any], gitlab_manager):
        self.config = config
        self.gitlab_manager = gitlab_manager
        self.pipeline_manager = GitPipelineManager(config)
        self.registry_manager = ContainerRegistryManager(config)
        self.inventory_manager = GitInventoryManager(config)
        self.use_db = True # Assumes database is initialized upstream

    def _format_release_notes(self, version: str, changelog_entry: dict) -> str:
        md = f"## Release {version}\n\n"
        if 'date' in changelog_entry:
            md += f"**Date:** {changelog_entry['date']} | **Author:** {changelog_entry.get('author', 'Unknown')}\n\n"
        
        changes = changelog_entry.get('changes', [])
        for category_block in changes:
            cat_name = category_block.get('category', 'Updates')
            items = category_block.get('items', [])
            if items:
                md += f"### {cat_name}\n"
                for item in items:
                    md += f"* {item}\n"
                md += "\n"
        return md.strip()

    def run_release(self, project_name: str, source_branch: str, target_branch: str, 
                    skip_changelog: bool, keep_branch: bool, debug: bool = False, author: str = None, dry_run: bool = False) -> Generator[Any, None, None]:
        
        if not self.gitlab_manager:
            raise RuntimeError("GitlabManager is not initialized.")
            
        audit_log = None
        session = None
        sql_reader = None
        sql_writer = None
        
        # We need to manage the session manually here because this is a long-running generator
        # and we don't want to hold a transaction open across network waits.
        # Actually, using a contextmanager for the whole generator is fine as long as we commit when needed.
        # To match the old logic exactly, we'll extract the session from the context manager manually.
        ctx = None
        if self.use_db:
            ctx = get_db_session(read_only=False)
            session = ctx.__enter__()
            try:
                sql_reader = SQLReader(session)
                sql_writer = SQLWriter(session)
                
                project_name = sql_reader.resolve_project_path(project_name)
                active_lock = sql_reader.get_active_git_release_audit_log(project_name)
                
                if active_lock:
                    msg = f"⚠️ WARNING: A release (Action: {active_lock.action}) is already currently running for {project_name} by {active_lock.actor}. Please wait for it to finish."
                    yield {"success": False, "message": msg}
                    session.close()
                    return
                    
                audit_log = sql_writer.create_git_release_audit_log(
                    project_name=project_name,
                    action="GIT_RELEASE_DRY_RUN" if dry_run else "GIT_RELEASE",
                    actor=author or "gia-ai",
                    status="RUNNING",
                    source_branch=source_branch,
                    target_branch=target_branch
                )
            except Exception as e:
                logger.error(f"[GitRelease] Failed to acquire DB lock: {e}")
                if session:
                    session.rollback()

        try:
            trace_logs = []
            for item in self._run_release_internal(project_name, source_branch, target_branch, skip_changelog, keep_branch, debug, audit_log, author, sql_reader, sql_writer, dry_run):
                trace_logs.append(item)
                if isinstance(item, dict) and not item.get("success", True):
                    if audit_log and sql_writer:
                        sql_writer.update_git_release_audit_log(audit_log.id, status="FAILED", error_message=item.get("message", "Unknown error occurred."))
                yield item
        except Exception as e:
            trace_logs.append({"success": False, "message": f"Unhandled Exception: {str(e)}", "stage": "ERROR"})
            if audit_log and sql_writer:
                sql_writer.update_git_release_audit_log(audit_log.id, status="FAILED", error_message=f"Unhandled Exception: {str(e)}")
            logger.error(f"[GitRelease] Unhandled Exception: {e}", exc_info=True)
            raise e
        finally:
            if session and audit_log:
                try:
                    if audit_log.status == "RUNNING":
                        sql_writer.update_git_release_audit_log(audit_log.id, status="FAILED", error_message="Orchestration aborted unexpectedly or connection dropped.")
                    
                    if sql_writer and sql_reader:
                        fresh_log = sql_reader.get_git_release_audit_log_by_id(audit_log.id)
                        if fresh_log:
                            current_details = copy.deepcopy(fresh_log.job_details_json or {})
                            current_details['trace_logs'] = trace_logs
                            sql_writer.update_git_release_audit_log(audit_log.id, job_details_json=current_details)
                    
                    if ctx:
                        ctx.__exit__(None, None, None)
                except Exception:
                    pass

    def _run_release_internal(self, project_name, source_branch, target_branch, skip_changelog, keep_branch, debug, audit_log, author, sql_reader, sql_writer, dry_run):
        mode_str = "[DRY-RUN] " if dry_run else ""
        yield f"{mode_str}Starting release: {source_branch} -> {target_branch}"
        
        yield "Syncing Git Inventory to ensure latest state before release..."
        try:
            self.inventory_manager.sync_database_inventory(sql_reader, sql_writer, project_name)
            yield "✅ Git Inventory successfully synced."
        except Exception as e:
            logger.error(f"[GitRelease] Pre-release inventory sync failed: {e}")
            yield f"⚠️ Warning: Pre-release inventory sync failed: {e}"
        
        if sql_reader:
            previous_release = sql_reader.get_previous_successful_release(project_name, source_branch, target_branch, "GIT_RELEASE")
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
                if audit_log and sql_writer:
                    sql_writer.update_git_release_audit_log(audit_log.id, actor=author_name)
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
        missing_changelog = True
        
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
                missing_changelog = False
        except Exception:
            pass
            
        tv = parse_version(target_version)
        sv = parse_version(source_version)
        
        changelog_already_generated = False
        if sv > tv:
            next_version = source_version
            changelog_already_generated = True
        else:
            next_base = tv if tv >= sv else sv
            next_patch = next_base.micro + 1
            next_version = f"{next_base.major}.{next_base.minor}.{next_patch}"
            
        if skip_changelog:
            version = source_version
        else:
            version = next_version
        
        def _get_tag(v_str):
            v = str(v_str)
            if v == "GENERATING":
                return v
            if target_branch == 'dev' and not v.endswith('-dev'):
                v += '-dev'
            if not v.startswith('v'):
                v = 'v' + v
            return v
            
        if audit_log and sql_writer:
            initial_tag = "GENERATING" if missing_changelog else _get_tag(version)
            sql_writer.update_git_release_audit_log(audit_log.id, version_tag=initial_tag)

        final_yaml = ""
        
        if not skip_changelog:
            try:
                yield f"Syncing local cache for '{source_branch}'..."
                self.gitlab_manager.checkout_project_branch(project_name, source_branch)
                
                local_base = self.config['external_services']['gitlab']['local_clone_path']
                repo_local_path = self.gitlab_manager.resolve_local_repo_path(project_name, local_base)
                
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
                    stderr_output = merge_res.stderr.strip() or merge_res.stdout.strip()
                    if "not something we can merge" in stderr_output.lower():
                        err_msg = f"Branch '{target_branch}' does not exist on origin. Please create it first. Git output: {stderr_output}"
                    else:
                        err_msg = f"Merge failed locally while syncing '{target_branch}' into '{source_branch}'. Git output: {stderr_output}. Please resolve locally and push."
                    logger.error(f"[GitRelease] {err_msg}")
                    yield {"success": False, "message": err_msg}
                    return

                cl_path = os.path.join(repo_local_path, 'docs', 'CHANGELOG.yaml')
                orchestrator = ChangelogOrchestrator(config=self.config)
                
                if changelog_already_generated:
                    yield f"Changelog for v{version} already exists in source branch [📜 Release Notes found]. Skipping generation."
                    if os.path.exists(cl_path):
                        with open(cl_path, 'r') as f:
                            final_yaml = f.read()
                            
                    if audit_log and sql_writer:
                        sql_writer.update_git_release_audit_log(
                            audit_log.id, 
                            changelog_generation_method="PRE_EXISTING",
                            version_tag=_get_tag(version)
                        )
                elif not os.path.exists(cl_path):
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
                        
                    parsed_backfill = None
                    try:
                        parsed_backfill = yaml.safe_load(full_backfill_yaml)
                    except Exception as e:
                        err_msg = f"Failed to parse backfilled changelog YAML: {e}"
                        logger.error(f"[GitRelease] {err_msg}")
                        yield {"success": False, "message": err_msg}
                        return

                    if isinstance(parsed_backfill, list) and len(parsed_backfill) > 0:
                        top_entry_source = parsed_backfill[0]
                        version = str(top_entry_source.get('version'))
                        if not version or version == "None":
                            yield {"success": False, "message": "Missing version in backfilled changelog YAML."}
                            return
                    else:
                        yield {"success": False, "message": "Backfilled changelog YAML is empty or malformed."}
                        return
                        
                    if audit_log and sql_writer:
                        sql_writer.update_git_release_audit_log(
                            audit_log.id, 
                            changelog_generation_method="AUTO_BACKFILLED_LLM", 
                            merged_features_json={"raw_yaml": full_backfill_yaml},
                            version_tag=_get_tag(version)
                        )
                        
                    yield "Full changelog backfill complete. Committing and pushing docs/CHANGELOG.yaml..."
                    final_yaml = full_backfill_yaml
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
                    
                    for item in generator:
                        if isinstance(item, dict) and "final_yaml" in item:
                            final_yaml = item["final_yaml"]
                        elif isinstance(item, str):
                            yield f"  {item}"
                            
                    if not final_yaml:
                        yield "No significant features detected by AI. Skipping changelog file update."
                    else:
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
                            
                        parsed_new = None
                        try:
                            parsed_new = yaml.safe_load(final_yaml)
                        except Exception as e:
                            err_msg = f"Failed to parse newly generated changelog for commit msg: {e}"
                            logger.error(f"[GitRelease] {err_msg}")
                            yield {"success": False, "message": err_msg}
                            return

                        if isinstance(parsed_new, list) and len(parsed_new) > 0:
                            top_entry_source = parsed_new[0]
                        else:
                            yield {"success": False, "message": "Generated changelog YAML is empty or malformed."}
                            return

                        if audit_log and sql_writer:
                            sql_writer.update_git_release_audit_log(
                                audit_log.id, 
                                changelog_generation_method="AUTO_GENERATED_LLM", 
                                merged_features_json={"raw_yaml": final_yaml},
                                version_tag=_get_tag(version)
                            )
                            
                        yield f"Committing and pushing generated changelog (v{next_version})..."
                
                if not changelog_already_generated:
                    if dry_run:
                        yield f"[DRY-RUN] Would execute: git add docs/CHANGELOG.yaml"
                        yield f"[DRY-RUN] Would execute: git commit -m 'chore(release): auto-generate changelog for v{version}'"
                        yield f"[DRY-RUN] Would execute: git push -o ci.skip origin {source_branch}"
                    else:
                        subprocess.run(['git', 'add', 'docs/CHANGELOG.yaml'], cwd=repo_local_path)
                        commit_res = subprocess.run(['git', 'commit', f'--author={author_name} <{author_email}>', '-m', f"chore(release): auto-generate changelog for v{version}"], cwd=repo_local_path, capture_output=True, text=True)
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
                if dry_run:
                    yield f"[DRY-RUN] Would sync changelog to deployment/docs/{project_name.split('/')[-1]}/CHANGELOG.yaml."
                else:
                    try:
                        proj_basename = project_name.split('/')[-1]
                        self.gitlab_manager.commit_file_api(
                            project_path="ai/halo/deployment",
                            file_path=f"docs/{proj_basename}/CHANGELOG.yaml",
                            branch="main",
                            content=open(cl_path, 'r').read(),
                            commit_msg=f"chore(docs): sync changelog for {proj_basename} v{version}",
                            author_name=author_name,
                            author_email=author_email
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
            yield f"Changelog generation skipped via flag. Proceeding with release v{version}..."
            
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

        mr_iid = 0
        mr_target_branch = target_branch

        if dry_run:
            yield f"[DRY-RUN] Would create and merge MR from '{source_branch}' to '{target_branch}'."
            yield f"[DRY-RUN] Would monitor MR pipeline and wait for merge success."
        else:
            logger.info("[GitRelease] Triggering Merge via GitLab API...")
            yield "Triggering Merge via GitLab API..."
            success, mr_iid, msg = self.pipeline_manager.create_and_merge_mr(
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
                
            if audit_log and sql_writer and mr_iid:
                sql_writer.update_git_release_audit_log(audit_log.id, merge_request_id=str(mr_iid))
                
            yield f"Successfully queued merge for '{source_branch}' into '{target_branch}'."
            
            import gitlab
            gl = gitlab.Gitlab(self.gitlab_manager.url, private_token=self.gitlab_manager.token, ssl_verify=False)
            project = gl.projects.get(project_name)
            
            yield "Waiting for MR pipeline to pass before merge..."
            
            pipeline_success = False
            pipeline_status = "failed"
            for update in self.pipeline_manager.monitor_pipeline(project_name, mr_iid=mr_iid, debug=debug):
                if isinstance(update, dict):
                    if "pipeline_success" in update:
                        pipeline_success = update.get("pipeline_success", False)
                        pipeline_status = update.get("pipeline_status", "failed")
                    if "telemetry" in update and audit_log and sql_writer:
                        sql_writer.update_git_release_audit_log(audit_log.id, job_details_json=update["telemetry"])
                    if "pipeline_success" in update or update.get("is_intermediate"):
                        continue
                yield update

            if not pipeline_success:
                err_msg = f"MR pipeline {pipeline_status}. Aborting release."
                logger.error(f"[GitRelease] {err_msg}")
                yield {"success": False, "message": err_msg}
                return
                
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
                yield f"  python3 halo_admin_utility.py git retry --project {project_name} --merge {mr.iid}"
                err_msg = f"MR failed to merge. State: {mr.state}, Status: {mr.detailed_merge_status}. Aborting release."
                logger.error(f"[GitRelease] {err_msg}")
                yield {"success": False, "message": err_msg}
                return

            mr_target_branch = mr.target_branch
            
        target_version = version
        if target_branch == 'dev':
            if not target_version.endswith('-dev'):
                target_version += '-dev'
        if not target_version.startswith('v'):
            target_version = 'v' + target_version
            
        slug = re.sub(r'[^a-z0-9]+', '-', source_branch.lower()).strip('-')[:63]
        yield f"Retagging container from '{slug}' to '{target_version}'..."
        
        if dry_run:
            yield f"[DRY-RUN] Would retag container from '{slug}' to '{target_version}'."
        else:
            retag_success, retag_msg = self.registry_manager.retag_container(project_name, slug, target_version)
            if not retag_success:
                logger.warning(f"[GitRelease] Container retagging failed: {retag_msg}")
                yield {"success": False, "message": f"Pipeline merge complete, but container retagging failed: {retag_msg}"}
                return

        yield f"Creating Git Tag '{target_version}' on '{mr_target_branch}'..."
        
        if dry_run:
            yield f"[DRY-RUN] Would create Git Tag '{target_version}' and native GitLab Release."
        else:
            tag_success, tag_msg = self.gitlab_manager.create_tag(project_name, target_version, mr_target_branch)
            if not tag_success and "already exists" not in tag_msg.lower() and "400" not in tag_msg.lower():
                yield {"success": False, "message": f"Failed to create Git tag: {tag_msg}"}
                return
            else:
                if not tag_success:
                    yield f"ℹ️ Git tag '{target_version}' already exists, proceeding to Release creation..."
                yield f"Creating native GitLab Release for '{target_version}'..."
                try:
                    parsed_new = yaml.safe_load(final_yaml) if final_yaml else [top_entry_source]
                    changelog_entry = parsed_new[0] if isinstance(parsed_new, list) and len(parsed_new) > 0 else {}
                    release_desc = self._format_release_notes(target_version, changelog_entry)
                    rel_success, rel_msg = self.gitlab_manager.create_release(project_name, target_version, release_desc)
                    if not rel_success:
                        yield {"success": False, "message": f"Failed to create GitLab Release: {rel_msg}"}
                        return
                    else:
                        yield f"✅ GitLab Release '{target_version}' created successfully!"
                except Exception as e:
                    yield {"success": False, "message": f"Failed to format or create GitLab Release: {e}"}
                    return
            
        if audit_log and sql_writer:
            sql_writer.update_git_release_audit_log(audit_log.id, status="SUCCESS", version_tag=target_version)

        yield "Syncing updated Git Inventory to database..."
        if dry_run:
            yield f"[DRY-RUN] Would synchronize targeted Git inventory for '{project_name}' to DB."
        else:
            try:
                self.inventory_manager.sync_database_inventory(sql_reader, sql_writer, project_name)
                yield "✅ Git Inventory successfully synced."
            except Exception as e:
                logger.error(f"[GitRelease] Failed to sync inventory: {e}")
                yield f"⚠️ Warning: Failed to sync git inventory: {e}"
            
        yield {"success": True, "message": f"{mode_str}Release completed successfully! ✅"}

    def run_retry(self, project_name: str, pipeline_id: int = 0, merge_id: int = 0, skip_warnings: bool = False, debug: bool = False, author: str = None) -> Generator[Any, None, None]:
        if not self.gitlab_manager:
            raise RuntimeError("GitlabManager is not initialized.")
            
        audit_log = None
        session = None
        sql_reader = None
        sql_writer = None
        
        ctx = None
        if self.use_db:
            ctx = get_db_session(read_only=False)
            session = ctx.__enter__()
            try:
                sql_reader = SQLReader(session)
                sql_writer = SQLWriter(session)
                
                project_name = sql_reader.resolve_project_path(project_name)
                active_lock = sql_reader.get_active_git_release_audit_log(project_name)
                
                if active_lock:
                    msg = f"⚠️ WARNING: A release (Action: {active_lock.action}) is already currently running for {project_name} by {active_lock.actor}. Please wait for it to finish."
                    yield {"success": False, "message": msg}
                    session.close()
                    return
                    
                version_tag = None
                if merge_id:
                    prev_log = sql_reader.get_latest_audit_log_by_mr(project_name, str(merge_id))
                    if prev_log:
                        version_tag = prev_log.version_tag
                        
                audit_log = sql_writer.create_git_release_audit_log(
                    project_name=project_name,
                    action="GIT_RETRY",
                    actor=author or "gia-ai",
                    status="RUNNING",
                    version_tag=version_tag
                )
            except Exception as e:
                logger.error(f"[GitRetry] Failed to acquire DB lock: {e}")
                if session:
                    session.rollback()

        try:
            trace_logs = []
            for item in self._run_retry_internal(project_name, pipeline_id, merge_id, skip_warnings, debug, audit_log, sql_reader, sql_writer, author):
                trace_logs.append(item)
                if isinstance(item, dict) and not item.get("success", True):
                    if audit_log and sql_writer:
                        sql_writer.update_git_release_audit_log(audit_log.id, status="FAILED", error_message=item.get("message", "Unknown error occurred."))
                yield item
        except Exception as e:
            trace_logs.append({"success": False, "message": f"Unhandled Exception: {str(e)}", "stage": "ERROR"})
            if audit_log and sql_writer:
                sql_writer.update_git_release_audit_log(audit_log.id, status="FAILED", error_message=f"Unhandled Exception: {str(e)}")
            logger.error(f"[GitRetry] Unhandled Exception: {e}", exc_info=True)
            raise e
        finally:
            if session and audit_log:
                try:
                    if audit_log.status == "RUNNING":
                        sql_writer.update_git_release_audit_log(audit_log.id, status="FAILED", error_message="Orchestration aborted unexpectedly or connection dropped.")
                    
                    if sql_writer and sql_reader:
                        fresh_log = sql_reader.get_git_release_audit_log_by_id(audit_log.id)
                        if fresh_log:
                            current_details = copy.deepcopy(fresh_log.job_details_json or {})
                            current_details['trace_logs'] = trace_logs
                            sql_writer.update_git_release_audit_log(audit_log.id, job_details_json=current_details)
                    
                    if ctx:
                        ctx.__exit__(None, None, None)
                except Exception:
                    pass

    def _run_retry_internal(self, project_name: str, pipeline_id: int, merge_id: int, skip_warnings: bool, debug: bool, audit_log, sql_reader, sql_writer, author: str) -> Generator[Any, None, None]:
            
        yield f"Initiating retry for pipeline #{pipeline_id} on project '{project_name}'..."

        author_name = self.config.get('external_services', {}).get('gitlab', {}).get('bot_username', 'GIA AI Bot')
        if author:
            resolved = self.gitlab_manager.resolve_user(project_name, author)
            if resolved and 'name' in resolved:
                author_name = resolved['name']
                yield f"✅ Mapped author override '{author}' to GitLab user: {author_name}"
                if audit_log and sql_writer:
                    sql_writer.update_git_release_audit_log(audit_log.id, actor=author_name)
        
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
                    
                if audit_log and sql_writer and not audit_log.source_branch:
                    sql_writer.update_git_release_audit_log(audit_log.id, source_branch=mr.source_branch, target_branch=mr.target_branch, merge_request_id=str(mr.iid))

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
                    
                    commit = project.commits.get(mr.sha)
                    commit_text = (commit.title + " " + commit.message).lower()
                    
                    if '[skip ci]' in commit_text or '[ci skip]' in commit_text:
                        yield "⚠️ The latest commit contains '[skip ci]'. GitLab permanently skips pipelines for this commit."
                        yield "Pushing an empty trigger commit to force CI execution..."
                        try:
                            new_commit = project.commits.create({
                                'branch': mr.source_branch,
                                'commit_message': 'chore: trigger CI pipeline via git retry',
                                'actions': [],
                                'allow_empty': True
                            })
                            yield "Empty trigger commit pushed successfully."
                            import time
                            
                            new_pipeline = None
                            for _ in range(30):
                                time.sleep(1)
                                commit_pipelines = project.pipelines.list(sha=new_commit.id)
                                if commit_pipelines:
                                    new_pipeline = commit_pipelines[0]
                                    break
                                    
                            if new_pipeline:
                                pipeline_id = new_pipeline.id
                                yield f"Created new MR pipeline #{pipeline_id} via trigger commit."
                            else:
                                yield f"Trigger commit pushed, but no pipeline generated after 30s."
                                return
                        except Exception as e:
                            yield f"Failed to push trigger commit: {e}"
                            return
                    else:
                        new_p = mr.pipelines.create()
                        pipeline_id = new_p.id
                        yield f"Created new MR pipeline #{pipeline_id} to replace the skipped one."
                    
                    if audit_log and sql_writer and not audit_log.source_branch:
                        sql_writer.update_git_release_audit_log(audit_log.id, source_branch=mr.source_branch, target_branch=mr.target_branch, merge_request_id=str(mr.iid))
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
        pipeline_status = "failed"
        for update in self.pipeline_manager.monitor_pipeline(project_name, pipeline_id=pipeline_id, debug=debug):
            if isinstance(update, dict):
                if "pipeline_success" in update:
                    pipeline_success = update.get("pipeline_success", False)
                    pipeline_status = update.get("pipeline_status", "failed")
                if "telemetry" in update and audit_log and sql_writer:
                    sql_writer.update_git_release_audit_log(audit_log.id, job_details_json=update["telemetry"])
                if "pipeline_success" in update or update.get("is_intermediate"):
                    continue
            yield update
            
        if not pipeline_success:
            yield {"success": False, "message": f"Pipeline #{pipeline_id} {pipeline_status}. Retry aborted."}
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
                    
        if mr and audit_log and sql_writer and not audit_log.source_branch:
            sql_writer.update_git_release_audit_log(audit_log.id, source_branch=mr.source_branch, target_branch=mr.target_branch, merge_request_id=str(mr.iid))
                
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
        changelog_data = []
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
            
            retag_success, retag_msg = self.registry_manager.retag_container(project_name, slug, target_version)
            if not retag_success:
                yield {"success": False, "message": f"Pipeline merge complete, but container retagging failed: {retag_msg}"}
                return

            yield f"Creating Git Tag '{target_version}' on '{mr.target_branch}'..."
            tag_success, tag_msg = self.gitlab_manager.create_tag(project_name, target_version, mr.target_branch)
            if not tag_success and "already exists" not in tag_msg.lower() and "400" not in tag_msg.lower():
                yield {"success": False, "message": f"Failed to create Git tag: {tag_msg}"}
                return
            else:
                if not tag_success:
                    yield f"ℹ️ Git tag '{target_version}' already exists, proceeding to Release creation..."
                yield f"Creating native GitLab Release for '{target_version}'..."
                try:
                    changelog_entry = changelog_data[0] if isinstance(changelog_data, list) and len(changelog_data) > 0 else {}
                    release_desc = self._format_release_notes(target_version, changelog_entry)
                    rel_success, rel_msg = self.gitlab_manager.create_release(project_name, target_version, release_desc)
                    if not rel_success:
                        yield {"success": False, "message": f"Failed to create GitLab Release: {rel_msg}"}
                        return
                    else:
                        yield f"✅ GitLab Release '{target_version}' created successfully!"
                except Exception as e:
                    yield {"success": False, "message": f"Failed to format or create GitLab Release: {e}"}
                    return
                
        if audit_log and sql_writer:
            sql_writer.update_git_release_audit_log(audit_log.id, status="SUCCESS", version_tag=target_version)

        yield "Syncing updated Git Inventory to database..."
        try:
            self.inventory_manager.sync_database_inventory(sql_reader, sql_writer, project_name)
            yield "✅ Git Inventory successfully synced."
        except Exception as e:
            logger.error(f"[GitRetry] Failed to sync inventory: {e}")
            yield f"⚠️ Warning: Failed to sync git inventory: {e}"
                
        yield {"success": True, "message": f"Retry and Release of MR !{mr.iid} completed successfully! ✅"}