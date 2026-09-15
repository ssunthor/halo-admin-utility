import logging
import datetime
from sqlalchemy.orm import Session
from core.database.models import (
    TenantResourceInventory, DeploymentAuditLog, GitProject, 
    GitBranch, GitContainer, ProjectType, HaloTenant, GitReleaseAuditLog
)

logger = logging.getLogger(__name__)

class SQLWriter:
    def __init__(self, session: Session):
        self.session = session

    def upsert_feature(self, feature_name: str, env_variable: str, description: str = None, product_category: str = None, ui_grouping: str = None, gitops_dependencies: dict = None, pricing_tiers: dict = None, is_paid_addon: bool = False, enabled_by_default: bool = False):
        from core.database.models import FeatureCatalog
        feature = self.session.query(FeatureCatalog).filter_by(env_variable=env_variable).first()
        
        if not feature:
            feature = FeatureCatalog(env_variable=env_variable)
            self.session.add(feature)
            
        feature.feature_name = feature_name
        feature.description = description
        feature.product_category = product_category
        feature.ui_grouping = ui_grouping
        feature.gitops_dependencies = gitops_dependencies or {}
        feature.pricing_tiers = pricing_tiers or {}
        feature.is_paid_addon = is_paid_addon
        feature.enabled_by_default = enabled_by_default
        
        self.session.flush()
        return feature

    def clear_inventory(self):
        self.session.query(TenantResourceInventory).delete()

    def clean_orphaned_tenants(self):
        self.session.flush()
        from core.database.models import HaloTenant, TenantResourceInventory, LifecycleState
        subq = self.session.query(TenantResourceInventory.tenant_id).subquery()
        orphans = self.session.query(HaloTenant).filter(
            ~HaloTenant.id.in_(subq.select()),
            HaloTenant.lifecycle_state != LifecycleState.ORPHANED,
            HaloTenant.lifecycle_state != LifecycleState.DECOMMISSIONED
        ).all()
        for orphan in orphans:
            logger.info(f"Marking orphaned tenant: {orphan.tenant_namespace} as ORPHANED")
            orphan.lifecycle_state = LifecycleState.ORPHANED
        self.session.flush()

    def delete_orphaned_tenants(self):
        self.session.flush()
        from core.database.models import HaloTenant, LifecycleState
        orphans = self.session.query(HaloTenant).filter(
            HaloTenant.lifecycle_state.in_([LifecycleState.ORPHANED, LifecycleState.DECOMMISSIONED])
        ).all()
        count = len(orphans)
        for orphan in orphans:
            logger.info(f"Physically deleting orphaned/decommissioned tenant: {orphan.tenant_namespace}")
            self.session.delete(orphan)
        self.session.flush()
        return count

    def add_deployment_log(self, tenant_id: str, app_name: str, status: str, action: str, target_version: str = None, message: str = None):
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
                    project_type=ptype,
                    native_releases=p.get("native_releases", [])
                )
                self.session.add(project)
                self.session.flush()
            else:
                project.native_releases = p.get("native_releases", [])
                self.session.flush()
                
            self.session.query(GitBranch).filter_by(project_id=project.id).delete()
            for b in p.get("branches", []):
                b_name = b if isinstance(b, str) else b.get("name")
                b_author = "Unknown" if isinstance(b, str) else b.get("author")
                
                b_last_updated = None
                if not isinstance(b, str) and b.get("last_updated_at"):
                    try:
                        # Attempt to parse timestamp (removing Z if present to simplify)
                        dt_str = b.get("last_updated_at").replace("Z", "+00:00")
                        b_last_updated = datetime.datetime.fromisoformat(dt_str)
                    except:
                        pass

                self.session.add(GitBranch(
                    project_id=project.id,
                    name=b_name,
                    author=b_author,
                    last_updated_at=b_last_updated
                ))
                
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
                        has_native_release=t.get("has_native_release", False),
                        tag_created_at=dt
                    ))
        self.session.commit()

    def upsert_halo_tenant(self, tenant_acronym: str, tenant_environment: str, tenant_namespace: str, target_cluster: str):
        tenant = self.session.query(HaloTenant).filter_by(
            tenant_namespace=tenant_namespace, 
            target_cluster=target_cluster
        ).first()
        
        if not tenant:
            tenant = HaloTenant(
                tenant_acronym=tenant_acronym,
                tenant_environment=tenant_environment,
                tenant_namespace=tenant_namespace,
                target_cluster=target_cluster
            )
            self.session.add(tenant)
            self.session.flush()
            
        from core.database.models import TenantCustomization
        if not tenant.customization:
            tenant.customization = TenantCustomization(
                tenant_id=tenant.id,
                tenant_category="UNKNOWN"
            )
            self.session.flush()
            
        return tenant

    def upsert_tenant_resource(self, tenant_id: str, resource_type: str, resource_name: str, metadata_dict: dict, cluster_name: str = None):
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

    def update_tenant_customization(self, tenant_namespace: str, **kwargs):
        tenant = self.session.query(HaloTenant).filter_by(tenant_namespace=tenant_namespace).first()
        if not tenant:
            return False, f"Tenant '{tenant_namespace}' not found."
            
        from core.database.models import TenantCustomization
        if not tenant.customization:
            tenant.customization = TenantCustomization(tenant_id=tenant.id)
            
        for k, v in kwargs.items():
            if hasattr(tenant.customization, k) and v != "":
                if k in ["configuration_payload", "component_versions"] and isinstance(v, str):
                    import json
                    try:
                        v = json.loads(v)
                    except:
                        pass
                setattr(tenant.customization, k, v)
                
        self.session.flush()
        return True, f"Successfully updated customization for {tenant_namespace}"

    def create_git_release_audit_log(self, project_name: str, action: str, actor: str, status: str, source_branch: str = None, target_branch: str = None, merge_request_id: str = None, version_tag: str = None):
        log = GitReleaseAuditLog(
            project_name=project_name,
            action=action,
            actor=actor,
            status=status,
            source_branch=source_branch,
            target_branch=target_branch,
            merge_request_id=merge_request_id,
            version_tag=version_tag,
            changelog_generation_method="N/A",
            merged_features_json={},
            job_details_json={}
        )
        self.session.add(log)
        self.session.commit()
        return log

    def update_git_release_audit_log(self, log_id: str, **kwargs):
        log = self.session.query(GitReleaseAuditLog).filter_by(id=log_id).first()
        if log:
            for key, value in kwargs.items():
                setattr(log, key, value)
            self.session.commit()
        return log

    def delete_git_audit_log(self, log_id: str):
        log = self.session.query(GitReleaseAuditLog).filter(GitReleaseAuditLog.id.startswith(log_id)).first()
        if log:
            self.session.delete(log)
            self.session.commit()
            return True
        return False