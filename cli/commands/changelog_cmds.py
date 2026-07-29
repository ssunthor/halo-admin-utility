import os
import click
import json
from cli.utils import get_hau_stub

@click.group(name='changelog')
def changelog_cmds():
    """Commands for AI-driven changelog functionality in HALO."""
    pass

@changelog_cmds.command(name='generate')
@click.option('--repo', required=True, help="Repository name (e.g. ai/halo/pipelines/netflow-dfp)")
@click.option('--branch', default='main', help="Target branch to extract changes for (default: main)")
@click.pass_context
def generate_changelog(ctx, repo, branch):
    """Generates a semantic CHANGELOG.yaml via the HAU gRPC backend."""
    config = ctx.obj['config']
    
    click.echo(f"Requesting changelog generation for {repo} on branch '{branch}' from HAU server...")
    
    try:
        stub = get_hau_stub(config)
        import hau_pb2
        
        request = hau_pb2.GenerateChangelogRequest(
            project_name=repo,
            branch_name=branch
        )
        
        response = stub.GenerateChangelog(request)
        
        if not response.success:
            click.secho(f"Failed: {response.message}", fg="red")
            return
            
        click.secho(f"Success: {response.message}", fg="green")
        click.secho("\n=== GENERATED CHANGELOG.YAML ===\n", fg="green")
        click.echo(response.changelog_yaml)
        click.secho("\n================================\n", fg="green")
        
    except Exception as e:
        click.secho(f"gRPC Error: {str(e)}", fg="red")

@changelog_cmds.command(name='backfill')
@click.option('--repo', required=True, help="Repository name")
@click.option('--branch', default='main', help="Target branch")
@click.option('--start-version', default='0.1.0', help="Starting version")
@click.option('--start-commit', default='', help="Optional starting commit hash (exclusive)")
@click.option('--out', default='backfill_output.yaml', help="Output file path")
@click.pass_context
def backfill_changelog(ctx, repo, branch, start_version, start_commit, out):
    """Backfills a semantic changelog via the HAU gRPC streaming backend."""
    config = ctx.obj['config']
    
    try:
        stub = get_hau_stub(config)
        import hau_pb2
        
        request = hau_pb2.GitBackfillRequest(
            project_name=repo,
            branch_name=branch,
            start_version=start_version,
            start_commit=start_commit
        )
        
        # This will block and stream responses from the server
        responses = stub.GitBackfillChangelog(request)
        for response in responses:
            if not response.success:
                click.secho(f"Error: {response.message}", fg="red")
                return
                
            if response.changelog_yaml:
                out_dir = os.path.dirname(os.path.abspath(out))
                if out_dir:
                    os.makedirs(out_dir, exist_ok=True)
                with open(out, 'w') as f:
                    f.write(response.changelog_yaml)
                click.secho(f"\nFinal changelog written to {out}", fg="green")
            else:
                msg = response.message
                if msg.startswith("\nProcessing Day") or msg.startswith("Processing Day"):
                    click.secho(msg, fg="cyan")
                elif msg.startswith("Payload too large") or msg.startswith("No significant features"):
                    click.secho(msg, fg="yellow")
                elif msg.startswith("Changelog generated successfully") or msg.startswith("Backfill complete"):
                    click.secho(msg, fg="green")
                elif msg.startswith("Error") or "failed" in msg.lower():
                    click.secho(msg, fg="red")
                else:
                    click.echo(msg)
                
    except Exception as e:
        click.secho(f"gRPC Error: {str(e)}", fg="red")
