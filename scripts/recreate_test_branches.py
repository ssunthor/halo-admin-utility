#!/usr/bin/env python3
import os
import subprocess
import shutil

CACHE_DIR = "/ai/utilities/halo_admin_utility/cache/halo/pipelines"
TEST_REPO = f"{CACHE_DIR}/netflow-dfp-test"

def run_cmd(cmd, cwd=None):
    print(f"Running: {' '.join(cmd)}")
    res = subprocess.run(cmd, cwd=cwd, text=True, capture_output=True)
    if res.returncode != 0:
        print(f"Error ({res.returncode}): {res.stderr}")
    return res

def cancel_all_pipelines():
    print("Canceling all running pipelines...")
    try:
        import urllib3
        urllib3.disable_warnings()
        import yaml
        import gitlab
        with open('/ai/utilities/halo_admin_utility/config/settings.yaml') as f:
            cfg = yaml.safe_load(f)
        gl = gitlab.Gitlab(cfg['external_services']['gitlab']['url'], private_token=cfg['external_services']['gitlab']['bot_token'], ssl_verify=False)
        p = gl.projects.get('ai/halo/pipelines/netflow-dfp-test')
        for status in ['running', 'pending']:
            for pl in p.pipelines.list(status=status, all=True):
                try:
                    pl.cancel()
                    print(f"Canceled {pl.id}")
                except Exception as e:
                    print(f"Failed to cancel {pl.id}: {e}")
    except Exception as e:
        print(f"Failed to connect to gitlab for cancellation: {e}")

def main():
    cancel_all_pipelines()
    
    if not os.path.exists(TEST_REPO):
        print(f"Cloning test repo into {TEST_REPO}...")
        os.makedirs(CACHE_DIR, exist_ok=True)
        run_cmd(['git', 'clone', 'https://oauth2:glpat-5hh1RgoaFNjYUWqeoaRto286MQp1OmQ1CA.01.0y0u9a018@gitlab.gt-t.net/ai/halo/pipelines/netflow-dfp-test.git'], cwd=CACHE_DIR)
        run_cmd(['git', 'remote', 'add', 'upstream', 'https://oauth2:glpat-5hh1RgoaFNjYUWqeoaRto286MQp1OmQ1CA.01.0y0u9a018@gitlab.gt-t.net/ai/halo/pipelines/netflow-dfp.git'], cwd=TEST_REPO)

    print("Resetting local state...")
    run_cmd(['git', 'reset', '--hard', 'HEAD'], cwd=TEST_REPO)
    run_cmd(['git', 'clean', '-fd'], cwd=TEST_REPO)

    run_cmd(['git', 'fetch', 'origin'], cwd=TEST_REPO)
    run_cmd(['git', 'fetch', 'upstream'], cwd=TEST_REPO)

    # Delete branches and tags
    print("Resetting branches and tags...")
    run_cmd(['git', 'push', 'origin', '--delete', 'feat/changelog'], cwd=TEST_REPO)
    run_cmd(['git', 'push', 'origin', '--delete', 'feat/health_check'], cwd=TEST_REPO)
    for t in ['test2', 'test3', 'test4', 'test_final']:
        run_cmd(['git', 'push', 'origin', '--delete', t], cwd=TEST_REPO)
    run_cmd(['git', 'push', 'origin', '--delete', 'dev'], cwd=TEST_REPO)
    
    # Try to delete tags that might have been created
    run_cmd(['git', 'push', 'origin', '--delete', 'v0.2.9-dev'], cwd=TEST_REPO)
    run_cmd(['git', 'push', 'origin', '--delete', 'v0.2.9'], cwd=TEST_REPO)
    run_cmd(['git', 'push', 'origin', '--delete', 'v0.3.0'], cwd=TEST_REPO)
    run_cmd(['git', 'push', 'origin', '--delete', 'v0.3.1-dev'], cwd=TEST_REPO)
    run_cmd(['git', 'push', 'origin', '--delete', 'v0.3.1'], cwd=TEST_REPO)

    # Recreate dev from upstream/dev
    run_cmd(['git', 'checkout', '-B', 'dev', 'upstream/dev'], cwd=TEST_REPO)
    run_cmd(['git', 'push', '-u', 'origin', 'dev', '-o', 'ci.skip'], cwd=TEST_REPO)

    # Create feat/changelog
    run_cmd(['git', 'checkout', '-B', 'feat/changelog'], cwd=TEST_REPO)

    # Copy and format CHANGELOG.yaml
    print("Formatting and copying changelog...")
    run_cmd(['python3', '/ai/utilities/halo_admin_utility/scripts/fix_changelog_format.py'])

    # Commit and push feat/changelog
    run_cmd(['git', 'add', 'docs/CHANGELOG.yaml'], cwd=TEST_REPO)
    run_cmd(['git', 'commit', '-m', 'Initialize dev and feat/changelog'], cwd=TEST_REPO)
    run_cmd(['git', 'push', '-u', 'origin', 'feat/changelog', '-o', 'ci.skip'], cwd=TEST_REPO)
    
    # Create feat/health_check
    run_cmd(['git', 'checkout', '-B', 'feat/health_check', 'dev'], cwd=TEST_REPO)
    os.makedirs(f"{TEST_REPO}/scripts", exist_ok=True)
    with open(f"{TEST_REPO}/scripts/health_check.py", 'w') as f:
        f.write("import os\n\ndef check_health():\n    return {'status': 'ok'}\n\nif __name__ == '__main__':\n    print(check_health())\n")
    run_cmd(['git', 'add', 'scripts/health_check.py'], cwd=TEST_REPO)
    run_cmd(['git', 'commit', '-m', 'feat(system): add health check script'], cwd=TEST_REPO)
    run_cmd(['git', 'push', '-u', 'origin', 'feat/health_check', '-o', 'ci.skip'], cwd=TEST_REPO)
    
    print("\n\n=======================================================")
    print("✅ Done! Environment is completely clean and reset.")
    print("You can now test the release pipeline with the following commands:")
    print("-------------------------------------------------------")
    print("1. Release feat/changelog:")
    print("   python3 halo_admin_utility.py git release --repo ai/halo/pipelines/netflow-dfp-test --source feat/changelog --target dev --skip-changelog")
    print("\n2. Release feat/health_check:")
    print("   python3 halo_admin_utility.py git release --repo ai/halo/pipelines/netflow-dfp-test --source feat/health_check --target dev")
    print("=======================================================\n")

if __name__ == "__main__":
    main()
