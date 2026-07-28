import urllib3
urllib3.disable_warnings()
import yaml
import gitlab

with open('/ai/utilities/halo_admin_utility/config/settings.yaml') as f:
    cfg = yaml.safe_load(f)
gl = gitlab.Gitlab(cfg['external_services']['gitlab']['url'], private_token=cfg['external_services']['gitlab']['bot_token'], ssl_verify=False)
p = gl.projects.get('ai/halo/pipelines/netflow-dfp-test')

try:
    pipe = p.pipelines.get(53441)
    print(f"Pipeline 53441 status: {pipe.status}")
    print(f"Ref: {pipe.ref}")
    
    if pipe.status == 'skipped':
        print("Attempting to retry skipped pipeline...")
        try:
            pipe.retry()
            print("Successfully retried via .retry()")
        except Exception as retry_e:
            print(f"Retry failed: {retry_e}")
            print("Attempting to create a new pipeline for the same ref...")
            new_pipe = p.pipelines.create({'ref': pipe.ref})
            print(f"Created new pipeline: {new_pipe.id}")
except Exception as e:
    print(f"Error: {e}")
