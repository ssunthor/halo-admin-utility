#!/usr/bin/env python3
# bootstrap_helper.py

import os
import sys
import subprocess

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
VENV_PATH = os.path.join(SCRIPT_DIR, "venv")
REQUIREMENTS_FILE = os.path.join(SCRIPT_DIR, "requirements.txt")
MARKER_FILE = os.path.join(VENV_PATH, ".installed")
UI_DIR = os.path.join(SCRIPT_DIR, "ui")
PACKAGE_JSON_FILE = os.path.join(UI_DIR, "package.json")

def needs_pip_install():
    if not os.path.exists(VENV_PATH) or not os.path.exists(MARKER_FILE):
        return True
    req_mtime = os.path.getmtime(REQUIREMENTS_FILE)
    marker_mtime = os.path.getmtime(MARKER_FILE)
    return req_mtime > marker_mtime

def needs_npm_install():
    if not os.path.exists(PACKAGE_JSON_FILE):
        return False
    node_modules_path = os.path.join(UI_DIR, "node_modules")
    return not os.path.exists(node_modules_path)

def bootstrap_and_reexecute_if_needed(debug_flag=False):
    in_venv = sys.prefix == VENV_PATH

    # 1. Manage Python Virtual Environment
    if needs_pip_install():
        print("[BOOTSTRAP] Python virtual environment missing or outdated. Installing backend dependencies...")
        if not os.path.exists(VENV_PATH):
            subprocess.check_call([sys.executable, "-m", "venv", VENV_PATH])
        
        pip_exe = os.path.join(VENV_PATH, "bin", "pip")
        subprocess.check_call([pip_exe, "install", "-q", "--upgrade", "pip"])
        
        if os.path.exists(REQUIREMENTS_FILE):
            with open(REQUIREMENTS_FILE, 'r') as f:
                for line in f:
                    pkg = line.strip()
                    if pkg and not pkg.startswith('#'):
                        print(f"  -> Installing {pkg}...")
                        subprocess.check_call([pip_exe, "install", "-q", pkg])
                        
        # Final safety pass for dependency resolution
        subprocess.check_call([pip_exe, "install", "-q", "-r", REQUIREMENTS_FILE])
        
        with open(MARKER_FILE, 'w') as f:
            f.write("installed")
        print("[BOOTSTRAP] Backend dependencies installed successfully.")

    # 2. Manage Node/NPM dependencies for UI (if present)
    if needs_npm_install():
        print("[BOOTSTRAP] 'ui/node_modules' not found. Installing frontend dependencies...")
        subprocess.check_call(["npm", "install", "--no-audit", "--no-fund"], cwd=UI_DIR)
        print("[BOOTSTRAP] Frontend dependencies installed successfully.")

    # 3. Re-execute script within the venv
    if not in_venv:
        venv_python = os.path.join(VENV_PATH, "bin", "python")
        os.execv(venv_python, [venv_python, "-u"] + sys.argv)

if __name__ == "__main__":
    bootstrap_and_reexecute_if_needed()
