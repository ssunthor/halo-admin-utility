import logging
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

class SQLWriter:
    def __init__(self, session: Session):
        self.session = session

    def clear_inventory(self):
        from core.database.models import TenantResourceInventory
        self.session.query(TenantResourceInventory).delete()

    def add_deployment_log(self, tenant_id: str, app_name: str, status: str, action: str, 
                           target_version: str = None, message: str = None):
        from core.database.models import DeploymentAuditLog
        log = DeploymentAuditLog(
            tenant_id=tenant_id,
            app_name=app_name,
            status=status,
            action=action,
            target_version=target_version,
            message=message
        )
        self.session.add(log)
        self.session.flush()

    def upsert_git_inventory(self, data: dict):
        from core.database.models import GitProject, GitBranch, GitContainer, ProjectType
        import datetime
        for p in data.get("projects", []):
            project_path = p.get("fullPath") or p.get("path")
            project_name = p.get("name")
            
            if not project_path:
                continue
                
            project = self.session.query(GitProject).filter_by(project_path=project_path).first()
            if not project:
                ptype = ProjectType.APPLICATION
                if "deployment" in project_path or "manifests" in project_path or "docs-site" in project_path:
                    ptype = ProjectType.INFORMATIONAL
                elif "templates" in project_path:
                    ptype = ProjectType.TEMPLATE
                    
                project = GitProject(
                    project_path=project_path,
                    project_name=project_name,
                    project_type=ptype
                )
                self.session.add(project)
                self.session.flush()
                
            # Update Branches
            self.session.query(GitBranch).filter_by(project_id=project.id).delete()
            for b in p.get("branches", []):
                b_name = b if isinstance(b, str) else b.get("name")
                b_author = "Unknown" if isinstance(b, str) else b.get("author")
                self.session.add(GitBranch(
                    project_id=project.id,
                    name=b_name,
                    author=b_author
                ))
                
            # Update Containers
            self.session.query(GitContainer).filter_by(project_id=project.id).delete()
            for c in p.get("containers", []):
                image_path = c.get("name")
                for t in c.get("tags", []):
                    created_at_str = t.get("created_at")
                    dt = None
                    if created_at_str and created_at_str != "unknown":
                        try:
                            dt = datetime.datetime.fromisoformat(created_at_str.replace("Z", "+00:00"))
                        except:
                            pass
                    self.session.add(GitContainer(
                        project_id=project.id,
                        tag_name=t.get("name"),
                        image_path=image_path,
                        author=t.get("author"),
                        is_git_tag=t.get("is_git_tag", False),
                        branch_exists=t.get("branch_exists", False),
                        tag_created_at=dt
                    ))
        self.session.commit()

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
        if not tenant.is_internal_overridden:
            tenant.is_internal = is_internal
        return tenant

    def upsert_tenant_resource(self, tenant_id: str, resource_type: str, resource_name: str, metadata_dict: dict, cluster_name: str = None):
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
                cluster_name=cluster_name,
                metadata_json=metadata_dict
            )
            self.session.add(resource)
        else:
            resource.metadata_json = metadata_dict
            if cluster_name:
                resource.cluster_name = cluster_name
        return resource
