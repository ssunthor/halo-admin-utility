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
    config = load_config()
    write_dsn = config.get('database', {}).get('write_dsn')
    engine = get_engine(write_dsn)
    
    with engine.connect() as conn:
        try:
            print("Adding is_internal_overridden column to halo_tenant...")
            conn.execute(text("ALTER TABLE halo_tenant ADD COLUMN is_internal_overridden BOOLEAN DEFAULT FALSE;"))
            conn.commit()
            print("Column added successfully.")
        except Exception as e:
            print(f"Error adding column (maybe it already exists?): {e}")

if __name__ == "__main__":
    main()
