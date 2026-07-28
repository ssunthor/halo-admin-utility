import logging
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

class SQLWriter:
    def __init__(self, session: Session):
        self.session = session

    def clear_inventory(self):
        from core.database.models import HaloTenant, TenantResourceInventory
        self.session.query(TenantResourceInventory).delete()
        self.session.query(HaloTenant).delete()

    def upsert_halo_tenant(self, slug_name: str, target_cluster: str, environment: str, is_internal: bool):
        from core.database.models import HaloTenant
        tenant = self.session.query(HaloTenant).filter_by(
            slug_name=slug_name, 
            target_cluster=target_cluster
        ).first()
        
        if not tenant:
            tenant = HaloTenant(
                slug_name=slug_name,
                target_cluster=target_cluster,
                environment=environment,
                is_internal=is_internal
            )
            self.session.add(tenant)
            self.session.flush() # To get the ID
            return tenant
            
        # Update existing
        tenant.environment = environment
        tenant.is_internal = is_internal
        return tenant

    def upsert_tenant_resource(self, tenant_id: str, resource_type: str, resource_name: str, metadata_dict: dict):
        from core.database.models import TenantResourceInventory
        resource = self.session.query(TenantResourceInventory).filter_by(
            tenant_id=tenant_id,
            resource_type=resource_type,
            resource_name=resource_name
        ).first()
        
        if not resource:
            resource = TenantResourceInventory(
                tenant_id=tenant_id,
                resource_type=resource_type,
                resource_name=resource_name,
                metadata_json=metadata_dict
            )
            self.session.add(resource)
        else:
            resource.metadata_json = metadata_dict
        return resource
