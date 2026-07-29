import sys
import os
sys.path.insert(0, '/ai/utilities/halo_admin_utility')
try:
    import bootstrap_helper
    bootstrap_helper.bootstrap_and_reexecute_if_needed()
except ImportError:
    pass

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

import yaml
import gitlab
import sys

def test_user_search(search_str):
    with open('/ai/utilities/halo_admin_utility/config/settings.yaml', 'r') as f:
        config = yaml.safe_load(f)
        
    gl_config = config.get('external_services', {}).get('gitlab', {})
    url = gl_config.get('url')
    token = gl_config.get('bot_token')
    
    gl = gitlab.Gitlab(url, private_token=token, ssl_verify=False)
    
    try:
        project = gl.projects.get('ai/halo/pipelines/netflow-dfp-test')
        print(f"Fetching members for {project.name}...")
        
        # members_all includes inherited members
        members = project.members_all.list(all=True)
        
        print(f"Found {len(members)} total members.")
        
        search_lower = search_str.lower()
        matched_member = None
        
        for m in members:
            # Check username, name, or email (if available)
            username = getattr(m, 'username', '').lower()
            name = getattr(m, 'name', '').lower()
            
            if search_lower in username or search_lower in name:
                matched_member = m
                break
                
        if matched_member:
            print(f"✅ MATCH FOUND for '{search_str}':")
            print(f"   Name: {matched_member.name}")
            print(f"   Username: {matched_member.username}")
            return matched_member
        else:
            print(f"❌ NO MATCH FOUND for '{search_str}'.")
            
            # fallback to global user search
            print(f"Falling back to global user search for '{search_str}'...")
            users = gl.users.list(search=search_str)
            if users:
                matched_member = users[0]
                print(f"✅ MATCH FOUND (Global) for '{search_str}':")
                print(f"   Name: {matched_member.name}")
                print(f"   Username: {matched_member.username}")
                return matched_member
            else:
                print(f"❌ NO MATCH FOUND GLOBALLY.")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        test_user_search(sys.argv[1])
    else:
        test_user_search("davidra")
        print("-" * 30)
        test_user_search("sergio.dinis@gtt.net")
        print("-" * 30)
        test_user_search("scott")
