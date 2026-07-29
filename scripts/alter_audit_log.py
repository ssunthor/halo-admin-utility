import os
import sys
from sqlalchemy import text

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, '..'))
if PARENT_DIR not in sys.path:
    sys.path.insert(0, PARENT_DIR)

from halo_admin_utility import load_config
from core.database.database import get_engine

def main():
    print("Loading HAU configuration...")
    config = load_config()
    
    db_config = config.get('database', {})
    write_dsn = db_config.get('write_dsn')
    
    if not write_dsn:
        print("❌ Error: write_dsn not found in configuration.")
        sys.exit(1)
        
    print("Connecting to the database...")
    engine = get_engine(write_dsn)
    
    queries = [
        "ALTER TABLE git_release_audit_log ADD COLUMN IF NOT EXISTS source_branch VARCHAR(255);",
        "ALTER TABLE git_release_audit_log ADD COLUMN IF NOT EXISTS target_branch VARCHAR(255);",
        "ALTER TABLE git_release_audit_log ADD COLUMN IF NOT EXISTS error_message VARCHAR;"
    ]
    
    try:
        with engine.begin() as conn:
            for q in queries:
                print(f"Executing: {q}")
                conn.execute(text(q))
        print("✅ Database migration completed successfully.")
    except Exception as e:
        print(f"❌ Failed to alter table: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()