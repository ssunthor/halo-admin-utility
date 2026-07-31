import logging
from sqlalchemy.orm import Session
from core.database.models import HaloTenant, TenantResourceInventory, GitProject, GitReleaseAuditLog

logger = logging.getLogger(__name__)

class SQLReader:
    def __init__(self, session: Session):
        self.session = session

    def get_all_inventory(self, tenant_slug: str = None):
        query = self.session.query(HaloTenant)
        if tenant_slug:
            query = query.filter_by(slug_name=tenant_slug)
        tenants = query.all()
        result = {}
        for t in tenants:
            if t.slug_name not in result:
                result[t.slug_name] = {}
            
            tenant_dict = {
                "slug_name": t.slug_name,
                "environment": t.environment,
                "is_internal": t.is_internal,
                "url": t.url
            }
            
            for r in t.resources:
                r_type = r.resource_type
                    
                item = r.metadata_json or {}
                item["name"] = r.resource_name
                r_cluster = r.cluster_name or t.target_cluster
                item["cluster"] = r_cluster
                
                if r_cluster not in result[t.slug_name]:
                    result[t.slug_name][r_cluster] = dict(tenant_dict)
                    result[t.slug_name][r_cluster]["resources"] = {}
                
                if r_type not in result[t.slug_name][r_cluster]["resources"]:
                    result[t.slug_name][r_cluster]["resources"][r_type] = []
                    
                result[t.slug_name][r_cluster]["resources"][r_type].append(item)
                
            if not t.resources:
                result[t.slug_name][t.target_cluster] = dict(tenant_dict)
                result[t.slug_name][t.target_cluster]["resources"] = {}
                
        return result

    def get_active_deployments_counts(self):
        import json
        
        counts = {}
        resources = self.session.query(TenantResourceInventory).all()
        for r in resources:
            if not r.metadata_json: continue
            
            images = []
            if 'image' in r.metadata_json:
                images.append(r.metadata_json['image'])
            for cont in r.metadata_json.get('containers', []):
                if 'image' in cont:
                    images.append(cont['image'])
                    
            for img in images:
                if img not in counts:
                    counts[img] = {'count': 0, 'namespaces': set()}
                counts[img]['count'] += 1
                if r.tenant:
                    counts[img]['namespaces'].add(r.tenant.slug_name)
                    
        for img in counts:
            counts[img]['namespaces'] = list(counts[img]['namespaces'])
            
        return counts

    def get_git_inventory(self, project_filter: str = None):
        query = self.session.query(GitProject).filter_by(is_ignored=False)
        
        if project_filter:
            query = query.filter(
                (GitProject.project_name == project_filter) | 
                (GitProject.project_path == project_filter) |
                (GitProject.project_path.like(f"%/{project_filter}"))
            )
            
        active_deployments = self.get_active_deployments_counts()
        audit_logs = self.get_successful_git_releases()
        audit_mapping = {}
        for log in audit_logs:
            if log.version_tag and log.project_name:
                if log.project_name not in audit_mapping:
                    audit_mapping[log.project_name] = {}
                audit_mapping[log.project_name][log.version_tag] = log.source_branch

        projects = query.all()
        result = []
        for p in projects:
            # FIX: Use project_path to map correctly from audit log full paths!
            p_audit = audit_mapping.get(p.project_path, {})
            branches = {b.name: b.author for b in p.branches}
            
            releases = []
            pre_releases = []
            features = []
            standalone_features = []
            
            matched_containers = set()
            for c in p.containers:
                tag = c.tag_name
                short_container_name = c.image_path.split('/')[-1] if c.image_path else p.project_name
                short_image = f"{short_container_name}:{tag}"
                deploy_info = active_deployments.get(short_image, {})
                deploy_count = deploy_info.get('count', 0)
                deploy_namespaces = deploy_info.get('namespaces', [])
                
                c_info = {
                    "tag": tag,
                    "author": c.author,
                    "created_at": c.tag_created_at.isoformat() if c.tag_created_at else "unknown",
                    "active_deployments": deploy_count,
                    "active_namespaces": deploy_namespaces,
                    "has_native_release": c.has_native_release
                }
                
                if tag.startswith('v') and '-dev' not in tag:
                    c_info["branch"] = "main" if "main" in branches else "master"
                    c_info["is_git_tag"] = c.is_git_tag
                    c_info["branch_exists"] = c.branch_exists
                    releases.append(c_info)
                    matched_containers.add(tag)
                elif tag.startswith('v') and '-dev' in tag:
                    c_info["source_feature"] = p_audit.get(tag, "Unknown")
                    pre_releases.append(c_info)
                    matched_containers.add(tag)
                else:
                    for b_name, b_author in branches.items():
                        sanitized_b = b_name.replace('/', '-')
                        if tag == sanitized_b:
                            features.append({
                                "branch": b_name,
                                "branch_author": b_author,
                                "container_tag": tag,
                                "container_created": c_info["created_at"],
                                "active_deployments": deploy_count,
                                "active_namespaces": deploy_namespaces,
                                "has_native_release": c.has_native_release
                            })
                            matched_containers.add(tag)
                            break
                            
            for c in p.containers:
                if c.tag_name not in matched_containers:
                    short_container_name = c.image_path.split('/')[-1] if c.image_path else p.project_name
                    short_image = f"{short_container_name}:{c.tag_name}"
                    deploy_info = active_deployments.get(short_image, {})
                    standalone_features.append({
                        "tag": c.tag_name,
                        "author": c.author,
                        "created_at": c.tag_created_at.isoformat() if c.tag_created_at else "unknown",
                        "active_deployments": deploy_info.get('count', 0),
                        "active_namespaces": deploy_info.get('namespaces', []),
                        "has_native_release": c.has_native_release
                    })
                    
            matched_branches = [f["branch"] for f in features]
            active_branches_without_containers = [
                {"branch": b_name, "author": b_author} 
                for b_name, b_author in branches.items() 
                if b_name not in matched_branches
            ]
            
            proj_data = {
                "name": p.project_name,
                "path": p.project_path,
                "type": p.project_type.name,
                "is_deprecated": p.is_deprecated,
                "inventory": {
                    "releases": sorted(releases, key=lambda x: x['tag'], reverse=True),
                    "pre_releases": sorted(pre_releases, key=lambda x: x['tag'], reverse=True),
                    "features": sorted(features, key=lambda x: x['branch']),
                    "standalone_features": sorted(standalone_features, key=lambda x: x['tag']),
                    "active_branches_without_containers": sorted(active_branches_without_containers, key=lambda x: x['branch'])
                }
            }
            result.append(proj_data)
        return result

    def get_git_containers(self):
        projects = self.session.query(GitProject).filter_by(is_ignored=False).all()
        all_tags = []
        for p in projects:
            for c in p.containers:
                all_tags.append({
                    "name": c.tag_name,
                    "path": f"{c.image_path}:{c.tag_name}",
                    "project": p.project_path,
                    "branch_exists": c.branch_exists,
                    "is_git_tag": c.is_git_tag,
                    "author": c.author,
                    "created_at": c.tag_created_at.isoformat() if c.tag_created_at else "unknown"
                })
        return all_tags

    def get_git_audit_logs(self, limit: int = 50, audit_id: str = None, project_name: str = None):
        query = self.session.query(GitReleaseAuditLog)
        if audit_id:
            query = query.filter(GitReleaseAuditLog.id.startswith(audit_id))
        elif project_name:
            from sqlalchemy import or_
            short_name = project_name.split('/')[-1]
            query = query.filter(or_(
                GitReleaseAuditLog.project_name == project_name,
                GitReleaseAuditLog.project_name == short_name
            ))
        records = query.order_by(GitReleaseAuditLog.timestamp.desc()).limit(limit).all()
        result = []
        for rec in records:
            result.append({
                "id": rec.id,
                "timestamp": rec.timestamp.isoformat() if rec.timestamp else None,
                "project_name": rec.project_name,
                "source_branch": getattr(rec, 'source_branch', 'N/A'),
                "target_branch": getattr(rec, 'target_branch', 'N/A'),
                "merge_request_id": getattr(rec, 'merge_request_id', None),
                "version_tag": rec.version_tag,
                "action": rec.action,
                "actor": rec.actor,
                "status": rec.status,
                "error_message": getattr(rec, 'error_message', None),
                "changelog_generation_method": rec.changelog_generation_method,
                "merged_features_json": rec.merged_features_json,
                "job_details_json": rec.job_details_json
            })
        return result

    def get_successful_git_releases(self):
        return self.session.query(GitReleaseAuditLog).filter(GitReleaseAuditLog.status == 'SUCCESS').all()

    def get_active_git_release_audit_log(self, project_name: str):
        return self.session.query(GitReleaseAuditLog).filter_by(
            project_name=project_name, 
            status="RUNNING"
        ).first()

    def get_previous_successful_release(self, project_name: str, source_branch: str, target_branch: str, action: str):
        return self.session.query(GitReleaseAuditLog).filter_by(
            project_name=project_name,
            source_branch=source_branch,
            target_branch=target_branch,
            status="SUCCESS",
            action=action
        ).order_by(GitReleaseAuditLog.timestamp.desc()).first()