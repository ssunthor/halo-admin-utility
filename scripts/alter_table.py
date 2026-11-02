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
    alter_query1 = text("ALTER TABLE halo_tenant RENAME COLUMN slug_name TO tenant_namespace;")
    alter_query2 = text("ALTER TABLE halo_tenant ADD COLUMN IF NOT EXISTS tenant_environment VARCHAR(50);")
    alter_query3 = text("ALTER TABLE halo_tenant ADD COLUMN IF NOT EXISTS netbox_slug VARCHAR(255);")
    alter_query4 = text("""
        UPDATE halo_tenant 
        SET tenant_acronym = 
            CASE 
                WHEN tenant_namespace LIKE 'halo-%' THEN split_part(tenant_namespace, '-', 2)
                WHEN tenant_namespace LIKE 'tenant-%' THEN split_part(tenant_namespace, '-', 2)
                ELSE split_part(tenant_namespace, '-', 1)
            END
        WHERE tenant_acronym IS NULL OR tenant_acronym = '';
    """)
    alter_query5 = text("""
        UPDATE halo_tenant
        SET tenant_environment = 
            CASE 
                WHEN tenant_namespace LIKE 'halo-%-%' THEN array_to_string((string_to_array(tenant_namespace, '-'))[3:], '-')
                WHEN tenant_namespace LIKE 'tenant-%-%' THEN array_to_string((string_to_array(tenant_namespace, '-'))[3:], '-')
                ELSE ''
            END
        WHERE tenant_environment IS NULL;
    """)
    alter_query6 = text("ALTER TABLE halo_tenant DROP CONSTRAINT IF EXISTS halo_tenant_tenant_acronym_key;")
    alter_query7 = text("ALTER TABLE halo_tenant DROP CONSTRAINT IF EXISTS halo_tenant_netbox_slug_key;")
    alter_query8 = text("ALTER TABLE git_project ADD COLUMN IF NOT EXISTS repo_path VARCHAR(255);")
    alter_query9 = text("ALTER TABLE git_project ADD COLUMN IF NOT EXISTS subpath VARCHAR(255);")
    alter_query10 = text("UPDATE git_project SET repo_path = project_path WHERE repo_path IS NULL;")
    
    try:
        with get_db_session(read_only=False) as session:
            try:
                session.execute(alter_query1)
                session.commit()
            except Exception as e:
                session.rollback()
                logger.warning(f"Could not rename slug_name, maybe already done? {e}")
            session.execute(alter_query2)
            session.execute(alter_query3)
            session.execute(alter_query4)
            session.execute(alter_query5)
            session.execute(alter_query6)
            session.execute(alter_query7)
            session.execute(alter_query8)
            session.execute(alter_query9)
            session.execute(alter_query10)
            session.commit()
        logger.info("✅ Successfully executed alter query.")
    except Exception as e:
        logger.error(f"Failed to execute query (perhaps it was already applied?): {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
