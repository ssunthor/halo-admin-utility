import os
import re

HEADER = """# ---------------------------------------------------------------------------
# HALO STANDARD CHANGELOG
#
# STANDARD CATEGORIES:
# - '🚀 Architecture & Infrastructure'
# - '✨ New Features & Enhancements'
# - '🎨 UI / UX Improvements'
# - '🐛 Bug Fixes & Resilience'
# - '🔒 Security & Auth'
# - '🧹 Refactoring & Chores'
# ---------------------------------------------------------------------------
"""

def format_all_changelogs():
    output_dir = '/ai/utilities/halo_admin_utility/output'
    dest_base = '/ai/utilities/halo_admin_utility/cache/halo/deployment/docs'
    
    for item in os.listdir(output_dir):
        path = os.path.join(output_dir, item)
        if os.path.isdir(path):
            changelog_path = os.path.join(path, 'changelog.yaml')
            if os.path.isfile(changelog_path):
                with open(changelog_path, 'r') as f:
                    lines = f.readlines()
                    
                out = [HEADER]
                header_done = False
                for line in lines:
                    if not header_done:
                        if line.startswith('- version:'):
                            out.append('---\n')
                            header_done = True
                        else:
                            continue  # Skip old headers
                            
                    # Replace all internal single quotes with double quotes first!
                    line = line.replace("'", '"')
                    
                    # Now find all "..." and replace the boundaries with '...'
                    line = re.sub(r'(: )"(.*)"$', r"\1'\2'", line) # For key: "value"
                    line = re.sub(r'(- )"(.*)"$', r"\1'\2'", line) # For - "value"
                    
                    out.append(line)
                    
                dest = os.path.join(dest_base, item, 'CHANGELOG.yaml')
                os.makedirs(os.path.dirname(dest), exist_ok=True)
                with open(dest, 'w') as f:
                    f.writelines(out)
                print(f"Processed {item}")

if __name__ == '__main__':
    format_all_changelogs()
