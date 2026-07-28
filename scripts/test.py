import sys
sys.path.insert(0, '/ai/utilities/halo_admin_utility')
import yaml
from core.managers.gitlab_manager import GitlabManager
import gitlab

with open('/ai/utilities/halo_admin_utility/config/settings.yaml') as f:
    config = yaml.safe_load(f)

gl_config = config['external_services']['gitlab']
gl = gitlab.Gitlab(gl_config['url'], private_token=gl_config['bot_token'], ssl_verify=False)

p = gl.projects.get('ai/halo/pipelines/netflow-dfp')
r = p.repositories.list()[0]
tags = r.tags.list(get_all=True)
if tags:
    tag_name = tags[0].name
    print("Tag:", tag_name)
    try:
        branch = p.branches.get(tag_name)
        author = branch.commit['author_name']
        print("Author from branch:", author)
    except Exception as e:
        print("Branch error:", e)
        
    try:
        tag_obj = p.tags.get(tag_name)
        author = tag_obj.commit['author_name']
        print("Author from git tag:", author)
    except Exception as e:
        print("Git tag error:", e)
else:
    print("No tags")
