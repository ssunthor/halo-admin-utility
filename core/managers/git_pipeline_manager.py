import logging
import time
from datetime import datetime, timezone, timedelta
import gitlab

logger = logging.getLogger(__name__)

class GitPipelineManager:
    def __init__(self, config):
        self.config = config
        self.url = self.config['external_services']['gitlab']['url']
        self.token = self.config['external_services']['gitlab'].get('bot_token')

    def create_and_merge_mr(self, project_path, source_branch, target_branch, commit_message, keep_branch=True, assignee_id=None):
        try:
            gl = gitlab.Gitlab(self.url, private_token=self.token, ssl_verify=False)
            project = gl.projects.get(project_path)
            
            mrs = project.mergerequests.list(source_branch=source_branch, target_branch=target_branch, state='opened')
            if mrs:
                mr = mrs[0]
            else:
                mr_payload = {
                    'source_branch': source_branch,
                    'target_branch': target_branch,
                    'title': f"HAU Auto-Release: {source_branch} -> {target_branch}",
                    'description': commit_message,
                    'remove_source_branch': not keep_branch
                }
                if assignee_id:
                    mr_payload['assignee_ids'] = [assignee_id]
                mr = project.mergerequests.create(mr_payload)
            
            active_pipeline = False
            for _ in range(30):
                mr = project.mergerequests.get(mr.iid)
                mr_pipelines = mr.pipelines.list()
                
                if mr_pipelines and mr_pipelines[0].status in ['running', 'pending', 'created']:
                    active_pipeline = True
                    
                if mr.detailed_merge_status not in ["checking", "preparing", "unchecked"]:
                    if mr.detailed_merge_status == "mergeable":
                        break
                    if mr.detailed_merge_status == "ci_still_running" or mr.detailed_merge_status == "ci_must_pass":
                        if active_pipeline:
                            break
                            
                time.sleep(2)
                
            remove_source = not keep_branch
            merge_msg = commit_message
            
            try:
                if mr.detailed_merge_status == "mergeable" and not active_pipeline:
                    mr.merge(merge_commit_message=merge_msg, should_remove_source_branch=remove_source)
                else:
                    mr.merge(merge_commit_message=merge_msg, should_remove_source_branch=remove_source, merge_when_pipeline_succeeds=True)
            except gitlab.exceptions.GitlabError as e:
                mr = project.mergerequests.get(mr.iid)
                status = mr.detailed_merge_status
                if status == "conflict":
                    return False, mr.iid, f"Merge conflicts exist. Please resolve them on GitLab."
                return False, mr.iid, f"GitLab rejected merge (405). Detailed MR Status: '{status}'. Raw Error: {str(e)}"
                
            return True, mr.iid, f"Successfully queued merge for '{source_branch}' into '{target_branch}'."
            
        except Exception as e:
            return False, None, f"{str(e)}"

    def monitor_pipeline(self, project_path, ref=None, mr_iid=None, pipeline_id=None, debug=False):
        gl = gitlab.Gitlab(self.url, private_token=self.token, ssl_verify=False)
        project = gl.projects.get(project_path)
        
        pipeline = None
        if pipeline_id:
            pipeline = project.pipelines.get(pipeline_id)
        else:
            for _ in range(15):
                if mr_iid:
                    mr = project.mergerequests.get(mr_iid)
                    if mr.state == 'merged' and mr.merge_commit_sha:
                        pipelines = project.pipelines.list(ref=mr.target_branch, sha=mr.merge_commit_sha, order_by='id', sort='desc')
                        if pipelines:
                            pipeline = project.pipelines.get(pipelines[0].id)
                            break
                    else:
                        pipelines = mr.pipelines.list()
                        if pipelines:
                            latest_pipeline = pipelines[0]
                            created_at = datetime.fromisoformat(latest_pipeline.created_at.replace('Z', '+00:00'))
                            if (datetime.now(timezone.utc) - created_at) < timedelta(seconds=30) or latest_pipeline.status in ['running', 'pending', 'created']:
                                pipeline = project.pipelines.get(latest_pipeline.id)
                                break
                elif ref:
                    pipelines = project.pipelines.list(ref=ref, order_by='id', sort='desc')
                    if pipelines:
                        latest_pipeline = pipelines[0]
                        created_at = datetime.fromisoformat(latest_pipeline.created_at.replace('Z', '+00:00'))
                        if (datetime.now(timezone.utc) - created_at) < timedelta(seconds=30) or latest_pipeline.status in ['running', 'pending', 'created']:
                            pipeline = project.pipelines.get(latest_pipeline.id)
                            break
                time.sleep(1)
            
        if not pipeline:
            yield "No active pipeline found after 15 seconds."
            return
            
        yield f"Monitoring Pipeline #{pipeline.id} on '{pipeline.ref}' (Web: {pipeline.web_url})..."
        
        job_states = {}
        job_trace_offsets = {}
        job_start_times = {}
        job_last_keepalive = {}
        telemetry = {"jobs": [], "footprint_mb": None}
        failed_blocking_stages = set()
        canceled_jobs = set()
        
        while pipeline.status in ['running', 'pending', 'created', 'waiting_for_resource', 'preparing']:
            jobs = pipeline.jobs.list(all=True)
            active_jobs = 0
            for job in jobs:
                prev_status = job_states.get(job.name)
                
                if job.status == 'running' and prev_status != 'running':
                    job_start_times[job.name] = time.time()
                
                is_terminal_transition = (job.status in ['success', 'failed', 'canceled'] and prev_status not in ['success', 'failed', 'canceled'])
                is_slow_running = (job.status == 'running' and time.time() - job_start_times.get(job.name, time.time()) > 5)
                
                if debug and (is_slow_running or is_terminal_transition):
                    try:
                        p_job = project.jobs.get(job.id)
                        trace_bytes = p_job.trace()
                        if trace_bytes:
                            trace_str = trace_bytes.decode('utf-8', errors='replace')
                            lines = trace_str.split('\n')
                            last_offset = job_trace_offsets.get(job.name, 0)
                            if len(lines) > last_offset:
                                for line in lines[last_offset:]:
                                    if line.strip():
                                        yield f"      [{job.name}] {line.strip()}"
                                job_trace_offsets[job.name] = len(lines)
                    except Exception:
                        pass
                
                if prev_status != job.status:
                    if job.status == 'success':
                        duration_val = getattr(job, 'duration', None)
                        if duration_val is not None:
                            duration = float(duration_val)
                        else:
                            duration = time.time() - job_start_times.get(job.name, time.time())
                        yield f"  ✅ Job '{job.name}' (Stage: {job.stage}) completed successfully in {duration:.1f}s."
                    elif job.status == 'failed':
                        allow_failure = getattr(job, 'allow_failure', False)
                        if allow_failure:
                            yield f"  ⚠️ Job '{job.name}' (Stage: {job.stage}) failed (allowed to fail)."
                        else:
                            yield f"  ❌ Job '{job.name}' (Stage: {job.stage}) failed."
                        try:
                            p_job = project.jobs.get(job.id)
                            trace_bytes = p_job.trace()
                            if trace_bytes:
                                trace_str = trace_bytes.decode('utf-8', errors='replace')
                                lines = trace_str.split('\n')
                                yield f"    --- Last 50 lines of trace for {job.name} ---"
                                for line in lines[-50:]:
                                    if line.strip():
                                        yield f"      {line.strip()}"
                                yield f"    ----------------------------------------"
                        except Exception as e:
                            yield f"      (Could not fetch trace: {e})"
                        
                        if not allow_failure:
                            failed_blocking_stages.add(job.stage)
                            
                    elif job.status == 'running':
                        yield f"  ▶️ Job '{job.name}' (Stage: {job.stage}) is now RUNNING..."
                    job_states[job.name] = job.status
                    
                if job.status == 'running':
                    now = time.time()
                    last_ka = job_last_keepalive.get(job.name, job_start_times.get(job.name, now))
                    if now - last_ka >= 60:
                        elapsed = now - job_start_times.get(job.name, now)
                        yield f"  ⏳ Job '{job.name}' (Stage: {job.stage}) is still running... ({int(elapsed)}s elapsed)"
                        job_last_keepalive[job.name] = now
                    

                if job.status in ['running', 'pending', 'created', 'waiting_for_resource'] and job.id not in canceled_jobs:
                    if failed_blocking_stages and job.stage not in failed_blocking_stages:
                        yield f"  🛑 Canceling job '{job.name}' (Stage: {job.stage}) to save time (previous required stage failed)."
                        try:
                            p_job = project.jobs.get(job.id)
                            p_job.cancel()
                            canceled_jobs.add(job.id)
                        except Exception as e:
                            yield f"  (Could not cancel job: {e})"

                if job.status in ['running', 'pending']:
                    active_jobs += 1
                            
            current_telemetry = {"jobs": []}
            for j in jobs:
                job_dur = getattr(j, 'duration', None)
                if j.status == 'running' and j.name in job_start_times:
                    job_dur = time.time() - job_start_times[j.name]
                current_telemetry["jobs"].append({
                    "id": j.id,
                    "name": j.name,
                    "stage": j.stage,
                    "status": j.status,
                    "duration": job_dur,
                    "allow_failure": getattr(j, 'allow_failure', False),
                    "web_url": getattr(j, 'web_url', None)
                })
            yield {"is_intermediate": True, "telemetry": current_telemetry}
            
            if active_jobs == 0 and not debug:
                yield f"Pipeline Status: {pipeline.status.upper()} (Transitioning stages or finalizing...)"
                
            time.sleep(5)
            pipeline = project.pipelines.get(pipeline.id)
            
        if pipeline.status == 'success':
            yield f"Pipeline #{pipeline.id} completed successfully! ✅"
            jobs = pipeline.jobs.list(all=True)
            for job in jobs:
                if job.status == 'failed':
                    yield f"  ⚠️ Note: Job '{job.name}' (Stage: {job.stage}) failed but was allowed to fail. (Web: {job.web_url})"
                    try:
                        p_job = project.jobs.get(job.id)
                        trace_bytes = p_job.trace()
                        if trace_bytes:
                            trace_str = trace_bytes.decode('utf-8', errors='replace')
                            lines = trace_str.split('\n')
                            yield f"    --- Last 50 lines of trace for {job.name} ---"
                            for line in lines[-50:]:
                                if line.strip():
                                    yield f"      {line.strip()}"
                            yield f"    ----------------------------------------"
                    except Exception as e:
                        yield f"      (Could not fetch trace: {e})"
            
            try:
                repos = project.repositories.list()
                if repos:
                    tags = repos[0].tags.list(get_all=True)
                    if tags:
                        import re
                        expected_tag_name = None
                        if pipeline.ref.startswith('refs/merge-requests/'):
                            try:
                                mr_iid_from_ref = int(pipeline.ref.split('/')[2])
                                mr_obj = project.mergerequests.get(mr_iid_from_ref)
                                expected_tag_name = re.sub(r'[^a-z0-9]+', '-', mr_obj.source_branch.lower()).strip('-')[:63]
                            except Exception:
                                pass
                        else:
                            expected_tag_name = re.sub(r'[^a-z0-9]+', '-', pipeline.ref.lower()).strip('-')[:63]
                            
                        target_tag = None
                        if expected_tag_name:
                            for t in tags:
                                if t.name == expected_tag_name:
                                    target_tag = repos[0].tags.get(id=t.name)
                                    break
                                    
                        if not target_tag:
                            tags.sort(key=lambda t: getattr(t, 'created_at', ''), reverse=True)
                            target_tag = repos[0].tags.get(id=tags[0].name)
                            
                        total_size_bytes = target_tag.attributes.get('total_size', 0)
                        if total_size_bytes:
                            size_mb = total_size_bytes / (1024 * 1024)
                            telemetry["footprint_mb"] = round(size_mb, 2)
                            yield f"  📦 Container '{target_tag.name}' footprint: {size_mb:.2f} MB"
            except Exception as e:
                yield f"  (Could not fetch container size: {e})"
                
            for job in jobs:
                telemetry["jobs"].append({
                    "id": job.id,
                    "name": job.name,
                    "stage": job.stage,
                    "status": job.status,
                    "duration": job.duration,
                    "web_url": job.web_url
                })
                
            yield {"pipeline_success": True, "telemetry": telemetry}
        else:
            yield f"Pipeline #{pipeline.id} failed with status: {pipeline.status.upper()} ❌"
            jobs = pipeline.jobs.list(all=True)
            for job in jobs:
                job_data = {
                    "id": job.id,
                    "name": job.name,
                    "stage": job.stage,
                    "status": job.status,
                    "duration": job.duration,
                    "web_url": job.web_url,
                    "trace": None
                }
                if job.status == 'failed':
                    allow_failure = getattr(job, 'allow_failure', False)
                    status_str = " (allowed to fail)" if allow_failure else ""
                    yield f"  - Failed Job: {job.name} (Stage: {job.stage}){status_str} (Web: {job.web_url})"
                    try:
                        p_job = project.jobs.get(job.id)
                        trace_bytes = p_job.trace()
                        if trace_bytes:
                            trace_str = trace_bytes.decode('utf-8', errors='replace')
                            lines = trace_str.split('\n')
                            trace_lines = [line.strip() for line in lines[-100:] if line.strip()]
                            job_data["trace"] = trace_lines
                            
                            yield f"    --- Last {len(trace_lines)} lines of trace for {job.name} ---"
                            for line in trace_lines[-50:]:
                                yield f"      {line}"
                            yield f"    ----------------------------------------"
                    except Exception as e:
                        yield f"      (Could not fetch trace: {e})"
                telemetry["jobs"].append(job_data)
                
            yield {"pipeline_success": False, "pipeline_id": pipeline.id, "pipeline_status": pipeline.status, "telemetry": telemetry}