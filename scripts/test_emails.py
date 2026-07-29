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

import gitlab
import yaml
import urllib3


def main():
    with open('/ai/utilities/halo_admin_utility/config/settings.yaml', 'r') as f:
        config = yaml.safe_load(f)
        
    gl_url = config['external_services']['gitlab']['url']
    gl_token = config['external_services']['gitlab']['bot_token']
    
    gl = gitlab.Gitlab(gl_url, private_token=gl_token, ssl_verify=False)
    
    project_path = 'ai/halo/pipelines/netflow-dfp-test'
    print(f"Fetching members for {project_path}...\n")
    
    try:
        project = gl.projects.get(project_path)
        members = project.members_all.list(all=True)
        
        print(f"{'Name':<30} | {'Username':<20} | {'Direct Email':<25} | {'Fallback Email':<25} | {'Public Email':<25}")
        print("-" * 130)
        
        for m in members:
            # We fetch the full user object to see what fields are exposed
            try:
                user = gl.users.get(m.id)
                direct_email = getattr(user, 'email', 'N/A')
                public_email = getattr(user, 'public_email', 'N/A')
            except:
                direct_email = 'N/A'
                public_email = 'N/A'
                
            username = getattr(m, 'username', 'N/A')
            name = getattr(m, 'name', 'N/A')
            fallback = f"{username}@gtt.net"
            
            print(f"{name:<30} | {username:<20} | {str(direct_email):<25} | {fallback:<25} | {str(public_email):<25}")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == '__main__':
    main()
