import click
import json
from cli.utils import print_grpc_json, handle_grpc_errors, get_hau_stub

@click.group(name='git')
def git_cli():
    """Git workspace and repository operations."""
    pass

@git_cli.command(name='sync-inventory')
@click.option("--grpc", "as_grpc", is_flag=True, help="Output raw gRPC response as JSON")
@handle_grpc_errors
@click.pass_context
def git_sync_inventory(ctx, as_grpc):
    """Synchronizes Git inventory, branches, and container tags into the database."""
    import hau_pb2
    stub = get_hau_stub(ctx.obj['config'])
    req = hau_pb2.GitInventorySyncRequest()
    click.echo("Starting Git Inventory Sync. This may take a moment to fetch and upsert...")
    resp = stub.GitInventorySync(req)
    
    if as_grpc:
        print_grpc_json(resp)
        return
        
    if not resp.success:
        click.secho(f"Failed: {resp.message}", fg='red')
    else:
        click.secho(f"Success: {resp.message}", fg='green', bold=True)

@git_cli.command(name='containers')
@click.option("--grpc", "as_grpc", is_flag=True, help="Output raw gRPC response as JSON")
@click.option("--project", "-p", default=None, help="Filter containers by project name")
@handle_grpc_errors
@click.pass_context
def git_containers(ctx, as_grpc, project):
    """Lists the available container registry tags for the HALO repository."""
    import hau_pb2
    stub = get_hau_stub(ctx.obj['config'])
    req = hau_pb2.GitContainersRequest()
    resp = stub.GitContainers(req)
    
    if as_grpc:
        print_grpc_json(resp)
        return
        
    if not resp.success:
        click.secho(f"❌ {resp.message}", fg='red')
        return
        
    try:
        tags = json.loads(resp.result_json)
        click.secho(f"\nAvailable Container Tags for ai/halo:\n", fg='cyan', bold=True)
        if not tags:
            click.echo("No tags found.")
            return
            
        grouped_tags = {}
        for tag in tags:
            tag_project = tag.get('project', 'unknown')
            if project and project not in tag_project:
                continue
            if tag_project not in grouped_tags:
                grouped_tags[tag_project] = []
            grouped_tags[tag_project].append(tag)
            
        for project_name, project_tags in grouped_tags.items():
            click.secho(f"\n📁 {project_name}", fg='magenta', bold=True)
            for t in project_tags:
                tag_name = t['name']
                path = t['path']
                created = t.get('created_at', 'unknown')
                author = t.get('author', 'Unknown')
                
                status_flag = ""
                stable_tags = ['main', 'latest', 'demo', 'dev', 'stable', 'master']
                
                is_git_tag = t.get('is_git_tag')
                if is_git_tag:
                    status_flag = click.style(" [📦 Release]", fg='green', bold=True)
                elif not t.get('branch_exists') and tag_name not in stable_tags:
                    status_flag = click.style(" [⚠️ Branch Deleted]", fg='yellow', bold=True)
                
                click.echo(f"  [TAG] {click.style(tag_name, fg='cyan', bold=True)}{status_flag} "
                           f"({click.style(path, fg='white', dim=True)}) "
                           f"- Created: {created} | Author: {author}")
        click.echo()
    except json.JSONDecodeError:
        click.secho(f"Failed to parse JSON response: {resp.result_json}", fg='red')

@git_cli.command(name='inventory')
@click.option("--grpc", "as_grpc", is_flag=True, help="Output raw gRPC response as JSON")
@click.option("--project", default=None, help="Project name or full path to filter inventory by")
@handle_grpc_errors
@click.pass_context
def git_inventory(ctx, as_grpc, project):
    """Fetches a high-speed Git inventory using GitLab's GraphQL API."""
    import hau_pb2
    stub = get_hau_stub(ctx.obj['config'])
    req = hau_pb2.GitInventoryRequest(project_name=project if project else "")
    click.echo(f"Fetching Git Inventory{' for ' + project if project else ''} from DB...")
    resp = stub.GitInventory(req)
    
    if as_grpc:
        print_grpc_json(resp)
        return
        
    if not resp.success:
        click.secho(f"❌ {resp.message}", fg='red')
        return
        
    try:
        data = json.loads(resp.result_json)
        projects = data.get("projects", [])
        click.secho(f"\nGit Inventory{' for ' + project if project else ''}:\n", fg='cyan', bold=True)
        if not projects:
            click.echo("No projects found.")
            return
            
        for p in projects:
            path_name = p.get('fullPath') or p.get('path', 'unknown-path')
            click.secho(f"📁 {path_name}", fg='magenta', bold=True)
            inv = p.get('inventory', {})
            
            def print_container(c, label=""):
                active_deployments = c.get('active_deployments', 0)
                namespaces = c.get('active_namespaces', [])
                ns_str = f" in {', '.join(namespaces)}" if namespaces else ""
                active_str = click.style(f" [🚀 Active Deployments: {active_deployments}{ns_str}]", fg='green', bold=True) if active_deployments > 0 else ""
                tag_name = click.style(c.get('tag', c.get('container_tag', '')), fg='cyan', bold=True)
                author = c.get('author', c.get('branch_author', 'Unknown'))
                created = c.get('created_at', c.get('container_created', 'unknown'))
                
                extra = ""
                if 'branch' in c:
                    extra = f" (Branch: {c['branch']})"
                if 'source_feature' in c and c['source_feature'] != "Unknown":
                    extra = f" (Feature: {c['source_feature']})"
                
                click.echo(f"      - {label}{tag_name}{extra}{active_str} | Created: {created} | Author: {author}")
                
            if inv.get('releases'):
                click.secho(f"   🚀 Releases:", fg='green')
                for c in inv['releases']: print_container(c, "📦 ")
            
            if inv.get('pre_releases'):
                click.secho(f"   🚧 Pre-releases (-dev):", fg='yellow')
                for c in inv['pre_releases']: print_container(c, "📦 ")
                
            if inv.get('features'):
                click.secho(f"   ✨ Active Features:", fg='blue')
                for c in inv['features']: print_container(c, "📦 ")
                
            if inv.get('standalone_features'):
                click.secho(f"   👻 Standalone Containers (Branch Deleted):", fg='red')
                for c in inv['standalone_features']: print_container(c, "📦 ")
                
            if inv.get('active_branches_without_containers'):
                click.secho(f"   🌱 Active Branches (No Container):", fg='cyan', dim=True)
                for b in inv['active_branches_without_containers']:
                    click.echo(f"      - 🌿 {click.style(b['branch'], fg='white', bold=True)} | Author: {b.get('author', 'Unknown')}")
            click.echo()
            
    except json.JSONDecodeError:
        click.secho(f"Failed to parse JSON response: {resp.result_json}", fg='red')

@git_cli.command(name='sync')
@click.argument('target', default='halo')
@click.option("--grpc", "as_grpc", is_flag=True, help="Output raw gRPC response as JSON")
@handle_grpc_errors
@click.pass_context
def git_sync(ctx, target, as_grpc):
    """Clones or pulls the latest changes for HALO or templates locally."""
    import hau_pb2
    stub = get_hau_stub(ctx.obj['config'])
    req = hau_pb2.GitSyncRequest(target=target)
    
    if target == 'templates':
        click.echo("Syncing ai/gitlab-ci-templates to local cache... This may take a moment.")
    else:
        click.echo("Syncing all ai/halo repositories to local cache (defaulting to 'dev' branch)... This may take a moment.")
        
    resp = stub.GitSync(req)
    
    if as_grpc:
        print_grpc_json(resp)
        return
        
    if resp.success:
        click.secho(f"\n{resp.message}", fg='green')
    else:
        click.secho(f"\n❌ Sync Failed: {resp.message}", fg='red')

@git_cli.command(name='list')
@click.option("--grpc", "as_grpc", is_flag=True, help="Output raw gRPC response as JSON")
@handle_grpc_errors
@click.pass_context
def git_list(ctx, as_grpc):
    """Lists locally cloned repositories and their available branches."""
    import hau_pb2
    stub = get_hau_stub(ctx.obj['config'])
    req = hau_pb2.GitListCacheRequest()
    resp = stub.GitListCache(req)
    
    if as_grpc:
        print_grpc_json(resp)
        return
        
    if resp.success:
        try:
            data = json.loads(resp.result_json)
            click.echo()
            for repo in data:
                click.echo(f"Repository: {repo['repository']} (Locally active branch: {repo['active_branch']})")
                default_branch = repo.get('default_branch', 'main')
                for b in repo.get('branches', []):
                    is_default = " [default]" if b == default_branch else ""
                    click.echo(f"  - {b}{is_default}")
                click.echo()
        except json.JSONDecodeError:
            click.echo(f"\n{resp.result_json}\n")
    else:
        click.secho(f"\n❌ List Failed: {resp.message}", fg='red')

@git_cli.command(name='push')
@click.option('-m', '--message', required=True, help='Commit message')
@click.option("--grpc", "as_grpc", is_flag=True, help="Output raw gRPC response as JSON")
@handle_grpc_errors
@click.pass_context
def git_push(ctx, message, as_grpc):
    """Commits and pushes all local changes in the cache to GitLab."""
    import hau_pb2
    stub = get_hau_stub(ctx.obj['config'])
    req = hau_pb2.GitPushRequest(commit_message=message)
    click.echo(f"Committing and pushing changes with message: '{message}'...")
    resp = stub.GitPush(req)
    
    if as_grpc:
        print_grpc_json(resp)
        return
        
    if resp.success:
        click.secho(f"\n{resp.message}", fg='green')
    else:
        click.secho(f"\n❌ Push Failed: {resp.message}", fg='red')

@git_cli.command(name='checkout')
@click.argument('project')
@click.argument('branch')
@click.option("--grpc", "as_grpc", is_flag=True, help="Output raw gRPC response as JSON")
@handle_grpc_errors
@click.pass_context
def git_checkout(ctx, project, branch, as_grpc):
    """Checks out a specific branch for a project in the local cache."""
    import hau_pb2
    stub = get_hau_stub(ctx.obj['config'])
    req = hau_pb2.GitCheckoutRequest(project_name=project, branch_name=branch)
    click.echo(f"Checking out and pulling branch '{branch}' for project '{project}'...")
    resp = stub.GitCheckout(req)
    
    if as_grpc:
        print_grpc_json(resp)
        return
        
    if resp.success:
        click.secho(f"\n✅ {resp.message}", fg='green')
    else:
        click.secho(f"\n❌ Checkout Failed: {resp.message}", fg='red')

@git_cli.command(name='release')
@click.option('--repo', required=True, help="Project name (e.g. ai/halo/pipelines/netflow-dfp)")
@click.option('--source', default='feat/changelog', help="Source branch to merge from")
@click.option('--target', default='dev', help="Target branch to merge to")
@click.option('--skip-changelog', is_flag=True, help="Skip generating changelog if missing")
@click.option('--delete-branch', is_flag=True, help="Delete the feature branch after merging (default is to keep it)")
@click.option('--debug', is_flag=True, help="Stream detailed job trace logs from the pipeline")
@click.option('--author', type=str, help="Override author (will resolve to GitLab user)")
@click.pass_context
def git_release(ctx, repo, source, target, skip_changelog, delete_branch, debug, author):
    """Executes a GitOps merge and release (with pipeline monitoring and tagging)."""
    import hau_pb2
    stub = get_hau_stub(ctx.obj['config'])
    
    req = hau_pb2.GitReleaseRequest(
        project_name=repo,
        source_branch=source,
        target_branch=target,
        skip_changelog_generation=skip_changelog,
        keep_branch=not delete_branch,
        debug=debug,
        author=author or ""
    )
    
    click.echo(f"Initiating release pipeline for {repo} ({source} -> {target})...")
    
    try:
        responses = stub.GitRelease(req)
        for response in responses:
            if not response.success:
                click.secho(f"❌ {response.message}", fg="red")
            else:
                if "Pipeline passed" in response.message:
                    click.secho(f"✅ {response.message}", fg="green")
                elif "Monitoring Pipeline" in response.message:
                    click.secho(f"⏳ {response.message}", fg="cyan")
                else:
                    click.echo(response.message)
    except Exception as e:
        click.secho(f"gRPC Error: {str(e)}", fg="red")

@git_cli.command(name="retry")
@click.option('--repo', required=True, help="Project name (e.g. ai/halo/pipelines/netflow-dfp)")
@click.option('--pipeline', type=int, help="ID of the pipeline to retry")
@click.option('--merge', type=int, help="ID of the Merge Request to retry")
@click.option('--skip-warnings', is_flag=True, help="Skip retrying if the pipeline is already successful (ignore warnings)")
@click.option('--debug', is_flag=True, help="Stream detailed job trace logs from the pipeline")
@click.pass_context
def git_retry(ctx, repo, pipeline, merge, skip_warnings, debug):
    """Retries a failed GitLab pipeline or Merge Request and streams its progress."""
    if not pipeline and not merge:
        click.secho("❌ You must provide either --pipeline or --merge", fg="red")
        return
    if pipeline and merge:
        click.secho("❌ You cannot provide both --pipeline and --merge", fg="red")
        return

    import hau_pb2
    stub = get_hau_stub(ctx.obj['config'])
    
    req = hau_pb2.GitRetryRequest(
        project_name=repo,
        pipeline_id=pipeline or 0,
        merge_id=merge or 0,
        skip_warnings=skip_warnings,
        debug=debug
    )
    
    if merge:
        click.echo(f"Initiating retry for MR !{merge} on {repo}...")
    else:
        click.echo(f"Initiating retry for pipeline #{pipeline} on {repo}...")
    
    try:
        responses = stub.GitRetry(req)
        for response in responses:
            if not response.success:
                click.secho(f"❌ {response.message}", fg="red")
            else:
                if "✅" in response.message:
                    click.secho(response.message, fg="green")
                elif "❌" in response.message:
                    click.secho(response.message, fg="red")
                elif "⚠️" in response.message:
                    click.secho(response.message, fg="yellow")
                else:
                    click.echo(response.message)
    except Exception as e:
        click.secho(f"RPC Error: {e}", fg="red")

@git_cli.command(name="audit")
@click.option('--id', type=str, help="ID of the specific audit log to view details")
@click.option('--repo', type=str, help="Filter by project name")
@click.option("--grpc", "as_grpc", is_flag=True, help="Output raw gRPC response as JSON")
@handle_grpc_errors
@click.pass_context
def git_audit(ctx, id, repo, as_grpc):
    """View Git Release orchestration audit logs and telemetry data."""
    import hau_pb2
    stub = get_hau_stub(ctx.obj['config'])
    
    req = hau_pb2.GitAuditRequest(
        id=id or "",
        project_name=repo or ""
    )
    
    resp = stub.GitAudit(req)
    
    if as_grpc:
        print_grpc_json(resp)
        return
        
    if not resp.success:
        click.secho(f"❌ {resp.message}", fg="red")
        return
        
    try:
        records = json.loads(resp.result_json)
        if not records:
            click.echo("No audit records found.")
            return
            
        if id:
            click.secho(f"--- GitReleaseAuditLog ID: {id} ---", fg='cyan', bold=True)
            for rec in records:
                click.echo(f"Timestamp:   {rec.get('timestamp')}")
                click.echo(f"Project:     {rec.get('project_name')}")
                click.echo(f"Source:      {rec.get('source_branch', 'N/A')}")
                click.echo(f"Target:      {rec.get('target_branch', 'N/A')}")
                click.echo(f"Version:     {rec.get('version_tag')}")
                click.echo(f"Action:      {rec.get('action')}")
                status_color = 'green' if rec.get('status') == 'SUCCESS' else 'red' if rec.get('status') == 'FAILED' else 'yellow'
                click.echo(f"Status:      {click.style(rec.get('status'), fg=status_color, bold=True)}")
                
                if rec.get('error_message'):
                    click.echo(f"Error:       {click.style(rec.get('error_message'), fg='red')}")
                
                click.echo(f"Method:      {rec.get('changelog_generation_method')}")
                
                features = rec.get('merged_features_json') or {}
                if features.get('raw_yaml'):
                    click.secho(f"\n[Generated Changelog]:", fg='magenta', bold=True)
                    click.echo(features.get('raw_yaml').strip())
                    
                jobs_details = rec.get('job_details_json') or {}
                if jobs_details.get('footprint_mb'):
                    click.secho(f"\n📦 Container Footprint: {jobs_details.get('footprint_mb')} MB", bold=True)
                    
                jobs = jobs_details.get('jobs', [])
                if jobs:
                    click.secho(f"\n[Pipeline Jobs]:", fg='magenta', bold=True)
                    for j in jobs:
                        j_status = j.get('status', 'unknown')
                        jc = 'green' if j_status == 'success' else 'red' if j_status == 'failed' else 'yellow'
                        dur = f"{j.get('duration', 0):.1f}s" if j.get('duration') else "N/A"
                        click.echo(f"  - {j.get('name'):<25} | {click.style(f'{j_status:<10}', fg=jc)} | {dur:<8} | {j.get('stage')}")
                        if j.get('trace'):
                            click.secho(f"    --- Last 15 lines of Trace ---", fg='red')
                            for tline in j.get('trace', [])[-15:]:
                                click.secho(f"      {tline}", fg='red', dim=True)
        else:
            click.secho(f"{'ID':<8} | {'Project':<38} | {'Version':<12} | {'Action':<13} | {'Status':<10} | {'Method':<20} | {'Date'}", fg='cyan', bold=True)
            click.secho("-" * 135, fg='cyan')
            for rec in records:
                status_color = 'green' if rec['status'] == 'SUCCESS' else 'red' if rec['status'] == 'FAILED' else 'yellow'
                status_str = click.style(f"{rec['status']:<10}", fg=status_color)
                short_id = str(rec['id'])[:8]
                click.echo(f"{short_id:<8} | {rec['project_name']:<38} | {str(rec['version_tag'] or 'N/A'):<12} | {rec['action']:<13} | {status_str} | {str(rec['changelog_generation_method'] or 'N/A'):<20} | {rec['timestamp']}")
    except Exception as e:
        click.secho(f"Failed to parse audit logs: {e}", fg="red")