import re

def fix_yaml():
    path = '/ai/utilities/halo_admin_utility/output/netflow-dfp/changelog.yaml'
    with open(path, 'r') as f:
        content = f.read()
    
    # 1. Replace all single quotes with double quotes
    content = content.replace("'", '"')
    
    # 2. Replace all double quotes with single quotes
    content = content.replace('"', "'")
    
    # Wait, if I do both, everything becomes single quotes. But the inner ones will break YAML!
    # Instead, let's just do a regex replace for double quotes that start/end a string.
    pass

# Better approach:
def fix_yaml2():
    path = '/ai/utilities/halo_admin_utility/output/netflow-dfp/changelog.yaml'
    with open(path, 'r') as f:
        lines = f.readlines()
        
    out = []
    header_done = False
    for line in lines:
        if line.startswith('- version:'):
            if not header_done:
                out.append('---\n')
                header_done = True
                
        # We know the LLM generated format exactly.
        # It's either:
        # - version: "..."
        # date: "..."
        # author: "..."
        # - category: "..."
        # - "..."
        
        # If the line contains a double quoted string, we can use regex to find it.
        # But wait, there could be internal single quotes that we need to escape!
        
        # Let's replace all internal single quotes with double quotes first!
        line = line.replace("'", '"')
        
        # Now find all "..." and replace the boundaries with '...'
        # Actually, since the LLM puts " at the very start and end of the string...
        line = re.sub(r'(: )"(.*)"$', r"\1'\2'", line) # For key: "value"
        line = re.sub(r'(- )"(.*)"$', r"\1'\2'", line) # For - "value"
        
        out.append(line)
        
    dest = '/ai/utilities/halo_admin_utility/cache/halo/pipelines/netflow-dfp-test/docs/CHANGELOG.yaml'
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    with open(dest, 'w') as f:
        f.writelines(out)
        
if __name__ == '__main__':
    import os
    fix_yaml2()
