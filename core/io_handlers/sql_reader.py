import logging
from sqlalchemy.orm import Session
from sqlalchemy import or_
from core.database.models import HaloTenant, TenantResourceInventory, GitProject, GitReleaseAuditLog, GitBranch

logger = logging.getLogger(__name__)

class SQLReader:
    def __init__(self, session: Session):
        self.session = session

    def get_tenant(self, namespace=None, tenant=None, env=None):
        if namespace: namespace = namespace.lower()
        if tenant: tenant = tenant.lower()
        if env: env = env.lower()
        
        query = self.session.query(HaloTenant)
        if namespace:
            query = query.filter_by(tenant_namespace=namespace)
        elif tenant and env:
            query = query.filter_by(tenant_acronym=tenant, tenant_environment=env)
        elif tenant:
            query = query.filter_by(tenant_acronym=tenant)
        else:
            return None
            
        results = query.all()
        if len(results) > 1:
            raise ValueError(f"Multiple environments found for tenant '{tenant}'. Please specify --env or --namespace.")
        elif len(results) == 1:
            return results[0]
        return None

    def get_all_tenants(self, tenant_namespace=None, tenant=None, env=None):
        if tenant_namespace: tenant_namespace = tenant_namespace.lower()
        if tenant: tenant = tenant.lower()
        if env: env = env.lower()
        
        from sqlalchemy.orm import joinedload
        query = self.session.query(HaloTenant).options(joinedload(HaloTenant.customization))
        if tenant_namespace:
            query = query.filter_by(tenant_namespace=tenant_namespace)
        elif tenant and env:
            query = query.filter_by(tenant_acronym=tenant, tenant_environment=env)
        elif tenant:
            query = query.filter_by(tenant_acronym=tenant)
        return query.all()

    def get_feature_catalog(self):
        from core.database.models import FeatureCatalog
        return self.session.query(FeatureCatalog).order_by(FeatureCatalog.product_category, FeatureCatalog.ui_grouping).all()

    def get_feature_by_env(self, env_variable: str):
        from core.database.models import FeatureCatalog
        return self.session.query(FeatureCatalog).filter_by(env_variable=env_variable).first()

    def get_all_inventory(self, tenant_namespace: str = None, tenant: str = None, env: str = None):
        if tenant_namespace: tenant_namespace = tenant_namespace.lower()
        if tenant: tenant = tenant.lower()
        if env: env = env.lower()
        
        from sqlalchemy.orm import joinedload
        query = self.session.query(HaloTenant).options(joinedload(HaloTenant.customization))
        if tenant_namespace:
            query = query.filter_by(tenant_namespace=tenant_namespace)
        elif tenant and env:
            query = query.filter_by(tenant_acronym=tenant, tenant_environment=env)
        elif tenant:
            query = query.filter_by(tenant_acronym=tenant)
            
        tenants = query.all()
        result = {}
        for t in tenants:
            if t.tenant_namespace not in result:
                result[t.tenant_namespace] = {}
            
            tenant_dict = {
                "tenant_namespace": t.tenant_namespace,
                "tenant_category": t.customization.tenant_category if t.customization else "CUSTOMER",
                "tenant_tier": t.customization.tenant_tier if t.customization else "UNKNOWN",
                "update_policy": t.customization.update_policy if t.customization else "MANUAL_ONLY",
                "owner": t.customization.owner if t.customization else "UNASSIGNED",
                "purpose": t.customization.purpose if t.customization else None,
                "maintenance_window": t.customization.maintenance_window if t.customization else None,
                "configuration_payload": t.customization.configuration_payload if t.customization else {},
                "component_versions": t.customization.component_versions if t.customization else {},
                "url": t.url
            }
            
            for r in t.resources:
                r_type = r.resource_type
                    
                item = r.metadata_json or {}
                item["name"] = r.resource_name
                r_cluster = r.cluster_name or t.target_cluster
                item["cluster"] = r_cluster
                
                if r_cluster not in result[t.tenant_namespace]:
                    result[t.tenant_namespace][r_cluster] = dict(tenant_dict)
                    result[t.tenant_namespace][r_cluster]["resources"] = {}
                
                if r_type not in result[t.tenant_namespace][r_cluster]["resources"]:
                    result[t.tenant_namespace][r_cluster]["resources"][r_type] = []
                    
                result[t.tenant_namespace][r_cluster]["resources"][r_type].append(item)
                
            if not t.resources:
                result[t.tenant_namespace][t.target_cluster] = dict(tenant_dict)
                result[t.tenant_namespace][t.target_cluster]["resources"] = {}
                
        return result

    def get_active_deployments_counts(self):
        counts = {}
        resources = self.session.query(TenantResourceInventory).all()
        for r in resources:
            if not r.metadata_json: continue
            
            reg_raw = r.metadata_json.get('registry', '')
            reg_path = reg_raw.split('/', 1)[1].rstrip('/') if '/' in reg_raw else ''
            
            images = []
            if 'image' in r.metadata_json:
                images.append((r.metadata_json['image'], reg_path))
            for cont in r.metadata_json.get('containers', []):
                if 'image' in cont:
                    c_reg_raw = cont.get('registry', reg_raw)
                    c_reg_path = c_reg_raw.split('/', 1)[1].rstrip('/') if '/' in c_reg_raw else reg_path
                    images.append((cont['image'], c_reg_path))
                    
            for img, r_path in images:
                keys_to_update = []
                if r_path:
                    keys_to_update.append(f"{r_path}/{img}")
                    if r_path.startswith('ai/halo'):
                        keys_to_update.append(img)
                else:
                    keys_to_update.append(img)
                    
                for k in keys_to_update:
                    if k not in counts:
                        counts[k] = {'count': 0, 'namespaces': set()}
                    if r.tenant:
                        counts[k]['namespaces'].add(r.tenant.tenant_namespace)
                    
        for k in counts:
            counts[k]['namespaces'] = sorted(list(counts[k]['namespaces']))
            counts[k]['count'] = len(counts[k]['namespaces'])
            
        return counts

    def get_git_inventory(self, project_filter: str = None):
        query = self.session.query(GitProject).filter_by(is_ignored=False)
        
        if project_filter:
            query = query.filter(
                (GitProject.project_name == project_filter) | 
                (GitProject.project_path == project_filter) |
                (GitProject.repo_path == project_filter) |
                (GitProject.project_path.like(f"%/{project_filter}")) |
                (GitProject.repo_path.like(f"%/{project_filter}"))
            )
            
        active_deployments = self.get_active_deployments_counts()
        all_logs = self.get_all_git_releases_ordered()
        
        audit_mapping = {}
        tag_status = {}
        tag_author = {}
        tag_created = {}
        
        for log in all_logs:
            if log.version_tag and log.project_name and log.status == 'SUCCESS':
                key = (log.project_name, log.version_tag)
                if key not in tag_status:
                    tag_status[key] = log.action
                    tag_author[key] = log.actor
                    tag_created[key] = log.timestamp.isoformat()
                    
                if log.action in ('GIT_RELEASE', 'GIT_RETRY'):
                    if log.project_name not in audit_mapping:
                        audit_mapping[log.project_name] = {}
                    if log.version_tag not in audit_mapping[log.project_name]:
                        audit_mapping[log.project_name][log.version_tag] = log.source_branch

        projects = query.all()
        if project_filter and not project_filter.startswith("ai/"):
            defense_matches = [p for p in projects if p.project_path.startswith("ai/defense-halo/")]
            if defense_matches:
                projects = defense_matches
                
        projects.sort(key=lambda p: (0 if p.project_path.startswith("ai/defense-halo/") else 1, p.project_path))
        result = []
        for p in projects:
            p_audit = dict(audit_mapping.get(p.project_path, {}))
            if p.repo_path and p.repo_path in audit_mapping:
                for k, v in audit_mapping[p.repo_path].items():
                    p_audit.setdefault(k, v)
                    if k.startswith(f"{p.project_name}-"):
                        p_audit.setdefault(k[len(p.project_name) + 1:], v)
                        
            branches = {b.name: {"author": b.author, "last_updated_at": b.last_updated_at.isoformat() if getattr(b, "last_updated_at", None) else None} for b in p.branches}
            
            releases = []
            pre_releases = []
            features = []
            standalone_features = []
            core_environments = []
            inactive_releases = []
            
            def _lookup_deployment(image_path: str, tag_val: str):
                full_img = f"{image_path}:{tag_val}" if image_path else f"{p.project_path}:{tag_val}"
                if full_img in active_deployments:
                    return active_deployments[full_img]
                proj_img = f"{p.project_path}:{tag_val}"
                if proj_img in active_deployments:
                    return active_deployments[proj_img]
                if p.project_path.startswith("ai/halo/"):
                    short_name = image_path.split('/')[-1] if image_path else p.project_name
                    short_img = f"{short_name}:{tag_val}"
                    if short_img in active_deployments:
                        return active_deployments[short_img]
                return {}
            
            matched_containers = set()
            for c in p.containers:
                tag = c.tag_name
                deploy_info = _lookup_deployment(c.image_path, tag)
                deploy_count = deploy_info.get('count', 0)
                deploy_namespaces = deploy_info.get('namespaces', [])
                
                c_info = {
                    "tag": tag,
                    "author": c.author,
                    "created_at": c.tag_created_at.isoformat() if c.tag_created_at else "unknown",
                    "active_deployments": deploy_count,
                    "active_namespaces": deploy_namespaces,
                    "has_native_release": c.has_native_release,
                    "is_inactive": False
                }
                
                if tag.startswith('v') and '-dev' not in tag:
                    c_info["branch"] = "main" if "main" in branches else "master"
                    c_info["is_git_tag"] = c.is_git_tag
                    c_info["branch_exists"] = c.branch_exists
                    releases.append(c_info)
                    matched_containers.add(tag)
                elif tag.startswith('v') and '-dev' in tag:
                    c_info["source_feature"] = p_audit.get(tag, p_audit.get(f"{p.project_name}-{tag}", "Unknown"))
                    pre_releases.append(c_info)
                    matched_containers.add(tag)
                else:
                    for b_name, b_info in branches.items():
                        sanitized_b = b_name.replace('/', '-')
                        if tag == sanitized_b:
                            feat_info = {
                                "branch": b_name,
                                "branch_author": b_info.get("author", "Unknown"),
                                "last_updated_at": b_info.get("last_updated_at"),
                                "container_tag": tag,
                                "container_created": c_info["created_at"],
                                "active_deployments": deploy_count,
                                "active_namespaces": deploy_namespaces,
                                "has_native_release": c.has_native_release
                            }
                            if b_name in ["main", "master", "dev"]:
                                core_environments.append(feat_info)
                            else:
                                features.append(feat_info)
                            matched_containers.add(tag)
                            break
                            
            for key, action in tag_status.items():
                if key[0] == p.project_path and action == 'DELETE':
                    tag = key[1]
                    if tag not in matched_containers:
                        native_list = p.native_releases or []
                        has_native_release = (
                            tag in native_list or
                            f"{p.project_name}-{tag}" in native_list or
                            f"{p.project_name}/{tag}" in native_list
                        )
                        if not has_native_release:
                            continue
                            
                        inactive_info = {
                            "tag": tag,
                            "author": tag_author.get(key, "Unknown"),
                            "created_at": tag_created.get(key, "unknown"),
                            "active_deployments": 0,
                            "active_namespaces": [],
                            "has_native_release": True,
                            "is_inactive": True
                        }
                        if tag.startswith('v') and '-dev' not in tag:
                            inactive_info["branch"] = "main" if "main" in branches else "master"
                            inactive_info["is_git_tag"] = True
                            inactive_info["branch_exists"] = False
                            inactive_releases.append(inactive_info)
                        elif tag.startswith('v') and '-dev' in tag:
                            inactive_info["source_feature"] = p_audit.get(tag, p_audit.get(f"{p.project_name}-{tag}", "Unknown"))
                            inactive_releases.append(inactive_info)
                            
            for c in p.containers:
                if c.tag_name not in matched_containers:
                    deploy_info = _lookup_deployment(c.image_path, c.tag_name)
                    standalone_features.append({
                        "tag": c.tag_name,
                        "author": c.author,
                        "created_at": c.tag_created_at.isoformat() if c.tag_created_at else "unknown",
                        "active_deployments": deploy_info.get('count', 0),
                        "active_namespaces": deploy_info.get('namespaces', []),
                        "has_native_release": c.has_native_release
                    })
                    
            matched_branches = [f["branch"] for f in features] + [f["branch"] for f in core_environments if "branch" in f]
            active_branches_without_containers = []
            
            # Extract known container repository paths for this project
            known_image_paths = set(c.image_path for c in p.containers if c.image_path)
            if not known_image_paths:
                known_image_paths = {p.project_path}
                
            for b_name, b_info in branches.items():
                if b_name not in matched_branches:
                    sanitized_b = b_name.replace('/', '-')
                    
                    # Proactively check if there are active deployments for this branch
                    # even if the container tag was deleted from the registry (e.g. by cleanup pipelines)
                    deploy_namespaces_set = set()
                    for img_path in known_image_paths:
                        d_info = _lookup_deployment(img_path, sanitized_b)
                        if d_info:
                            deploy_namespaces_set.update(d_info.get('namespaces', []))
                    deploy_namespaces = sorted(list(deploy_namespaces_set))
                    deploy_count = len(deploy_namespaces)
                    
                    branch_info = {
                        "branch": b_name, 
                        "author": b_info.get("author", "Unknown"), 
                        "last_updated_at": b_info.get("last_updated_at")
                    }
                    
                    # If it has active deployments, we map it to the branch so it's not invisible
                    if deploy_count > 0:
                        branch_info["container_tag"] = sanitized_b
                        branch_info["container_created"] = "unknown"
                        branch_info["active_deployments"] = deploy_count
                        branch_info["active_namespaces"] = deploy_namespaces
                        branch_info["has_native_release"] = False
                    
                    if b_name in ["main", "master", "dev"]:
                        core_environments.append(branch_info)
                    else:
                        if deploy_count > 0:
                            features.append(branch_info)
                        else:
                            active_branches_without_containers.append(branch_info)
            
            proj_data = {
                "name": p.project_name,
                "path": p.project_path,
                "repo_path": p.repo_path or p.project_path,
                "subpath": p.subpath or "",
                "type": p.project_type.name,
                "is_deprecated": p.is_deprecated,
                "inventory": {
                    "core_environments": sorted(core_environments, key=lambda x: x.get('branch', '')),
                    "releases": sorted(releases, key=lambda x: x['tag'], reverse=True),
                    "pre_releases": sorted(pre_releases, key=lambda x: x['tag'], reverse=True),
                    "features": sorted(features, key=lambda x: x['branch']),
                    "standalone_features": sorted(standalone_features, key=lambda x: x['tag']),
                    "active_branches_without_containers": sorted(active_branches_without_containers, key=lambda x: x['branch']),
                    "inactive_releases": sorted(inactive_releases, key=lambda x: x['tag'], reverse=True)
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
            short_name = project_name.split('/')[-1]
            query = query.filter(or_(
                GitReleaseAuditLog.project_name == project_name,
                GitReleaseAuditLog.project_name == short_name,
                GitReleaseAuditLog.project_name.like(f"%/{short_name}")
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
        return self.session.query(GitReleaseAuditLog).filter(GitReleaseAuditLog.status == 'SUCCESS').order_by(GitReleaseAuditLog.timestamp.desc()).all()

    def get_all_git_releases_ordered(self):
        return self.session.query(GitReleaseAuditLog).order_by(GitReleaseAuditLog.timestamp.desc()).all()

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

    def resolve_project_obj(self, project_name: str):
        if not project_name:
            return None
        matches = self.session.query(GitProject).filter(
            or_(
                GitProject.project_path == project_name,
                GitProject.project_name == project_name,
                GitProject.project_path.like(f"%/{project_name}"),
                GitProject.repo_path == project_name
            )
        ).all()
        if not matches:
            return None
        for m in matches:
            if m.project_path == project_name:
                return m
        defense_matches = [m for m in matches if m.project_path.startswith("ai/defense-halo/")]
        if defense_matches:
            return defense_matches[0]
        return matches[0]

    def resolve_project_path(self, project_name: str) -> str:
        if not project_name:
            return project_name
        proj = self.resolve_project_obj(project_name)
        return proj.project_path if proj else project_name

    def get_git_project_by_name(self, project_name: str):
        matches = self.session.query(GitProject).filter(
            or_(
                GitProject.project_name == project_name,
                GitProject.project_path == project_name,
                GitProject.project_path.like(f"%/{project_name}"),
                GitProject.repo_path == project_name
            )
        ).all()
        if not matches:
            return []
        exact = [m for m in matches if m.project_path == project_name]
        if exact:
            return exact
        if not project_name.startswith("ai/"):
            defense_matches = [m for m in matches if m.project_path.startswith("ai/defense-halo/")]
            if defense_matches:
                return defense_matches
        return matches

    def get_git_branch(self, project_id: str, branch_name: str):
        return self.session.query(GitBranch).filter_by(project_id=project_id, name=branch_name).first()

    def get_latest_audit_log_by_mr(self, project_name: str, merge_request_id: str):
        return self.session.query(GitReleaseAuditLog).filter_by(
            project_name=project_name, 
            action="GIT_RELEASE",
            merge_request_id=merge_request_id
        ).order_by(GitReleaseAuditLog.timestamp.desc()).first()
        
    def get_git_release_audit_log_by_id(self, log_id: str):
        return self.session.query(GitReleaseAuditLog).filter_by(id=log_id).first()