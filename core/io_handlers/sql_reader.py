import logging
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

class SQLReader:
    def __init__(self, session: Session):
        self.session = session

    def get_all_inventory(self, tenant_slug: str = None):
        from core.database.models import HaloTenant
        query = self.session.query(HaloTenant)
        if tenant_slug:
            query = query.filter_by(slug_name=tenant_slug)
        tenants = query.all()
        result = {}
        for t in tenants:
            if t.target_cluster not in result:
                result[t.target_cluster] = {}
            
            tenant_dict = {
                "slug_name": t.slug_name,
                "environment": t.environment,
                "is_internal": t.is_internal,
                "url": t.url,
                "resources": {}
            }
            
            for r in t.resources:
                r_type = r.resource_type
                if r_type not in tenant_dict["resources"]:
                    tenant_dict["resources"][r_type] = []
                    
                item = r.metadata_json or {}
                item["name"] = r.resource_name
                tenant_dict["resources"][r_type].append(item)
                
            result[t.target_cluster][t.slug_name] = tenant_dict
            
        return result
