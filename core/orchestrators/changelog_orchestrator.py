import os
import subprocess
import logging
import re
from typing import Dict, Any, Optional, List

from core.llm_interface import vLLMClient
from prompts.changelog_prompt import CHANGELOG_PROMPT
from prompts.extract_features_prompt import EXTRACT_FEATURES_PROMPT
from prompts.merge_changelog_prompt import MERGE_CHANGELOG_PROMPT

logger = logging.getLogger(__name__)

def chunk_text(text: str, lines_per_chunk: int = 500) -> list[str]:
    lines = text.split('\n')
    chunks = []
    for i in range(0, len(lines), lines_per_chunk):
        chunks.append('\n'.join(lines[i:i+lines_per_chunk]))
    return chunks

class ChangelogOrchestrator:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        llm_config = self.config.get('llm_engines', {}).get('primary')
        if not llm_config:
            raise ValueError("No 'llm_engines.primary' configuration found in settings.yaml")
            
        auth_config = self.config.get('auth')
        self.client = vLLMClient(config=llm_config, auth_cfg=auth_config)

    def _format_author(self, raw_author: str) -> str:
        if raw_author == "Gemini Agent":
            return "Scott Chrestman"
        if raw_author == "gia-ai":
            return "Martin Kecka"
        if raw_author.endswith(" ADM"):
            return raw_author[:-4]
        if raw_author.endswith(" PRV"):
            return raw_author[:-4]
            
        # Handle cases where author is set to email like "first.last@domain.com"
        email_match = re.match(r'^([a-zA-Z]+)\.([a-zA-Z]+)(?:@.*)?$', raw_author)
        if email_match:
            first = email_match.group(1).capitalize()
            last = email_match.group(2).capitalize()
            return f"{first} {last}"
            
        return raw_author
        
    def _generate_changelog(self, raw_commits: str) -> str:
        system_prompt = CHANGELOG_PROMPT.format(raw_commits=raw_commits)
        messages = [{"role": "user", "content": system_prompt}]
        token_estimate = len(raw_commits) // 4
        logger.info(f"Requesting changelog generation from gemma4... (Payload Size: ~{token_estimate} tokens)")
        
        response = self.client.get_chat_completion(messages=messages, temperature=0.2, json_mode=False)
        if not response or "content" not in response:
            raise RuntimeError("LLM failed to generate a response.")
            
        content = response["content"].strip()
        if content.startswith("```yaml"): content = content[7:]
        if content.startswith("```"): content = content[3:]
        if content.endswith("```"): content = content[:-3]
        
        content = content.strip()
        content = content.replace("\\'", "''")
        
        return content

    def _extract_features(self, code_chunk: str) -> str:
        messages = [{"role": "user", "content": EXTRACT_FEATURES_PROMPT + "\n\nCODE:\n" + code_chunk}]
        token_estimate = len(code_chunk) // 4
        logger.info(f"Extracting features from chunk (~{token_estimate} tokens)...")
        
        response = self.client.get_chat_completion(messages=messages, temperature=0.2, json_mode=False)
        if not response or "content" not in response: return ""
        return response["content"].strip()

    def _merge_changelogs(self, items_list: List[str]) -> str:
        combined_items = "\n".join(items_list)
        messages = [{"role": "user", "content": MERGE_CHANGELOG_PROMPT + "\n\nFEATURES:\n" + combined_items}]
        logger.info(f"Merging {len(items_list)} feature lists...")
        
        response = self.client.get_chat_completion(messages=messages, temperature=0.2, json_mode=False)
        if not response or "content" not in response:
            raise RuntimeError("LLM failed to generate a response.")
            
        content = response["content"].strip()
        if content.startswith("```yaml"): content = content[7:]
        if content.startswith("```"): content = content[3:]
        if content.endswith("```"): content = content[:-3]
        
        content = content.strip()
        content = content.replace("\\'", "''")
        
        return content
        
    def generate_for_commits(self, repo_local_path: str, start_commit: str, end_commit: str, author: str, date_str: str, version: str, commits_list: list = None):
        """
        Orchestrates the changelog generation for a specific commit range.
        If the diff is too large, it automatically falls back to a Map-Reduce extraction approach.
        Yields progress strings and finally a dict with {"final_yaml": ...}
        """
        diff_res = subprocess.run(
            ['git', 'diff', start_commit, end_commit, '--', '.', ':(exclude)package-lock.json', ':(exclude)yarn.lock', ':(exclude)pnpm-lock.yaml', ':(exclude)*changelog.yaml', ':(exclude)*CHANGELOG.yaml', ':(exclude)*.md'],
            cwd=repo_local_path, capture_output=True, text=True
        )
        
        if diff_res.returncode != 0:
            logger.error(f"Git diff failed: {diff_res.stderr}")
            raise RuntimeError(f"Git diff failed: {diff_res.stderr.strip()}")
            
        raw_diff = diff_res.stdout.strip()
        if not raw_diff:
            logger.info("No meaningful code changes. Skipping.")
            yield "No meaningful code changes. Skipping."
            yield {"final_yaml": None}
            return
            
        token_estimate = len(raw_diff) // 4
        logger.info(f"Diff payload size: ~{token_estimate} tokens.")
        yield f"Diff payload size: ~{token_estimate} tokens."
        
        try:
            if token_estimate > 20000:
                logger.warning(f"Payload too large (~{token_estimate} tokens). Falling back to Map-Reduce...")
                yield f"Payload too large (~{token_estimate} tokens). Falling back to Map-Reduce..."
                all_extracted_features = []
                
                if commits_list:
                    commit_hashes = commits_list.copy()
                else:
                    commits_res = subprocess.run(
                        ['git', 'log', f"{start_commit}..{end_commit}", '--format=%H'],
                        cwd=repo_local_path, capture_output=True, text=True
                    )
                    commit_hashes = [c for c in commits_res.stdout.strip().split('\n') if c]
                    if not commit_hashes:
                        commit_hashes = [end_commit]
                    commit_hashes.reverse()
                
                for i, commit_hash in enumerate(commit_hashes):
                    logger.info(f"  Processing commit {i+1}/{len(commit_hashes)}: {commit_hash[:7]}...")
                    yield f"  Processing commit {i+1}/{len(commit_hashes)}: {commit_hash[:7]}..."
                    parent_res = subprocess.run(
                        ['git', 'rev-parse', f'{commit_hash}^1'],
                        cwd=repo_local_path, capture_output=True, text=True
                    )
                    parent_hash = parent_res.stdout.strip()
                    if parent_res.returncode != 0 or not parent_hash:
                        parent_hash = '4b825dc642cb6eb9a060e54bf8d69288fbee4904'
                    
                    files_res = subprocess.run(
                        ['git', 'diff', '--name-only', parent_hash, commit_hash],
                        cwd=repo_local_path, capture_output=True, text=True
                    )
                    files = [f for f in files_res.stdout.strip().split('\n') if f]
                    
                    for file in files:
                        if file.endswith('package-lock.json') or file.endswith('yarn.lock') or file.endswith('pnpm-lock.yaml') or 'changelog.yaml' in file.lower() or file.endswith('.md'):
                            logger.info(f"    -> Skipping lockfile/changelog/docs: {file}")
                            yield f"    -> Skipping lockfile/changelog/docs: {file}"
                            continue
                            
                        file_diff_res = subprocess.run(
                            ['git', 'diff', parent_hash, commit_hash, '--', file],
                            cwd=repo_local_path, capture_output=True, text=True
                        )
                        file_diff = file_diff_res.stdout.strip()
                        if not file_diff: continue
                            
                        file_tokens = len(file_diff) // 4
                        if file_tokens > 8000:
                            logger.info(f"    -> Extracting from HUGE file: {file} (~{file_tokens} tokens, chunking...)")
                            yield f"    -> Extracting from HUGE file: {file} (~{file_tokens} tokens, chunking...)"
                            chunks = chunk_text(file_diff, lines_per_chunk=500)
                            for chunk in chunks:
                                features = self._extract_features(chunk)
                                if features: all_extracted_features.append(features)
                        else:
                            logger.info(f"    -> Extracting from: {file} (~{file_tokens} tokens)")
                            yield f"    -> Extracting from: {file} (~{file_tokens} tokens)"
                            features = self._extract_features(file_diff)
                            if features: all_extracted_features.append(features)
                            
                logger.info(f"Merging {len(all_extracted_features)} feature sets into final changelog...")
                yield f"Merging {len(all_extracted_features)} feature sets into final changelog..."
                yaml_output = self._merge_changelogs(all_extracted_features)
            else:
                logger.info("Requesting standard LLM generation...")
                yield "Requesting standard LLM generation..."
                yaml_output = self._generate_changelog(raw_commits=raw_diff)
            
            if "items:" not in yaml_output:
                logger.warning("No significant features or fixes detected. Returning empty result.")
                yield "No significant features or fixes detected. Returning empty result."
                yield {"final_yaml": None}
            else:
                final_yaml = f"version: '{version}'\ndate: '{date_str}'\nauthor: '{author}'\n"
                final_yaml += yaml_output + "\n"
                yield {"final_yaml": final_yaml}
                
        except Exception as e:
            logger.error(f"Failed to generate changelog: {e}")
            raise e

    def run_backfill(self, repo_local_path: str, branch: str, start_version: str = "0.1.0", start_commit: str = None, start_date: str = None, has_existing: bool = True, debug_run: bool = False):
        yield f"Analyzing git history for on branch '{branch}'..."
        
        result = subprocess.run(
            ['git', 'log', '--first-parent', branch, '--date=short', '--format=%ad|%H|%an|%s', '--reverse'],
            cwd=repo_local_path, capture_output=True, text=True
        )
        
        if result.returncode != 0:
            yield f"Git log failed: {result.stderr}"
            return
            
        lines = result.stdout.strip().split('\n')
        if not lines or lines == ['']:
            yield "No commits found."
            return
            
        ordered_commits = []
        found_start_commit = False if start_commit else True
        for line in lines:
            parts = line.split('|', 3)
            if len(parts) != 4: continue
            date_str, commit_hash, raw_author, subject = parts
            
            if not found_start_commit:
                if commit_hash.startswith(start_commit):
                    found_start_commit = True
                continue
            
            if (subject.startswith("chore(docs):") or 
                subject.startswith("chore(release):") or 
                subject.startswith("HAU Auto-Release:") or 
                subject.startswith("Auto-sync from ") or 
                re.match(r'^\[v\d+\.\d+\.\d+.*\]', subject)):
                continue
                
            author = self._format_author(raw_author)
            
            if start_date and date_str <= start_date:
                continue
                
            is_merge = subject.startswith("Merge branch") or subject.startswith("Merge pull request")
            
            if (not ordered_commits or 
                ordered_commits[-1]['is_merge'] or 
                is_merge or 
                ordered_commits[-1]['date_str'] != date_str):
                ordered_commits.append({
                    'date_str': date_str,
                    'start_commit_hash': commit_hash,
                    'end_commit_hash': commit_hash,
                    'author': author,
                    'subject': subject,
                    'commits': [commit_hash],
                    'is_merge': is_merge
                })
            else:
                ordered_commits[-1]['end_commit_hash'] = commit_hash
                ordered_commits[-1]['author'] = author
                ordered_commits[-1]['commits'].append(commit_hash)

        if start_date:
            yield f"Filtering for days > {start_date}. {len(ordered_commits)} commits to process."
        else:
            yield f"Found {len(ordered_commits)} commits of activity."
        
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
        
        current_version = get_next_version(start_version) if has_existing else start_version
        changelog_entries = []
        
        for i, commit_info in enumerate(ordered_commits):
            date_str = commit_info['date_str']
            latest_commit = commit_info['end_commit_hash']
            first_commit = commit_info['start_commit_hash']
            author = commit_info['author']
            
            if i == 0 and start_commit:
                prev_end_commit = start_commit
            else:
                parent_res = subprocess.run(
                    ['git', 'rev-parse', f'{first_commit}^1'],
                    cwd=repo_local_path, capture_output=True, text=True
                )
                if parent_res.returncode == 0 and parent_res.stdout.strip():
                    prev_end_commit = parent_res.stdout.strip()
                else:
                    prev_end_commit = '4b825dc642cb6eb9a060e54bf8d69288fbee4904'
            
            type_str = "Merge feature" if ordered_commits[i]['is_merge'] else "Day"
            yield f"\nProcessing Commit {i+1}/{len(ordered_commits)}: {latest_commit[:7]} on {date_str} (Version {current_version} - {type_str} changelog)"
            
            if debug_run:
                yield f"  [DEBUG-RUN] Would process {type_str.lower()} commits from {prev_end_commit} to {latest_commit} for Version {current_version}."
                current_version = get_next_version(current_version)
                continue

            
            try:
                final_yaml = None
                for update in self.generate_for_commits(
                    repo_local_path=repo_local_path,
                    start_commit=prev_end_commit,
                    end_commit=latest_commit,
                    author=author,
                    date_str=date_str,
                    version=current_version,
                    commits_list=commit_info['commits']
                ):
                    if isinstance(update, dict) and "final_yaml" in update:
                        final_yaml = update["final_yaml"]
                    else:
                        yield str(update)
                
                if not final_yaml:
                    yield "No significant features or fixes detected. Skipping version..."
                else:
                    lines_out = final_yaml.strip().split('\n')
                    formatted_yaml = f"- {lines_out[0]}\n"
                    for line_out in lines_out[1:]:
                        if line_out.strip():
                            formatted_yaml += f"  {line_out}\n"
                        else:
                            formatted_yaml += "\n"
                    
                    changelog_entries.append(formatted_yaml)
                    yield "Changelog generated successfully."
                    
                    # Yield incremental YAML so the client can save progress
                    temp_entries = list(changelog_entries)
                    temp_entries.reverse()
                    incremental_doc = "# ---------------------------------------------------------------------------\n"
                    incremental_doc += "# HALO STANDARD CHANGELOG\n"
                    incremental_doc += "#\n"
                    incremental_doc += "# STANDARD CATEGORIES:\n"
                    incremental_doc += "# - \"🚀 Architecture & Infrastructure\"\n"
                    incremental_doc += "# - \"✨ New Features & Enhancements\"\n"
                    incremental_doc += "# - \"🎨 UI / UX Improvements\"\n"
                    incremental_doc += "# - \"🐛 Bug Fixes & Resilience\"\n"
                    incremental_doc += "# - \"🔒 Security & Auth\"\n"
                    incremental_doc += "# - \"🧹 Refactoring & Chores\"\n"
                    incremental_doc += "# ---------------------------------------------------------------------------\n"
                    incremental_doc += "---\n"
                    incremental_doc += "\n\n".join(temp_entries)
                    
                    yield {"incremental_yaml": incremental_doc}
                    
                    current_version = get_next_version(current_version)
            except Exception as e:
                yield f"Failed to generate changelog for {date_str}: {e}"
                
            prev_end_commit = latest_commit

        if not changelog_entries:
            return

        changelog_entries.reverse()
        final_doc = "# ---------------------------------------------------------------------------\n"
        final_doc += "# HALO STANDARD CHANGELOG\n"
        final_doc += "#\n"
        final_doc += "# STANDARD CATEGORIES:\n"
        final_doc += "# - \"🚀 Architecture & Infrastructure\"\n"
        final_doc += "# - \"✨ New Features & Enhancements\"\n"
        final_doc += "# - \"🎨 UI / UX Improvements\"\n"
        final_doc += "# - \"🐛 Bug Fixes & Resilience\"\n"
        final_doc += "# - \"🔒 Security & Auth\"\n"
        final_doc += "# - \"🧹 Refactoring & Chores\"\n"
        final_doc += "# ---------------------------------------------------------------------------\n"
        final_doc += "---\n"
        final_doc += "\n\n".join(changelog_entries)
        
        latest_feature_branch = None
        if ordered_commits:
            last_commit = ordered_commits[-1]
            subject = last_commit['subject']
            m = re.search(r"Merge branch '([^']+)'", subject)
            if m:
                latest_feature_branch = m.group(1)
            else:
                latest_feature_branch = subject[:30].strip()

        yield {"final_yaml": final_doc, "latest_feature_branch": latest_feature_branch}

    def generate_from_branch(self, repo_local_path: str, branch_name: str, project_name: str) -> str:
        date_res = subprocess.run(
            ['git', 'log', '-1', '--format=%ad', '--date=short', 'HEAD'], 
            cwd=repo_local_path, capture_output=True, text=True
        )
        merge_date = date_res.stdout.strip() if date_res.returncode == 0 else "UNKNOWN"
        
        author_res = subprocess.run(
            ['git', 'log', '-1', '--format=%an', 'HEAD'], 
            cwd=repo_local_path, capture_output=True, text=True
        )
        raw_author = author_res.stdout.strip() if author_res.returncode == 0 else "UNKNOWN"
        merge_author = self._format_author(raw_author)

        generator = self.generate_for_commits(
            repo_local_path=repo_local_path,
            start_commit='HEAD^1',
            end_commit='HEAD',
            author=merge_author,
            date_str=merge_date,
            version="UNKNOWN"
        )
        
        final_yaml = None
        for item in generator:
            if isinstance(item, dict) and "final_yaml" in item:
                final_yaml = item["final_yaml"]
                
        return final_yaml