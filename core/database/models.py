from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Boolean, Enum as SQLEnum, JSON
from sqlalchemy.orm import declarative_base, relationship
import uuid
from datetime import datetime
import enum

Base = declarative_base()

def generate_uuid():
    return str(uuid.uuid4())

class LifecycleState(enum.Enum):
    ONBOARDING = "ONBOARDING"
    AI_BURN_IN = "AI_BURN_IN"
    GO_LIVE_APPROVED = "GO_LIVE_APPROVED"
    ACTIVE_BILLING = "ACTIVE_BILLING"
    ORPHANED = "ORPHANED"
    DECOMMISSIONING = "DECOMMISSIONING"
    DECOMMISSIONED = "DECOMMISSIONED"

class CollectorHealth(enum.Enum):
    PROVISIONING = "PROVISIONING"
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    OFFLINE = "OFFLINE"

class DeploymentStatus(enum.Enum):
    TRIGGERED = "TRIGGERED"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"

class HaloTenant(Base):
    __tablename__ = 'halo_tenant'
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    cmd_tenant_id = Column(String(255), nullable=True)
    cmd_group_id = Column(String(255), nullable=True)
    netbox_id = Column(Integer, nullable=True)
    tenant_acronym = Column(String(50), nullable=False)
    tenant_environment = Column(String(50), nullable=True)
    tenant_name = Column(String(255), nullable=False)
    tenant_group = Column(String(255), nullable=True)
    tenant_namespace = Column(String(255), nullable=False, unique=True)
    netbox_slug = Column(String(255), nullable=True)
    target_cluster = Column(String(50), nullable=False)
    halo_version = Column(String(50), nullable=True)
    url = Column(String(255), nullable=True)
    lifecycle_state = Column(SQLEnum(LifecycleState), default=LifecycleState.ONBOARDING)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    customization = relationship("TenantCustomization", back_populates="tenant", uselist=False, cascade="all, delete-orphan")
    collectors = relationship("CollectorInventory", back_populates="tenant", cascade="all, delete-orphan")
    deployment_logs = relationship("DeploymentAuditLog", back_populates="tenant", cascade="all, delete-orphan")
    resources = relationship("TenantResourceInventory", back_populates="tenant", cascade="all, delete-orphan")

class TenantCustomization(Base):
    __tablename__ = 'tenant_customization'
    
    tenant_id = Column(String(36), ForeignKey('halo_tenant.id'), primary_key=True)
    tenant_category = Column(String(50), default="CUSTOMER")
    tenant_tier = Column(String(50), default="UNKNOWN")
    update_policy = Column(String(50), default="MANUAL_ONLY")
    owner = Column(String(255), default="UNASSIGNED")
    purpose = Column(String(255), nullable=True)
    maintenance_window = Column(String(255), nullable=True)
    configuration_payload = Column(JSON, default=dict)
    component_versions = Column(JSON, default=dict)

    tenant = relationship("HaloTenant", back_populates="customization")

class CollectorInventory(Base):
    __tablename__ = 'collector_inventory'
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    tenant_id = Column(String(36), ForeignKey('halo_tenant.id'), nullable=False)
    hostname = Column(String(255), nullable=False)
    ha_pair_id = Column(String(36), nullable=True)
    health_status = Column(SQLEnum(CollectorHealth), default=CollectorHealth.PROVISIONING)
    last_heartbeat = Column(DateTime, nullable=True)

    tenant = relationship("HaloTenant", back_populates="collectors")

class TenantResourceInventory(Base):
    __tablename__ = 'tenant_resource_inventory'
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    tenant_id = Column(String(36), ForeignKey('halo_tenant.id'), nullable=False)
    resource_type = Column(String(50), nullable=False)
    resource_name = Column(String(255), nullable=False)
    cluster_name = Column(String(50), nullable=True)
    status = Column(String(50), default='PROVISIONED')
    metadata_json = Column(JSON, nullable=True)

    tenant = relationship("HaloTenant", back_populates="resources")

class DeploymentAuditLog(Base):
    __tablename__ = 'deployment_audit_log'
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    tenant_id = Column(String(36), ForeignKey('halo_tenant.id'), nullable=False)
    actor = Column(String(255), nullable=False)
    action = Column(String(255), nullable=False)
    domain = Column(String(255), nullable=False)
    target_cluster = Column(String(255), nullable=True)
    payload_reference = Column(String(255), nullable=True)
    gitlab_pipeline_id = Column(String(255), nullable=True)
    status = Column(SQLEnum(DeploymentStatus), default=DeploymentStatus.TRIGGERED)
    timestamp = Column(DateTime, default=datetime.utcnow)
    tenant = relationship("HaloTenant", back_populates="deployment_logs")

class GitReleaseAuditLog(Base):
    __tablename__ = 'git_release_audit_log'
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    project_name = Column(String(255), nullable=False)
    source_branch = Column(String(255), nullable=True)
    target_branch = Column(String(255), nullable=True)
    merge_request_id = Column(String(50), nullable=True)
    version_tag = Column(String(50), nullable=True)
    action = Column(String(50), nullable=False)
    actor = Column(String(255), nullable=False, default="gia-ai")
    status = Column(String(50), nullable=False, default="RUNNING")
    error_message = Column(String, nullable=True)
    changelog_generation_method = Column(String(50), nullable=True)
    merged_features_json = Column(JSON, nullable=True)
    job_details_json = Column(JSON, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class ProjectType(enum.Enum):
    APPLICATION = "APPLICATION"
    INFORMATIONAL = "INFORMATIONAL"
    TEMPLATE = "TEMPLATE"

class GitProject(Base):
    __tablename__ = 'git_project'
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    project_path = Column(String(255), nullable=False, unique=True)
    project_name = Column(String(100), nullable=False)
    repo_path = Column(String(255), nullable=True)
    subpath = Column(String(255), nullable=True)
    project_type = Column(SQLEnum(ProjectType), default=ProjectType.APPLICATION)
    
    is_deprecated = Column(Boolean, default=False)
    is_ignored = Column(Boolean, default=False)
    native_releases = Column(JSON, default=list)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    branches = relationship("GitBranch", back_populates="project", cascade="all, delete-orphan")
    containers = relationship("GitContainer", back_populates="project", cascade="all, delete-orphan")

class FeatureCatalog(Base):
    __tablename__ = 'feature_catalog'
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    feature_name = Column(String(255), nullable=False)
    description = Column(String, nullable=True)
    product_category = Column(String(100), nullable=True)
    ui_grouping = Column(String(100), nullable=True)
    env_variable = Column(String(255), nullable=False, unique=True)
    gitops_dependencies = Column(JSON, default=dict)
    pricing_tiers = Column(JSON, default=dict)
    is_paid_addon = Column(Boolean, default=False)
    enabled_by_default = Column(Boolean, default=False)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class GitBranch(Base):
    __tablename__ = 'git_branch'
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    project_id = Column(String(36), ForeignKey('git_project.id'), nullable=False)
    name = Column(String(255), nullable=False)
    author = Column(String(255), nullable=True)
    last_updated_at = Column(DateTime, nullable=True)
    
    project = relationship("GitProject", back_populates="branches")

class GitContainer(Base):
    __tablename__ = 'git_container'
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    project_id = Column(String(36), ForeignKey('git_project.id'), nullable=False)
    tag_name = Column(String(255), nullable=False)
    image_path = Column(String(512), nullable=False)
    author = Column(String(255), nullable=True)
    is_git_tag = Column(Boolean, default=False)
    branch_exists = Column(Boolean, default=False)
    has_native_release = Column(Boolean, default=False)
    tag_created_at = Column(DateTime, nullable=True)
    
    project = relationship("GitProject", back_populates="containers")