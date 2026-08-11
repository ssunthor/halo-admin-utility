import click
import json
from cli.utils import print_grpc_json, handle_grpc_errors, get_hau_stub

@click.group(name='git', context_settings=dict(max_content_width=300, terminal_width=300))
def git_cli():
    """Git workspace and repository operations."""
    pass

@git_cli.command(name='sync-inventory')
@click.option("--project", "-p", default=None, help="Filter sync by specific project name")
@click.option("--grpc", "as_grpc", is_flag=True, help="Output raw gRPC response as JSON")
@handle_grpc_errors
@click.pass_context
def git_sync_inventory(ctx, project, as_grpc):
    """Synchronizes Git inventory, branches, and container tags into the database."""
    import hau_pb2
    stub = get_hau_stub(ctx.obj['config'])
    req = hau_pb2.GitInventorySyncRequest(project_name=project or "")
    
    target_str = f" for '{project}'" if project else ""
    click.echo(f"Starting Git Inventory Sync{target_str}. This may take a moment to fetch and upsert...")
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
                
                # Check for container creation date and branch last updated date
                created = c.get('created_at', c.get('container_created'))
                branch_updated = c.get('branch_last_updated')
                
                date_str = ""
                if created and created != "unknown":
                    date_str += f" | Container Created: {created}"
                if branch_updated and branch_updated != "unknown":
                    date_str += f" | Branch Updated: {branch_updated}"
                if not date_str:
                    date_str = " | Created: unknown"
                
                extra = ""
                if 'branch' in c:
                    extra = f" (Branch: {c['branch']})"
                if 'source_feature' in c and c['source_feature'] != "Unknown":
                    extra = f" (Feature: {c['source_feature']})"
                    
                inactive_str = click.style(" [Inactive]", fg='red', bold=True) if c.get('is_inactive') else ""
                native_rel_str = click.style(" [📜 Release Notes]", fg='magenta', bold=True) if c.get('has_native_release') else ""
                
                click.echo(f"      - {label}{tag_name}{extra}{active_str}{native_rel_str}{inactive_str}{date_str} | Author: {author}")
                
            main_branch = next((c for c in inv.get('core_environments', []) if c.get('branch') in ['main', 'master']), None)
            dev_branch = next((c for c in inv.get('core_environments', []) if c.get('branch') == 'dev'), None)
            
            if main_branch or inv.get('releases'):
                click.secho(f"   🟢 Main Environment:", fg='green', bold=True)
                if main_branch:
                    if 'container_tag' in main_branch or 'tag' in main_branch:
                        print_container(main_branch, "📦 ")
                    else:
                        updated_str = f" | Branch Updated: {main_branch.get('last_updated_at')}" if main_branch.get('last_updated_at') else ""
                        click.echo(f"      - 🌿 {click.style(main_branch['branch'], fg='white', bold=True)}{updated_str} | Author: {main_branch.get('author', 'Unknown')}")
                if inv.get('releases'):
                    for c in inv['releases']: print_container(c, "🚀 ")
                    
            if dev_branch or inv.get('pre_releases'):
                click.secho(f"   🟡 Dev Environment:", fg='yellow', bold=True)
                if dev_branch:
                    if 'container_tag' in dev_branch or 'tag' in dev_branch:
                        print_container(dev_branch, "📦 ")
                    else:
                        updated_str = f" | Branch Updated: {dev_branch.get('last_updated_at')}" if dev_branch.get('last_updated_at') else ""
                        click.echo(f"      - 🌿 {click.style(dev_branch['branch'], fg='white', bold=True)}{updated_str} | Author: {dev_branch.get('author', 'Unknown')}")
                if inv.get('pre_releases'):
                    for c in inv['pre_releases']: print_container(c, "🚧 ")
                
            if inv.get('features'):
                click.secho(f"   ✨ Active Features:", fg='blue')
                for c in inv['features']: print_container(c, "📦 ")
                
            if inv.get('standalone_features'):
                click.secho(f"   👻 Standalone Containers (Branch Deleted):", fg='red')
                for c in inv['standalone_features']: print_container(c, "📦 ")
                
            if inv.get('active_branches_without_containers'):
                click.secho(f"   🌱 Active Branches (No Container):", fg='cyan', dim=True)
                for b in inv['active_branches_without_containers']:
                    updated_str = f" | Branch Updated: {b.get('last_updated_at')}" if b.get('last_updated_at') else ""
                    click.echo(f"      - 🌿 {click.style(b['branch'], fg='white', bold=True)}{updated_str} | Author: {b.get('author', 'Unknown')}")
                    
            if inv.get('inactive_releases'):
                click.secho(f"   🗑️ Inactive Releases (Audit):", fg='red', dim=True)
                for c in inv['inactive_releases']: print_container(c, "🚧 " if '-dev' in c.get('tag', '') else "🚀 ")
            click.echo()
            
    except json.JSONDecodeError:
        click.secho(f"Failed to parse JSON response: {resp.result_json}", fg='red')

@git_cli.command(name='sync')
@click.argument('target', default='halo')
@click.option("--grpc", "as_grpc", is_flag=True, help="Output raw gRPC response as JSON")
@click.option("--branch", "-b", help="Branch to sync and checkout (e.g. dev or main). Falls back to repo default if missing.")
@handle_grpc_errors
@click.pass_context
def git_sync(ctx, target, as_grpc, branch):
    """Clones or pulls the latest changes for HALO or templates locally."""
    import hau_pb2
    stub = get_hau_stub(ctx.obj['config'])
    req = hau_pb2.GitSyncRequest(target=target, branch=branch or "")
    
    if target == 'templates':
        click.echo("Syncing ai/gitlab-ci-templates to local cache... This may take a moment.")
    else:
        branch_str = f"'{branch}'" if branch else "'dev'"
        click.echo(f"Syncing all ai/halo repositories to local cache (defaulting to {branch_str} branch)... This may take a moment.")
        
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
                protected_branches = repo.get('protected_branches', [])
                for b in repo.get('branches', []):
                    is_default = " [default]" if b == default_branch else ""
                    is_protected = " [🔒 protected]" if b in protected_branches else ""
                    click.echo(f"  - {b}{is_default}{is_protected}")
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
@click.option('--project', required=True, help="Project name (e.g. ai/halo/pipelines/netflow-dfp)")
@click.option('--source', default='feat/changelog', help="Source branch to merge from")
@click.option('--target', default='dev', help="Target branch to merge to")
@click.option('--skip-changelog', is_flag=True, help="Skip generating changelog if missing")
@click.option('--delete-branch', is_flag=True, help="Delete the feature branch after merging (default is to keep it)")
@click.option('--debug', is_flag=True, help="Stream detailed job trace logs from the pipeline")
@click.option('--author', type=str, help="Override author (will resolve to GitLab user)")
@click.option('--dry-run', is_flag=True, help="Simulate the release process without modifying GitLab or pushing commits.")
@click.pass_context
def git_release(ctx, project, source, target, skip_changelog, delete_branch, debug, author, dry_run):
    """Executes a GitOps merge and release (with pipeline monitoring and tagging)."""
    import hau_pb2
    stub = get_hau_stub(ctx.obj['config'])
    
    req = hau_pb2.GitReleaseRequest(
        project_name=project,
        source_branch=source,
        target_branch=target,
        skip_changelog_generation=skip_changelog,
        keep_branch=not delete_branch,
        debug=debug,
        author=author or "",
        dry_run=dry_run
    )
    
    mode_str = "[DRY-RUN] " if dry_run else ""
    click.echo(f"{mode_str}Initiating release pipeline for {project} ({source} -> {target})...")
    
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
@click.option('--project', required=True, help="Project name (e.g. ai/halo/pipelines/netflow-dfp)")
@click.option('--pipeline', type=int, help="ID of the pipeline to retry")
@click.option('--merge', type=int, help="ID of the Merge Request to retry")
@click.option('--skip-warnings', is_flag=True, help="Skip retrying if the pipeline is already successful (ignore warnings)")
@click.option('--debug', is_flag=True, help="Stream detailed job trace logs from the pipeline")
@click.option('--author', type=str, help="Override author (will resolve to GitLab user)")
@click.pass_context
def git_retry(ctx, project, pipeline, merge, skip_warnings, debug, author):
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
        project_name=project,
        pipeline_id=pipeline or 0,
        merge_id=merge or 0,
        skip_warnings=skip_warnings,
        debug=debug,
        author=author or ""
    )
    
    if merge:
        click.echo(f"Initiating retry for MR !{merge} on {project}...")
    else:
        click.echo(f"Initiating retry for pipeline #{pipeline} on {project}...")
    
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
@click.option('--project', type=str, help="Filter by project name")
@click.option("--grpc", "as_grpc", is_flag=True, help="Output raw gRPC response as JSON")
@handle_grpc_errors
@click.pass_context
def git_audit(ctx, id, project, as_grpc):
    """View Git Release orchestration audit logs and telemetry data."""
    import hau_pb2
    stub = get_hau_stub(ctx.obj['config'])
    
    req = hau_pb2.GitAuditRequest(
        id=id or "",
        project_name=project or ""
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
                click.echo(f"Actor:       {rec.get('actor', 'N/A')}")
                click.echo(f"Source:      {rec.get('source_branch', 'N/A')}")
                click.echo(f"Target:      {rec.get('target_branch', 'N/A')}")
                click.echo(f"MR ID:       !{rec.get('merge_request_id', 'N/A')}")
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
                            num_lines = min(len(j.get('trace', [])), 50)
                            click.secho(f"    --- Last {num_lines} lines of Trace ---", fg='red')
                            for tline in j.get('trace', [])[-50:]:
                                click.secho(f"      {tline}", fg='red', dim=True)
        else:
            click.secho(f"{'ID':<8} | {'Project':<35} | {'Version':<11} | {'MR':<5} | {'Action':<11} | {'Actor':<15} | {'Path (Src->Tgt)':<25} | {'Status':<10} | {'Method':<18} | {'Date'}", fg='cyan', bold=True)
            click.secho("-" * 175, fg='cyan')
            for rec in records:
                status_color = 'green' if rec['status'] == 'SUCCESS' else 'red' if rec['status'] == 'FAILED' else 'yellow'
                status_str = click.style(f"{rec['status']:<10}", fg=status_color)
                short_id = str(rec['id'])[:8]
                proj_name = rec['project_name'][:35]
                ver = str(rec['version_tag'] or 'N/A')[:11]
                mr_id = str(rec.get('merge_request_id') or 'N/A')[:5]
                act = str(rec['action'])[:11]
                actor = str(rec.get('actor') or 'gia-ai')[:15]
                
                src = rec.get('source_branch') or 'N/A'
                tgt = rec.get('target_branch') or 'N/A'
                path_str = f"{src} -> {tgt}"
                if len(path_str) > 25:
                    path_str = path_str[:22] + "..."
                    
                method = str(rec.get('changelog_generation_method') or 'N/A')[:18]
                
                click.echo(f"{short_id:<8} | {proj_name:<35} | {ver:<11} | {mr_id:<5} | {act:<11} | {actor:<15} | {path_str:<25} | {status_str} | {method:<18} | {rec['timestamp']}")
    except Exception as e:
        click.secho(f"Failed to parse audit logs: {e}", fg="red")

@git_cli.command(name='delete')
@click.option('--project', required=True, help="Project name (e.g. ai/halo/pipelines/netflow-dfp)")
@click.option('--branch', help="Name of the branch to delete")
@click.option('--container', help="Tag of the container to delete")
@click.option('-y', '--yes', is_flag=True, help="Skip confirmation prompt")
@click.option("--grpc", "as_grpc", is_flag=True, help="Output raw gRPC response as JSON")
@handle_grpc_errors
@click.pass_context
def git_delete(ctx, project, branch, container, yes, as_grpc):
    """Deletes a feature branch and/or container tag safely."""
    if not branch and not container:
        click.secho("❌ You must specify at least one of --branch or --container.", fg="red")
        return
        
    if not yes:
        targets = []
        if branch and not container:
            targets.append(f"branch '{branch}' AND its associated container tag")
        else:
            if branch: targets.append(f"branch '{branch}'")
            if container: targets.append(f"container '{container}'")
        target_str = " and ".join(targets)
        click.confirm(f"Are you sure you want to delete {target_str} in '{project}'?", abort=True)
        
    import hau_pb2
    stub = get_hau_stub(ctx.obj['config'])
    
    req = hau_pb2.GitDeleteRequest(
        project_name=project,
        branch_name=branch or "",
        container_tag=container or ""
    )
    
    click.echo("Initiating deletion... (Syncing inventory first, this may take a moment)")
    
    resp = stub.GitDelete(req)
    
    if as_grpc:
        print_grpc_json(resp)
        return
        
    if not resp.success:
        click.secho(f"❌ Deletion Failed:\n{resp.message}", fg="red")
    else:
        if "does not exist" in resp.message:
            click.secho(f"⚠️ Deletion Finished with Warnings:\n{resp.message}", fg="yellow")
        else:
            click.secho(f"✅ Deletion Success:\n{resp.message}", fg="green")