from sqlalchemy import Column, String, DateTime, ForeignKey, Boolean, Enum as SQLEnum, JSON
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
    cmd_tenant_id = Column(String(255), nullable=True) # Link to CMD
    slug_name = Column(String(255), nullable=False, unique=True)
    target_cluster = Column(String(50), nullable=False)
    halo_version = Column(String(50), nullable=True)
    environment = Column(String(50), nullable=True)
    is_internal = Column(Boolean, default=False)
    url = Column(String(255), nullable=True)
    lifecycle_state = Column(SQLEnum(LifecycleState), default=LifecycleState.ONBOARDING)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    feature_flags = relationship("TenantFeatureFlag", back_populates="tenant", cascade="all, delete-orphan")
    collectors = relationship("CollectorInventory", back_populates="tenant", cascade="all, delete-orphan")
    deployment_logs = relationship("DeploymentAuditLog", back_populates="tenant", cascade="all, delete-orphan")
    resources = relationship("TenantResourceInventory", back_populates="tenant", cascade="all, delete-orphan")

class TenantFeatureFlag(Base):
    __tablename__ = 'tenant_feature_flag'
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    tenant_id = Column(String(36), ForeignKey('halo_tenant.id'), nullable=False)
    feature_key = Column(String(255), nullable=False)
    is_enabled = Column(Boolean, default=False)
    custom_value = Column(String(255), nullable=True)

    tenant = relationship("HaloTenant", back_populates="feature_flags")

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
    """
    Similar to CMU's AiModelInventory, tracks specific deployed assets for the tenant.
    e.g., Ingress (Cloudflare DNS), Keycloak Realms, specific Pipelines.
    """
    __tablename__ = 'tenant_resource_inventory'
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    tenant_id = Column(String(36), ForeignKey('halo_tenant.id'), nullable=False)
    resource_type = Column(String(50), nullable=False) # e.g., 'INGRESS', 'KEYCLOAK_REALM', 'PIPELINE'
    resource_name = Column(String(255), nullable=False) # e.g., 'corp.defensehalo.ai'
    status = Column(String(50), default='PROVISIONED')
    metadata_json = Column(JSON, nullable=True) # Additional config tracking

    tenant = relationship("HaloTenant", back_populates="resources")

class DeploymentAuditLog(Base):
    __tablename__ = 'deployment_audit_log'
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    tenant_id = Column(String(36), ForeignKey('halo_tenant.id'), nullable=False)
    actor = Column(String(255), nullable=False) # Aligned with CMU
    action = Column(String(255), nullable=False) # e.g., DEPLOY_TENANT, UPDATE_INGRESS
    domain = Column(String(255), nullable=False) # e.g., Ingress, Pipeline, Core
    target_cluster = Column(String(255), nullable=True)
    payload_reference = Column(String(255), nullable=True) # Git commit, YAML path, etc.
    gitlab_pipeline_id = Column(String(255), nullable=True)
    status = Column(SQLEnum(DeploymentStatus), default=DeploymentStatus.TRIGGERED)
    timestamp = Column(DateTime, default=datetime.utcnow)

    tenant = relationship("HaloTenant", back_populates="deployment_logs")


