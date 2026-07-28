#!/usr/bin/env python3
import sys
import os
import subprocess
import click

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
MODULE_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, '..'))
if MODULE_ROOT not in sys.path:
    sys.path.insert(0, MODULE_ROOT)

try:
    import bootstrap_helper
    bootstrap_helper.bootstrap_and_reexecute_if_needed()
except ImportError:
    pass

from core.managers.llm_manager import LLMManager
from halo_admin_utility import load_config

def chunk_text(text: str, lines_per_chunk: int = 500) -> list:
    lines = text.split('\n')
    return ['\n'.join(lines[i:i + lines_per_chunk]) for i in range(0, len(lines), lines_per_chunk)]

@click.command()
@click.option('--repo', default='ai/halo/backend', help="Repository name")
@click.option('--date', default='2026-03-04', help="Specific date to process")
@click.option('--branch', default='dev', help="Target branch")
def test_large(repo, date, branch):
    """Test map-reduce logic on a massive day diff."""
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

    click.echo(f"Analyzing {repo} on branch '{branch}' for {date}...")
    
    # Get all commits for that day
    # --since and --until ensure we only get that day
    result = subprocess.run(
        ['git', 'log', '--first-parent', branch, '--oneline', '--reverse',
         f'--since={date}T00:00:00', f'--until={date}T23:59:59'],
        cwd=repo_local_path, capture_output=True, text=True
    )
    
    if result.returncode != 0:
        click.secho(f"Git log failed: {result.stderr}", fg="red")
        return
        
    lines = result.stdout.strip().split('\n')
    if not lines or lines == ['']:
        click.secho("No commits found for that date.", fg="red")
        return
        
    llm_manager = LLMManager(config=config)
    
    click.echo(f"Found {len(lines)} commits on {date}.")
    
    all_extracted_features = []
    
    for line in lines:
        commit_hash = line.split()[0]
        
        # Get parent of this commit
        parent_res = subprocess.run(
            ['git', 'rev-parse', f'{commit_hash}^1'],
            cwd=repo_local_path, capture_output=True, text=True
        )
        parent_hash = parent_res.stdout.strip()
        if parent_res.returncode != 0 or not parent_hash:
            # It's an initial commit
            parent_hash = '4b825dc642cb6eb9a060e54bf8d69288fbee4904'
            
        click.secho(f"\nProcessing commit {commit_hash} (Parent: {parent_hash})", fg="blue")
        
        # Get files changed
        files_res = subprocess.run(
            ['git', 'diff', '--name-only', parent_hash, commit_hash],
            cwd=repo_local_path, capture_output=True, text=True
        )
        files = [f for f in files_res.stdout.strip().split('\n') if f]
        
        for file in files:
            file_diff_res = subprocess.run(
                ['git', 'diff', parent_hash, commit_hash, '--', file],
                cwd=repo_local_path, capture_output=True, text=True
            )
            file_diff = file_diff_res.stdout.strip()
            if not file_diff:
                continue
                
            token_estimate = len(file_diff) // 4
            
            if token_estimate > 8000:
                click.echo(f"  File {file} is large (~{token_estimate} tokens). Chunking...")
                chunks = chunk_text(file_diff, lines_per_chunk=500)
                for idx, chunk in enumerate(chunks):
                    click.echo(f"    -> Map: Extracting chunk {idx+1}/{len(chunks)} (~{len(chunk)//4} tokens)...")
                    features = llm_manager.extract_features(chunk)
                    if features:
                        all_extracted_features.append(features)
            else:
                click.echo(f"  File {file} is small (~{token_estimate} tokens). Processing whole...")
                features = llm_manager.extract_features(file_diff)
                if features:
                    all_extracted_features.append(features)

    if not all_extracted_features:
        click.secho("No features extracted.", fg="red")
        return
        
    click.secho("\n--- REDUCE PHASE ---", fg="green", bold=True)
    click.echo(f"Sending {len(all_extracted_features)} extracted feature sets to merge...")
    
    yaml_output = llm_manager.merge_changelogs(all_extracted_features)
    
    click.secho("\n=== FINAL YAML OUTPUT ===", fg="cyan", bold=True)
    click.echo(yaml_output)

if __name__ == '__main__':
    test_large()
