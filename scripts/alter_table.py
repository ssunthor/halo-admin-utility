#!/usr/bin/env python3
import os
import sys
import logging
from sqlalchemy import text

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from halo_admin_utility import load_config
from core.database.database import initialize_database, get_db_session

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)-5s - [%(name)s] - %(message)s')
logger = logging.getLogger("alter_table")

def main():
    config = load_config()
    write_dsn = config.get('database', {}).get('write_dsn')
    
    if not write_dsn:
        logger.error("No write_dsn found in config/settings.yaml")
        sys.exit(1)
        
    logger.info("Connecting to the database...")
    initialize_database(config)
    
    # --------------------------------------------------------------------------------
    # [UNIVERSAL ALTER SCRIPT]
    # Modify the `alter_query` below to execute any arbitrary schema changes.
    # --------------------------------------------------------------------------------
    alter_query1 = text("ALTER TABLE halo_tenant ADD COLUMN IF NOT EXISTS tenant_acronym VARCHAR(50);")
    alter_query2 = text("ALTER TABLE halo_tenant ADD COLUMN IF NOT EXISTS tenant_name VARCHAR(255);")
    alter_query3 = text("ALTER TABLE halo_tenant ADD COLUMN IF NOT EXISTS tenant_group VARCHAR(255);")
    alter_query4 = text("ALTER TABLE halo_tenant ADD COLUMN IF NOT EXISTS netbox_id INTEGER;")
    alter_query5 = text("ALTER TABLE halo_tenant ADD COLUMN IF NOT EXISTS cmd_group_id VARCHAR(255);")
    
    try:
        with get_db_session(read_only=False) as session:
            session.execute(alter_query1)
            session.execute(alter_query2)
            session.execute(alter_query3)
            session.execute(alter_query4)
            session.execute(alter_query5)
        logger.info("✅ Successfully executed alter query.")
    except Exception as e:
        logger.error(f"Failed to execute query (perhaps it was already applied?): {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
