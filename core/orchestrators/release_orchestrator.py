import os
import logging
import json
import base64
import subprocess
import yaml
import re
import copy
import time
from packaging.version import parse as parse_version
from typing import Dict, Any, Generator
from datetime import datetime, timezone, timedelta
import gitlab

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
        self.use_db = True

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

    def _get_top_version_and_date(self, yaml_content: str):
        try:
            parsed = yaml.safe_load(yaml_content)
            if isinstance(parsed, list) and len(parsed) > 0:
                return str(parsed[0].get('version', '0.1.0')), parsed[0].get('date', '')
        except Exception:
            pass
        return "0.1.0", ""

    def _generate_llm_commit_msg(self, version: str, changelog_entry: dict) -> str:
        try:
            llm_config = self.config.get('llm_engines', {}).get('primary')
            auth_config = self.config.get('auth')
            client = vLLMClient(config=llm_config, auth_cfg=auth_config)
            
            prompt = GIT_COMMIT_PROMPT.format(version=version, changelog_items=json.dumps(changelog_entry.get('changes', [])))
            messages = [{"role": "user", "content": prompt}]
            
            llm_res = client.get_chat_completion(messages=messages, temperature=0.2, json_mode=False)
            commit_msg = llm_res.get('content', '').strip() if llm_res else f"[v{version}] Auto-merge feature"
            return commit_msg
        except Exception as e:
            logger.error(f"[GitRelease] Failed to generate commit message: {e}")
            return f"[v{version}] Auto-merge feature"

    def _check_active_pipeline(self, project_name: str, branch: str):
        try:
            gl = gitlab.Gitlab(self.gitlab_manager.url, private_token=self.gitlab_manager.token, ssl_verify=False)
            project = gl.projects.get(project_name)
            pipelines = project.pipelines.list(ref=branch, order_by='id', sort='desc', get_all=False)
            if pipelines:
                latest = pipelines[0]
                if latest.status in ['running', 'pending', 'created', 'waiting_for_resource', 'preparing']:
                    return True, latest.status
            return False, None
        except Exception as e:
            logger.warning(f"Failed to check pipelines for {branch}: {e}")
            return False, None


    def run_release(self, project_name: str, source_branch: str, target_branch: str, 
                    skip_changelog: bool, keep_branch: bool, debug: bool = False, 
                    author: str = None, dry_run: bool = False,
                    release_only: bool = False, skip_rogue_check: bool = False,
                    use_deployment_changelog: bool = False) -> Generator[Any, None, None]:
        
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
            for item in self._run_release_internal(project_name, source_branch, target_branch, skip_changelog, keep_branch, debug, audit_log, author, sql_reader, sql_writer, dry_run, release_only, skip_rogue_check, use_deployment_changelog):
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

    def _run_release_internal(self, project_name, source_branch, target_branch, skip_changelog, keep_branch, debug, audit_log, author, sql_reader, sql_writer, dry_run, release_only, skip_rogue_check, use_deployment_changelog):
        mode_str = "[DRY-RUN] " if dry_run else ""
        
        if release_only:
            yield f"{mode_str}Starting environment sync (release-only) on target branch '{target_branch}'..."
        else:
            yield f"{mode_str}Starting release: {source_branch} -> {target_branch}"
        
        yield "Syncing Git Inventory to ensure latest state before release..."
        try:
            self.inventory_manager.sync_database_inventory(sql_reader, sql_writer, project_name)
            yield "✅ Git Inventory successfully synced."
        except Exception as e:
            logger.error(f"[GitRelease] Pre-release inventory sync failed: {e}")
            yield f"⚠️ Warning: Pre-release inventory sync failed: {e}"
        
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
                yield {"success": False, "message": f"❌ Could not resolve author '{author}' in GitLab project members or users."}
                return

        local_base = self.config['external_services']['gitlab']['local_clone_path']
        repo_local_path = self.gitlab_manager.resolve_local_repo_path(project_name, local_base)
        cl_path = os.path.join(repo_local_path, 'docs', 'CHANGELOG.yaml')
        orchestrator = ChangelogOrchestrator(config=self.config)

        def _get_tag(v_str):
            v = str(v_str)
            if v == "GENERATING": return v
            if target_branch == 'dev' and not v.endswith('-dev'): v += '-dev'
            if not v.startswith('v'): v = 'v' + v
            return v

        if release_only:
            self.gitlab_manager.checkout_project_branch(project_name, target_branch)
            is_main = target_branch in ['main', 'master']
            fetch_deployment_changelog = is_main or use_deployment_changelog
            
            if fetch_deployment_changelog:
                proj_basename = project_name.split('/')[-1]
                try:
                    deployment_yaml = self.gitlab_manager.fetch_raw_yaml("ai/halo/deployment", f"docs/{proj_basename}/CHANGELOG.yaml", branch="main")
                except Exception as e:
                    yield {"success": False, "message": f"Failed to fetch source of truth changelog from deployment repo: {e}"}
                    return
                
                if not deployment_yaml:
                    yield {"success": False, "message": "Source of truth changelog is empty."}
                    return
                    
                date_res = subprocess.run(['git', 'log', '-1', '--format=%cs', f'origin/{target_branch}'], cwd=repo_local_path, capture_output=True, text=True)
                last_commit_date = date_res.stdout.strip()
                
                parsed_yaml = yaml.safe_load(deployment_yaml)
                target_version = None
                for entry in parsed_yaml:
                    if entry.get('date', '') <= last_commit_date:
                        target_version = str(entry.get('version'))
                        break
                        
                if not target_version:
                    target_version = str(parsed_yaml[-1].get('version')) if parsed_yaml else "0.1.0"

                yield f"Last commit on '{target_branch}' is from {last_commit_date}. Matched with deployment changelog version v{target_version}."

                lines = deployment_yaml.split('\n')
                final_yaml_lines = []
                found_target = False
                for line in lines:
                    if not found_target:
                        if line.startswith("- version:") and (f"'{target_version}'" in line or f" {target_version}" in line):
                            found_target = True
                            final_yaml_lines.append(line)
                        elif line.startswith("#") or line.strip() == "---" or line.strip() == "":
                            final_yaml_lines.append(line)
                    else:
                        final_yaml_lines.append(line)
                        
                final_yaml = "\n".join(final_yaml_lines)
                
                # New early return: skip codebase push for main branch release-only
                yield f"Target version determined from deployment changelog: v{target_version}. Proceeding with container tagging without modifying codebase..."
                if dry_run:
                    yield f"[DRY-RUN] Would retag container to 'v{target_version}' and create Git release."
                else:
                    yield from self._finalize_artifacts(project_name, target_version, target_branch, target_branch, final_yaml, audit_log, sql_writer, sql_reader, dry_run)
                return
            else:
                existing_yaml = open(cl_path, 'r').read() if os.path.exists(cl_path) else ""
                start_version, start_date = self._get_top_version_and_date(existing_yaml)
                
                last_commit_res = subprocess.run(['git', 'log', '-1', '--format=%s'], cwd=repo_local_path, capture_output=True, text=True)
                last_commit_msg = last_commit_res.stdout.strip()
                
                is_last_commit_release = (
                    re.match(r'^\[v\d+\.\d+\.\d+.*\]', last_commit_msg) or 
                    last_commit_msg.startswith('HAU Auto-Release:') or 
                    last_commit_msg.startswith('chore(release):')
                )
                
                if is_last_commit_release:
                    yield f"✅ Last commit '{last_commit_msg}' indicates a recent release or auto-sync."
                    target_version_tag = start_version
                    version_match = re.search(r'\[v(\d+\.\d+\.\d+.*?)\]', last_commit_msg)
                    if version_match:
                        target_version_tag = version_match.group(1)
                        
                    if target_branch == 'dev' and not target_version_tag.endswith('-dev'):
                        target_version_tag += '-dev'
                    if not target_version_tag.startswith('v'):
                        target_version_tag = 'v' + target_version_tag
                        
                    yield f"Verifying if container tag '{target_version_tag}' exists in registry..."
                    container_exists = self.registry_manager.container_exists(project_name, target_version_tag)
                    if container_exists:
                        yield f"✅ Container '{target_version_tag}' verified as alive."
                        yield {"success": True, "message": f"✅ Branch '{target_branch}' is already clean and fully documented. No release needed."}
                        return
                    else:
                        is_active, p_status = self._check_active_pipeline(project_name, target_branch)
                        if is_active:
                            yield {"success": False, "message": f"❌ Aborting: The branch '{target_branch}' currently has an active pipeline ({p_status}). Please wait for the container build to finish before retagging."}
                            return
                        yield f"⚠️ Target version '{target_version_tag}' container is missing. Proceeding with retagging..."
                        if dry_run:
                            yield f"[DRY-RUN] Would retag container to '{target_version_tag}' and create Git release."
                        else:
                            final_v = version_match.group(1) if version_match else start_version
                            yield from self._finalize_artifacts(project_name, final_v, target_branch, target_branch, existing_yaml, audit_log, sql_writer, sql_reader, dry_run)
                        return

                yield f"Running deep historical check on '{target_branch}' to detect rogue commits..."
                full_backfill_yaml = None
                latest_feature_branch = None
                last_cl_commit_res = subprocess.run(['git', 'log', '-1', '--first-parent', '--format=%H', 'docs/CHANGELOG.yaml'], cwd=repo_local_path, capture_output=True, text=True)
                last_cl_commit = last_cl_commit_res.stdout.strip()
                for item in orchestrator.run_backfill(repo_local_path, target_branch, start_version=start_version, start_commit=last_cl_commit if last_cl_commit else None, start_date=start_date if not last_cl_commit else None, has_existing=bool(existing_yaml.strip())):
                    if isinstance(item, dict):
                        if "incremental_yaml" in item:
                            full_backfill_yaml = item["incremental_yaml"]
                        if "final_yaml" in item:
                            full_backfill_yaml = item["final_yaml"]
                        if "latest_feature_branch" in item:
                            latest_feature_branch = item["latest_feature_branch"]
                    elif isinstance(item, str):
                        yield f"  {item}"

                if not full_backfill_yaml:
                    yield "No new changelog entries generated. Branch history is already documented."
                    full_backfill_yaml = existing_yaml

                target_version, _ = self._get_top_version_and_date(full_backfill_yaml)
                if target_version == start_version:
                    target_version_tag = target_version
                    if target_branch == 'dev' and not target_version_tag.endswith('-dev'):
                        target_version_tag += '-dev'
                    if not target_version_tag.startswith('v'):
                        target_version_tag = 'v' + target_version_tag
                        
                    yield f"Verifying if container tag '{target_version_tag}' exists in registry..."
                    container_exists = self.registry_manager.container_exists(project_name, target_version_tag)
                    if container_exists:
                        yield f"✅ Container '{target_version_tag}' verified as alive."
                        yield {"success": True, "message": f"✅ Branch '{target_branch}' is already clean and fully documented. No release needed."}
                        return
                    else:
                        is_active, p_status = self._check_active_pipeline(project_name, target_branch)
                        if is_active:
                            yield {"success": False, "message": f"❌ Aborting: The branch '{target_branch}' currently has an active pipeline ({p_status}). Please wait for the container build to finish before retagging."}
                            return
                        yield f"⚠️ Target version '{target_version_tag}' container is missing. Proceeding with retagging..."
                        if dry_run:
                            yield f"[DRY-RUN] Would retag container to '{target_version_tag}' and create Git release."
                            yield "\n[dry-run changelog]\n"
                            yield full_backfill_yaml
                        else:
                            yield from self._finalize_artifacts(project_name, target_version, target_branch, target_branch, full_backfill_yaml, audit_log, sql_writer, sql_reader, dry_run, new_yaml=None)
                        return
                existing_lines = existing_yaml.split('\n')
                insert_idx = 0
                for idx, line in enumerate(existing_lines):
                    stripped = line.strip()
                    if stripped == '' or stripped.startswith('#') or stripped == '---': insert_idx = idx + 1
                    else: break
                existing_entries = "\n".join(existing_lines[insert_idx:])
                final_yaml = full_backfill_yaml.strip() + "\n\n" + existing_entries if existing_entries else full_backfill_yaml
                
                commit_msg_prefix = f"chore(release): backfill missing changelog up to v{target_version} [skip ci]"

            yield f"⚠️ Undocumented commits found. Synchronizing environment to v{target_version}..."
            sync_branch = f"chore/auto-sync-{target_branch}-{int(time.time())}"
            
            if audit_log and sql_writer:
                source_branch_for_audit = latest_feature_branch if latest_feature_branch else sync_branch
                sql_writer.update_git_release_audit_log(
                    audit_log.id, 
                    source_branch=source_branch_for_audit,
                    changelog_generation_method="RELEASE_ONLY_SYNC",
                    version_tag=_get_tag(target_version)
                )

            if dry_run:
                proj_basename = project_name.split('/')[-1]
                yield f"[DRY-RUN] Would create branch '{sync_branch}', commit synced changelog up to v{target_version}, and push with ci.skip."
                yield f"[DRY-RUN] Would create MR for '{sync_branch}' -> '{target_branch}' and auto-merge with [skip ci]."
                yield f"[DRY-RUN] Would commit and sync changelog to deployment repo at 'docs/{proj_basename}/CHANGELOG.yaml'."
                yield from self._finalize_artifacts(project_name, target_version, target_branch, target_branch, final_yaml, audit_log, sql_writer, sql_reader, dry_run, new_yaml=full_backfill_yaml)
                yield "\n[dry-run changelog]\n"
                yield full_backfill_yaml
                return
                
            subprocess.run(['git', 'checkout', '-b', sync_branch], cwd=repo_local_path)
            os.makedirs(os.path.dirname(cl_path), exist_ok=True)
            with open(cl_path, 'w') as f:
                f.write(final_yaml)
                
            subprocess.run(['git', 'config', 'user.name', author_name], cwd=repo_local_path)
            subprocess.run(['git', 'config', 'user.email', author_email], cwd=repo_local_path)
            subprocess.run(['git', 'add', 'docs/CHANGELOG.yaml'], cwd=repo_local_path)
            subprocess.run(['git', 'commit', f'--author={author_name} <{author_email}>', '-m', commit_msg_prefix], cwd=repo_local_path)
            subprocess.run(['git', 'push', '-o', 'ci.skip', '-u', 'origin', sync_branch], cwd=repo_local_path, capture_output=True)

            yield "Triggering environment sync merge (skipping CI)..."
            success, mr_iid, msg = self.pipeline_manager.create_and_merge_mr(
                project_name, sync_branch, target_branch, f"{commit_msg_prefix}\n\n[skip ci]", keep_branch=False, assignee_id=author_id
            )
            if not success:
                yield {"success": False, "message": f"Merge failed: {msg}"}
                return
                
            if audit_log and sql_writer:
                sql_writer.update_git_release_audit_log(audit_log.id, merge_request_id=str(mr_iid))
            
            yield "Waiting for merge to complete (skipping pipeline wait due to [skip ci])...."
            gl = gitlab.Gitlab(self.gitlab_manager.url, private_token=self.gitlab_manager.token, ssl_verify=False)
            project = gl.projects.get(project_name)
            merged = False
            for _ in range(30):
                mr = project.mergerequests.get(mr_iid)
                if mr.state == 'merged':
                    merged = True
                    break
                if mr.state == 'closed':
                    break
                time.sleep(5)
                
            if not merged:
                yield {"success": False, "message": f"MR failed to merge. State: {mr.state}."}
                return

            proj_basename = project_name.split('/')[-1]
            yield f"Synchronizing updated changelog to deployment repository (docs/{proj_basename}/CHANGELOG.yaml)..."
            proj_basename = project_name.split('/')[-1]
            if dry_run:
                yield f"[DRY-RUN] Would commit and sync changelog for v{target_version} to deployment docs."
            else:
                try:
                    self.gitlab_manager.commit_file_api(
                        project_path="ai/halo/deployment",
                        file_path=f"docs/{proj_basename}/CHANGELOG.yaml",
                        branch="main",
                        content=final_yaml,
                        commit_msg=f"chore(docs): sync changelog for {proj_basename} v{target_version} [skip ci]",
                        author_name=author_name,
                        author_email=author_email
                    )
                    yield f"Successfully synced changelog to deployment docs."
                except Exception as e:
                    yield f"Warning: Failed to sync changelog to deployment repo: {e}"

            is_active, p_status = self._check_active_pipeline(project_name, target_branch)
            if is_active:
                yield {"success": False, "message": f"❌ Aborting: The branch '{target_branch}' currently has an active pipeline ({p_status}). Please wait for the container build to finish before retagging."}
                return

            yield from self._finalize_artifacts(project_name, target_version, target_branch, target_branch, final_yaml, audit_log, sql_writer, sql_reader, dry_run, new_yaml=full_backfill_yaml)
            return

        is_promotion = (source_branch == 'dev' and target_branch in ['main', 'master'])

        if not is_promotion and not skip_changelog and not skip_rogue_check:
            yield "Performing pre-flight rogue commit check on target branch..."
            self.gitlab_manager.checkout_project_branch(project_name, target_branch)
            existing_yaml = open(cl_path, 'r').read() if os.path.exists(cl_path) else ""
            start_version, start_date = self._get_top_version_and_date(existing_yaml)
            
            check_yaml = None
            for item in orchestrator.run_backfill(repo_local_path, target_branch, start_version=start_version, start_date=start_date, has_existing=bool(existing_yaml.strip())):
                if isinstance(item, dict) and "final_yaml" in item:
                    check_yaml = item["final_yaml"]
            
            if check_yaml:
                check_version, _ = self._get_top_version_and_date(check_yaml)
                if check_version != start_version:
                    err_msg = f"❌ Rogue undocumented merges detected on '{target_branch}'. Please run with --release-only to sanitize the environment, or use --skip-rogue-check to bypass."
                    yield {"success": False, "message": err_msg}
                    return
            yield "✅ Target branch is clean."

        yield f"Syncing local cache for '{source_branch}'..."
        self.gitlab_manager.checkout_project_branch(project_name, source_branch)

        try:
            gl = gitlab.Gitlab(self.gitlab_manager.url, private_token=self.gitlab_manager.token, ssl_verify=False)
            project = gl.projects.get(project_name)
            compare = project.repository_compare(target_branch, source_branch)
            if not compare.get('commits'):
                yield {"success": False, "message": f"❌ Aborting release: No new commits found in '{source_branch}' compared to '{target_branch}'. Branch is already merged."}
                return
        except Exception as e:
            logger.warning(f"[GitRelease] Failed to compare branches via API: {e}")

        subprocess.run(['git', 'config', 'user.name', author_name], cwd=repo_local_path)
        subprocess.run(['git', 'config', 'user.email', author_email], cwd=repo_local_path)
        
        yield f"Merging 'origin/{target_branch}' into '{source_branch}' locally..."
        merge_res = subprocess.run(['git', 'merge', f'origin/{target_branch}', '-m', f"Auto-sync from {target_branch} [skip ci]"], cwd=repo_local_path, capture_output=True, text=True)
        if merge_res.returncode != 0:
            subprocess.run(['git', 'merge', '--abort'], cwd=repo_local_path)
            stderr_output = merge_res.stderr.strip() or merge_res.stdout.strip()
            err_msg = f"Merge failed locally while syncing '{target_branch}' into '{source_branch}'. Git output: {stderr_output}. Please resolve locally and push."
            yield {"success": False, "message": err_msg}
            return

        existing_yaml = open(cl_path, 'r').read() if os.path.exists(cl_path) else ""
        source_version, _ = self._get_top_version_and_date(existing_yaml)
        
        try:
            target_raw = self.gitlab_manager.fetch_raw_yaml(project_name, 'docs/CHANGELOG.yaml', branch=target_branch)
        except Exception:
            target_raw = ""
            
        target_version, _ = self._get_top_version_and_date(target_raw)

        tv = parse_version(target_version)
        sv = parse_version(source_version)
        next_base = tv if tv >= sv else sv
        next_version = f"{next_base.major}.{next_base.minor}.{next_base.micro + 1}"
        
        if skip_changelog:
            version = source_version
            final_yaml = existing_yaml
        elif is_promotion:
            version = source_version.replace('-dev', '')
            final_yaml = existing_yaml.replace(f"version: '{source_version}'", f"version: '{version}'")
        else:
            version = next_version
            final_yaml = ""

        if audit_log and sql_writer:
            initial_tag = "GENERATING" if not existing_yaml else _get_tag(version)
            sql_writer.update_git_release_audit_log(audit_log.id, version_tag=initial_tag)

        if not skip_changelog:
            if is_promotion:
                yield f"🚀 Promotion flow detected ({source_branch} -> {target_branch}). Bypassing generation and syncing exact state..."
                with open(cl_path, 'w') as f:
                    f.write(final_yaml)
                if audit_log and sql_writer:
                    sql_writer.update_git_release_audit_log(audit_log.id, changelog_generation_method="PROMOTION", version_tag=_get_tag(version))
            else:
                yield f"Generating semantic release notes for v{next_version}..."
                gen_yaml = None
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
                        gen_yaml = item["final_yaml"]
                    elif isinstance(item, str):
                        yield f"  {item}"
                        
                if not gen_yaml:
                    yield "No significant features detected by AI. Skipping changelog file update."
                    final_yaml = existing_yaml
                else:
                    lines_out = gen_yaml.strip().split('\n')
                    formatted_yaml = ""
                    for i, line_out in enumerate(lines_out):
                        if i == 0:
                            if not line_out.startswith("-"): formatted_yaml += f"- {line_out}\n"
                            else: formatted_yaml += f"{line_out}\n"
                        else:
                            formatted_yaml += f"  {line_out}\n"
                            
                    existing_lines = existing_yaml.split('\n')
                    insert_idx = 0
                    for idx, line in enumerate(existing_lines):
                        stripped = line.strip()
                        if stripped == '' or stripped.startswith('#') or stripped == '---': insert_idx = idx + 1
                        else: break
                        
                    new_content = "\n".join(existing_lines[:insert_idx])
                    if new_content and not new_content.endswith('\n'): new_content += "\n"
                    new_content += formatted_yaml + "\n\n" + "\n".join(existing_lines[insert_idx:])
                    final_yaml = new_content
                    
                    with open(cl_path, 'w') as f:
                        f.write(final_yaml)

                    if audit_log and sql_writer:
                        sql_writer.update_git_release_audit_log(audit_log.id, changelog_generation_method="AUTO_GENERATED_LLM", merged_features_json={"raw_yaml": formatted_yaml}, version_tag=_get_tag(version))

            if dry_run:
                yield f"[DRY-RUN] Would commit changelog and push to '{source_branch}'."
            else:
                subprocess.run(['git', 'add', 'docs/CHANGELOG.yaml'], cwd=repo_local_path)
                commit_res = subprocess.run(['git', 'commit', f'--author={author_name} <{author_email}>', '-m', f"chore(release): auto-generate changelog for v{version}"], cwd=repo_local_path, capture_output=True, text=True)
                if commit_res.returncode != 0 and "nothing to commit" not in commit_res.stdout:
                    yield {"success": False, "message": f"Failed to commit changelog: {commit_res.stderr}"}
                    return
                push_res = subprocess.run(['git', 'push', '-o', 'ci.skip', 'origin', source_branch], cwd=repo_local_path, capture_output=True, text=True)
                if push_res.returncode != 0:
                    yield "Push rejected. Attempting pull --rebase..."
                    subprocess.run(['git', 'pull', '--rebase', 'origin', source_branch], cwd=repo_local_path)
                    push_res_2 = subprocess.run(['git', 'push', '-o', 'ci.skip', 'origin', source_branch], cwd=repo_local_path, capture_output=True, text=True)
                    if push_res_2.returncode != 0:
                        yield {"success": False, "message": f"Failed to push changelog: {push_res_2.stderr}"}
                        return

            proj_basename = project_name.split('/')[-1]
            
            deployment_yaml = ""
            try:
                deployment_yaml = self.gitlab_manager.fetch_raw_yaml("ai/halo/deployment", f"docs/{proj_basename}/CHANGELOG.yaml", branch="main")
            except Exception:
                pass
                
            if deployment_yaml:
                deploy_top_version, _ = self._get_top_version_and_date(deployment_yaml)
                
                v_push = version.replace('-dev', '') if version else '0.0.0'
                v_deploy = deploy_top_version.replace('-dev', '') if deploy_top_version else '0.0.0'
                
                if parse_version(v_deploy) > parse_version(v_push):
                    yield {"success": False, "message": f"Error: Deployment repository has a newer changelog version ({deploy_top_version}) than the one being pushed ({version}). Aborting sync to prevent data loss."}
                    return

            if dry_run:
                yield f"[DRY-RUN] Would commit and sync changelog for v{version} to deployment docs."
            else:
                try:
                    self.gitlab_manager.commit_file_api(
                        project_path="ai/halo/deployment",
                        file_path=f"docs/{proj_basename}/CHANGELOG.yaml",
                        branch="main",
                        content=open(cl_path, 'r').read(),
                        commit_msg=f"chore(docs): sync changelog for {proj_basename} v{version}",
                        author_name=author_name,
                        author_email=author_email
                    )
                    yield f"Successfully synced changelog to deployment docs."
                except Exception as e:
                    yield f"Warning: Failed to sync changelog to deployment repo: {e}"

        parsed_new = yaml.safe_load(final_yaml) if final_yaml else []
        changelog_entry = parsed_new[0] if isinstance(parsed_new, list) and len(parsed_new) > 0 else {}
        yield "Generating commit message via LLM..."
        commit_msg = self._generate_llm_commit_msg(version, changelog_entry)
        yield f"Commit message generated: {commit_msg}"

        if dry_run:
            yield f"[DRY-RUN] Would create and merge MR from '{source_branch}' to '{target_branch}'."
        else:
            yield "Triggering Merge via GitLab API..."
            success, mr_iid, msg = self.pipeline_manager.create_and_merge_mr(
                project_name, source_branch, target_branch, commit_msg, keep_branch=keep_branch, assignee_id=author_id
            )
            if not success:
                yield {"success": False, "message": msg}
                return
            if audit_log and sql_writer and mr_iid:
                sql_writer.update_git_release_audit_log(audit_log.id, merge_request_id=str(mr_iid))
            yield f"Successfully queued merge for '{source_branch}' into '{target_branch}'."
            
            yield from self._finalize_release(project_name, mr_iid, version, target_branch, final_yaml, audit_log, sql_writer, sql_reader, debug, dry_run, source_branch)

    def _finalize_release(self, project_name, mr_iid, target_version, mr_target_branch, final_yaml, audit_log, sql_writer, sql_reader, debug, dry_run, source_branch):
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
            yield {"success": False, "message": err_msg}
            return

        merged = False
        mr = None
        for _ in range(30):
            mr = project.mergerequests.get(mr_iid)
            if mr.state == 'merged':
                merged = True
                break
            if mr.state == 'closed':
                break
            yield f"Merge in progress (State: {mr.state}, Status: {mr.detailed_merge_status})..."
            time.sleep(5)

        if not merged:
            err_msg = f"MR failed to merge. State: {mr.state}, Status: {mr.detailed_merge_status}. Aborting release."
            yield {"success": False, "message": err_msg}
            return

        yield from self._finalize_artifacts(project_name, target_version, source_branch, mr.target_branch, final_yaml, audit_log, sql_writer, sql_reader, dry_run)

    def _finalize_artifacts(self, project_name, version, source_slug_branch, target_branch, final_yaml, audit_log, sql_writer, sql_reader, dry_run, new_yaml=None):
        target_version_tag = version
        if target_branch == 'dev' and not target_version_tag.endswith('-dev'):
            target_version_tag += '-dev'
        if not target_version_tag.startswith('v'):
            target_version_tag = 'v' + target_version_tag

        slug = re.sub(r'[^a-z0-9]+', '-', source_slug_branch.lower()).strip('-')[:63]
        yield f"Retagging container from '{slug}' to '{target_version_tag}'..."

        if dry_run:
            yield f"[DRY-RUN] Would retag container from '{slug}' to '{target_version_tag}'."
        else:
            retag_success, retag_msg = self.registry_manager.retag_container(project_name, slug, target_version_tag)
            if not retag_success:
                yield {"success": False, "message": f"Artifact processing failed: Container retagging failed: {retag_msg}"}
                return

        yield f"Creating Git Tag '{target_version_tag}' on '{target_branch}'..."
        if dry_run:
            yield f"[DRY-RUN] Would create Git Tag '{target_version_tag}' and native GitLab Release."
        else:
            tag_success, tag_msg = self.gitlab_manager.create_tag(project_name, target_version_tag, target_branch, message="Release tag [skip ci]")
            if not tag_success and "already exists" not in tag_msg.lower() and "400" not in tag_msg.lower():
                yield {"success": False, "message": f"Failed to create Git tag: {tag_msg}"}
                return
            
            if not tag_success:
                yield f"ℹ️ Git tag '{target_version_tag}' already exists, proceeding to Release creation..."
            
            yield f"Creating native GitLab Release for '{target_version_tag}'..."
            try:
                parsed_source = yaml.safe_load(new_yaml if new_yaml else final_yaml) if (new_yaml or final_yaml) else []
                if isinstance(parsed_source, list) and len(parsed_source) > 0:
                    release_desc = ""
                    for entry in parsed_source:
                        entry_tag = entry.get('version', target_version_tag)
                        if not entry_tag.startswith('v'): entry_tag = 'v' + entry_tag
                        if target_branch == 'dev' and not entry_tag.endswith('-dev'): entry_tag += '-dev'
                        release_desc += self._format_release_notes(entry_tag, entry) + "\n\n"
                    release_desc = release_desc.strip()
                else:
                    release_desc = self._format_release_notes(target_version_tag, {})

                rel_success, rel_msg = self.gitlab_manager.create_release(project_name, target_version_tag, release_desc)
                if not rel_success:
                    yield {"success": False, "message": f"Failed to create GitLab Release: {rel_msg}"}
                    return
                yield f"✅ GitLab Release '{target_version_tag}' created successfully!"
            except Exception as e:
                yield {"success": False, "message": f"Failed to format or create GitLab Release: {e}"}
                return

        if audit_log and sql_writer:
            sql_writer.update_git_release_audit_log(audit_log.id, status="SUCCESS", version_tag=target_version_tag)

        yield "Syncing updated Git Inventory to database..."
        try:
            self.inventory_manager.sync_database_inventory(sql_reader, sql_writer, project_name)
            yield "✅ Git Inventory successfully synced."
        except Exception as e:
            yield f"⚠️ Warning: Failed to sync git inventory: {e}"

        yield {"success": True, "message": f"{'[DRY-RUN] ' if dry_run else ''}Release completed successfully! ✅"}

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
            time.sleep(5)
            
        if not merged:
            err_msg = f"MR failed to merge. State: {mr.state}, Status: {mr.detailed_merge_status}."
            yield {"success": False, "message": err_msg}
            return
            
        yield "Pipeline merge complete!"
        
        target_version = "0.1.0"
        changelog_data = []
        try:
            f = project.files.get(file_path='docs/CHANGELOG.yaml', ref=mr.target_branch)
            changelog_content = base64.b64decode(f.content).decode('utf-8')
            changelog_data = yaml.safe_load(changelog_content)
            if isinstance(changelog_data, list) and len(changelog_data) > 0:
                target_version = str(changelog_data[0].get('version', '0.1.0'))
        except Exception as e:
            logger.warning(f"[GitRetry] Could not parse version from changelog for retagging: {e}")
            
        if target_version != "0.1.0":
            yield from self._finalize_artifacts(project_name, target_version, mr.source_branch, mr.target_branch, None, audit_log, sql_writer, sql_reader, False)

        yield {"success": True, "message": f"Retry and Release of MR !{mr.iid} completed successfully! ✅"}