import os
import sys
import logging
from sqlalchemy import text

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from halo_admin_utility import load_config
from core.database.database import get_engine

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)-5s - [%(name)s] - %(message)s')
logger = logging.getLogger("alter_git_branch")

def main():
    config = load_config()
    write_dsn = config.get('database', {}).get('write_dsn')
    
    if not write_dsn:
        logger.error("No write_dsn found in config/settings.yaml")
        sys.exit(1)
        
    logger.info("Connecting to the database to alter git_branch...")
    engine = get_engine(write_dsn)
    
    alter_query = text("ALTER TABLE git_branch ADD COLUMN IF NOT EXISTS last_updated_at TIMESTAMP;")
    
    try:
        with engine.connect() as conn:
            conn.execute(alter_query)
            conn.commit()
        logger.info("✅ Successfully added 'last_updated_at' column to 'git_branch' table.")
    except Exception as e:
        logger.error(f"Failed to alter table: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
