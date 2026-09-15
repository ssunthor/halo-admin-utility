import os
import click
import json
from cli.utils import get_hau_stub

@click.group(name='changelog', context_settings=dict(max_content_width=300, terminal_width=300))
def changelog_cmds():
    """Commands for AI-driven changelog functionality in HALO."""
    pass

@changelog_cmds.command(name='generate')
@click.option('--project', required=True, help="Project name (e.g. ai/halo/pipelines/netflow-dfp)")
@click.option('--branch', default='main', help="Target branch to extract changes for (default: main)")
@click.pass_context
def generate_changelog(ctx, project, branch):
    """Generates a semantic CHANGELOG.yaml via the HAU gRPC backend."""
    config = ctx.obj['config']
    
    click.echo(f"Requesting changelog generation for {project} on branch '{branch}' from HAU server...")
    
    try:
        stub = get_hau_stub(config)
        import hau_pb2
        
        request = hau_pb2.GenerateChangelogRequest(
            project_name=project,
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
@click.option('--project', required=True, help="Project name")
@click.option('--branch', default='main', help="Target branch")
@click.option('--start-version', default='0.1.0', help="Starting version")
@click.option('--start-commit', default='', help="Optional starting commit hash (exclusive)")
@click.option('--out', default='backfill_output.yaml', help="Output file path")
@click.pass_context
def backfill_changelog(ctx, project, branch, start_version, start_commit, out):
    """Backfills a semantic changelog via the HAU gRPC streaming backend."""
    config = ctx.obj['config']
    
    try:
        stub = get_hau_stub(config)
        import hau_pb2
        
        request = hau_pb2.GitBackfillRequest(
            project_name=project,
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
                if response.message == "Incremental changelog update.":
                    click.secho(f"  -> Incremental changelog saved to {out}", fg="cyan")
                else:
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

@changelog_cmds.command(name='sync')
@click.option('--project', required=True, help="Project name")
@click.option('--branch', default='dev', help="Target branch")
@click.option('--changelog', required=True, help="Path to the local CHANGELOG.yaml to sync")
@click.pass_context
def sync_changelog(ctx, project, branch, changelog):
    """Syncs the changelog by only backfilling missing versions and redoing the latest version."""
    config = ctx.obj['config']
    
    try:
        import yaml
        stub = get_hau_stub(config)
        import hau_pb2
        
        click.echo(f"Reading local changelog from {changelog}...")
        
        try:
            with open(changelog, 'r') as f:
                raw_yaml_changelog = f.read()
        except FileNotFoundError:
            click.secho(f"Error: Changelog file {changelog} not found. Please provide a valid path.", fg="red")
            return
        
        start_version = "0.1.0"
        start_date = ""
        old_yaml_entries = ""
        
        if raw_yaml_changelog:
            try:
                changelog_data = yaml.safe_load(raw_yaml_changelog)
                if isinstance(changelog_data, list) and len(changelog_data) >= 1:
                    latest_item = changelog_data[0]
                    start_version = latest_item.get('version', '0.1.0')
                    start_date = latest_item.get('date', '')
                    
                    if len(changelog_data) >= 2:
                        keep_from_version = changelog_data[1].get('version', '')
                        
                        lines = raw_yaml_changelog.split('\n')
                        keep_lines = []
                        found_target = False
                        for line in lines:
                            if not found_target:
                                if line.strip() == f"- version: '{keep_from_version}'" or line.strip() == f"- version: {keep_from_version}":
                                    found_target = True
                                    keep_lines.append(line)
                            else:
                                keep_lines.append(line)
                                
                        if found_target:
                            old_yaml_entries = '\n'.join(keep_lines)
                        else:
                            click.secho("Warning: Could not parse old YAML accurately, doing a full backfill.", fg="yellow")
                            start_date = ""
                    else:
                        # Only 1 version, nothing to keep
                        old_yaml_entries = ""
                else:
                    click.secho("No valid versions found, falling back to full backfill.", fg="yellow")
            except Exception as e:
                click.secho(f"Failed to parse existing YAML: {e}. Doing full backfill.", fg="yellow")
        else:
            click.secho("Existing changelog is empty. Doing full backfill.", fg="yellow")
            
        click.echo(f"Starting sync from version {start_version} and date {start_date}...")
        
        request = hau_pb2.GitBackfillRequest(
            project_name=project,
            branch_name=branch,
            start_version=start_version,
            start_commit="",
            start_date=start_date
        )
        
        responses = stub.GitBackfillChangelog(request)
        for response in responses:
            if not response.success:
                click.secho(f"Error: {response.message}", fg="red")
                return
                
            if response.changelog_yaml:
                final_yaml = response.changelog_yaml
                if old_yaml_entries:
                    if not final_yaml.endswith('\n'):
                        final_yaml += '\n'
                    final_yaml += '\n' + old_yaml_entries + '\n'
                    
                with open(changelog, 'w') as f:
                    f.write(final_yaml)
                if response.message == "Incremental changelog update.":
                    click.secho(f"  -> Incremental changelog saved to {changelog}", fg="cyan")
                else:
                    click.secho(f"\nFinal synced changelog written to {changelog}", fg="green")

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
