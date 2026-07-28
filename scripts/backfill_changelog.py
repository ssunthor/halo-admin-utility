#!/usr/bin/env python3
import sys
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
MODULE_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, '..'))
if MODULE_ROOT not in sys.path:
    sys.path.insert(0, MODULE_ROOT)

try:
    import bootstrap_helper
    bootstrap_helper.bootstrap_and_reexecute_if_needed()
except ImportError:
    pass

import subprocess
import click

from halo_admin_utility import load_config

def get_next_version(current_version):
    parts = current_version.split('.')
    major = int(parts[0])
    minor = int(parts[1])
    patch = int(parts[2])
    
    if patch >= 9:
        minor += 1
        patch = 0
    else:
        patch += 1
        
    return f"{major}.{minor}.{patch}"

@click.command()
@click.option('--repo', required=True, help="Repository name (e.g. ai/halo/pipelines/netflow-dfp)")
@click.option('--branch', default='dev', help="Target branch to backfill (default: dev)")
@click.option('--start-version', default='0.1.0', help="Starting version (default: 0.1.0)")
@click.option('--out', default='backfill_output.yaml', help="Output file path (default: backfill_output.yaml)")
def backfill(repo, branch, start_version, out):
    """Backfills a semantic changelog for a repository grouped by day."""
    config = load_config()
    
    local_base = config['external_services']['gitlab']['local_clone_path']
    project_path = config['external_services']['gitlab']['project_path']
    rel_path = repo
    if rel_path.startswith(project_path + "/"):
        rel_path = rel_path[len(project_path) + 1:]
    
    repo_local_path = os.path.join(local_base, rel_path)
    if not os.path.exists(repo_local_path):
        click.secho(f"Error: Repository cache not found at {repo_local_path}", fg="red")
        return

    click.echo(f"Analyzing git history for {repo} on branch '{branch}'...")
    
    # Get all commits on the branch, oldest to newest
    # Format: YYYY-MM-DD|Hash|Author
    result = subprocess.run(
        ['git', 'log', '--first-parent', branch, '--date=short', '--format=%ad|%H|%an', '--reverse'],
        cwd=repo_local_path, capture_output=True, text=True
    )
    
    if result.returncode != 0:
        click.secho(f"Git log failed: {result.stderr}", fg="red")
        return
        
    lines = result.stdout.strip().split('\n')
    if not lines or lines == ['']:
        click.secho("No commits found.", fg="red")
        return
        
    # Group commits by day
    # Format: { 'YYYY-MM-DD': { 'commits': [...], 'author': 'most frequent/last' } }
    days = {}
    ordered_days = []
    
    for line in lines:
        parts = line.split('|')
        if len(parts) != 3:
            continue
        date_str, commit_hash, author = parts
        
        if date_str not in days:
            days[date_str] = {'commits': [], 'author': author}
            ordered_days.append(date_str)
            
        days[date_str]['commits'].append(commit_hash)
        # Keep updating author, so it effectively becomes the last author of the day
        days[date_str]['author'] = author

    click.echo(f"Found {len(ordered_days)} unique days of activity.")
    
    llm_manager = LLMManager(config=config)
    current_version = start_version
    
    # We will need the previous day's last commit to diff against.
    # For the very first day, the previous commit is the empty tree hash.
    prev_end_commit = '4b825dc642cb6eb9a060e54bf8d69288fbee4904'
    
    changelog_entries = []
    
    for i, date_str in enumerate(ordered_days):
        day_info = days[date_str]
        latest_commit = day_info['commits'][-1]
        author = day_info['author']
        
        click.secho(f"\nProcessing Day {i+1}/{len(ordered_days)}: {date_str} (Version {current_version})", fg="blue")
        
        try:
            from core.orchestrators.changelog_orchestrator import ChangelogOrchestrator
            orchestrator = ChangelogOrchestrator(config=settings)
            
            yaml_output = orchestrator.generate_for_commits(
                repo_local_path=repo_local_path,
                start_commit=prev_end_commit,
                end_commit=latest_commit,
                author=author,
                date_str=date_str,
                version=current_version
            )
            
            if not yaml_output:
                click.secho("No significant features or fixes detected. Skipping version...", fg="yellow")
            else:
                lines = yaml_output.strip().split('\n')
                final_yaml = f"- {lines[0]}\n"
                for line in lines[1:]:
                    final_yaml += f"  {line}\n"
                
                changelog_entries.append(final_yaml)
                click.secho("Changelog generated successfully.", fg="green")
                
                # Increment version for the NEXT loop
                current_version = get_next_version(current_version)
            
        except Exception as e:
            click.secho(f"Failed to generate changelog for {date_str}: {e}", fg="red")
            
        # Prepare for next day
        prev_end_commit = latest_commit

    # Reverse to have newest on top
    changelog_entries.reverse()

    with open(out, 'w') as f:
        # Write some header
        f.write("# ---------------------------------------------------------------------------\n")
        f.write("# BACKFILLED CHANGELOG\n")
        f.write("#\n")
        f.write("# STANDARD CATEGORIES:\n")
        f.write("# - \"🚀 Architecture & Infrastructure\"\n")
        f.write("# - \"✨ New Features & Enhancements\"\n")
        f.write("# - \"🎨 UI / UX Improvements\"\n")
        f.write("# - \"🐛 Bug Fixes & Resilience\"\n")
        f.write("# - \"🔒 Security & Auth\"\n")
        f.write("# - \"🧹 Refactoring & Chores\"\n")
        f.write("# ---------------------------------------------------------------------------\n")
        
        for entry in changelog_entries:
            f.write(entry + "\n")

    click.secho(f"\nBackfill complete! Output written to {out}", fg="green", bold=True)

if __name__ == '__main__':
    backfill()
