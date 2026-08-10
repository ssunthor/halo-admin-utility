import os
import sys
from sqlalchemy import text

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, '..'))
if PARENT_DIR not in sys.path:
    sys.path.insert(0, PARENT_DIR)

from halo_admin_utility import load_config
from core.database.database import get_engine
from core.database.models import Base

def main():
    config = load_config()
    write_dsn = config.get('database', {}).get('write_dsn')
    engine = get_engine(write_dsn)
    
    # 1. Create the new tables (tenant_customization)
    Base.metadata.create_all(bind=engine)
    
    with engine.connect() as conn:
        try:
            print("Fetching legacy is_internal flags...")
            result = conn.execute(text("SELECT id, is_internal FROM halo_tenant;"))
            tenants = result.fetchall()
            
            print(f"Migrating {len(tenants)} tenants to tenant_customization...")
            for tenant in tenants:
                tenant_id = tenant[0]
                is_internal = tenant[1]
                category = "INTERNAL" if is_internal else "CUSTOMER"
                
                # Check if it already exists
                exists = conn.execute(
                    text("SELECT 1 FROM tenant_customization WHERE tenant_id = :tenant_id"), 
                    {"tenant_id": tenant_id}
                ).fetchone()
                
                if not exists:
                    conn.execute(
                        text("""
                            INSERT INTO tenant_customization 
                            (tenant_id, tenant_category, tenant_tier, update_policy, owner, configuration_payload) 
                            VALUES (:tenant_id, :tenant_category, 'UNKNOWN', 'MANUAL_ONLY', 'UNASSIGNED', '{}')
                        """),
                        {"tenant_id": tenant_id, "tenant_category": category}
                    )
            conn.commit()
            
            print("Dropping legacy columns and tables...")
            try:
                conn.execute(text("ALTER TABLE halo_tenant DROP COLUMN IF EXISTS is_internal;"))
            except Exception as e:
                print(f"Failed to drop is_internal (may already be dropped): {e}")
            
            try:
                conn.execute(text("ALTER TABLE halo_tenant DROP COLUMN IF EXISTS is_internal_overridden;"))
            except Exception as e:
                print(f"Failed to drop is_internal_overridden: {e}")

            try:
                conn.execute(text("ALTER TABLE halo_tenant DROP COLUMN IF EXISTS environment;"))
            except Exception as e:
                print(f"Failed to drop environment: {e}")
            
            try:
                conn.execute(text("DROP TABLE IF EXISTS tenant_feature_flag CASCADE;"))
            except Exception as e:
                print(f"Failed to drop tenant_feature_flag: {e}")
                
            conn.commit()
            print("Migration complete.")
        except Exception as e:
            print(f"Migration error: {e}")

if __name__ == "__main__":
    main()
