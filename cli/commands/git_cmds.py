import click
import json
from cli.utils import print_grpc_json, handle_grpc_errors, get_hau_stub

@click.group(name='git')
def git_cli():
    """Git workspace and repository operations."""
    pass

@git_cli.command(name='containers')
@click.option("--grpc", "as_grpc", is_flag=True, help="Output raw gRPC response as JSON")
@handle_grpc_errors
@click.pass_context
def git_containers(ctx, as_grpc):
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
            
        # Group tags by project
        grouped_tags = {}
        for tag in tags:
            project = tag.get('project', 'unknown')
            if project not in grouped_tags:
                grouped_tags[project] = []
            grouped_tags[project].append(tag)
            
        for project_name, project_tags in grouped_tags.items():
            click.secho(f"\n📁 {project_name}", fg='magenta', bold=True)
            for t in project_tags:
                tag_name = t['name']
                path = t['path']
                created = t.get('created_at', 'unknown')
                author = t.get('author', 'Unknown')
                
                status_flag = ""
                # Define stable standard tags that usually don't have associated temporary branches
                stable_tags = ['main', 'latest', 'demo', 'dev', 'stable', 'master']
                
                if not t.get('branch_exists') and tag_name not in stable_tags:
                    status_flag = click.style(" [⚠️ Branch Deleted]", fg='yellow', bold=True)
                
                click.echo(f"  [TAG] {click.style(tag_name, fg='cyan', bold=True)}{status_flag} "
                           f"({click.style(path, fg='white', dim=True)}) "
                           f"- Created: {created} | Author: {author}")
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
@click.pass_context
def git_release(ctx, repo, source, target, skip_changelog, delete_branch, debug):
    """Executes a GitOps merge and release (with pipeline monitoring and tagging)."""
    import hau_pb2
    stub = get_hau_stub(ctx.obj['config'])
    
    req = hau_pb2.GitReleaseRequest(
        project_name=repo,
        source_branch=source,
        target_branch=target,
        skip_changelog_generation=skip_changelog,
        keep_branch=not delete_branch,
        debug=debug
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
