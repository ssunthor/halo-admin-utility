import os
import shutil
import logging
import logging
from core.database.models import HaloTenant
from core.connectors import cmu_connector

logger = logging.getLogger(__name__)

class DecommissionOrchestrator:
    def __init__(self, config, sql_writer):
        self.config = config
        self.sql_writer = sql_writer
        cmu_connector.init_cmu_connector(self.config)

    def decommission_tenant(self, tenant_acronym: str, region: str):
        msg = f"Starting decommissioning for tenant {tenant_acronym} in {region}"
        logger.info(msg)
        yield msg
        
        session = self.sql_writer.session
        tenant = session.query(HaloTenant).filter_by(tenant_acronym=tenant_acronym).first()
        
        if not tenant:
            msg = f"Tenant {tenant_acronym} not found in DB. Proceeding with cleanup of external resources anyway."
            logger.warning(msg)
            yield msg
        
        # 1. Cleanup CMU (Keycloak Identity & Vault Secrets)
        client_id = f"halo-{tenant_acronym}"
        msg = f"Deleting Keycloak identity {client_id} via CMU..."
        logger.info(msg)
        yield msg
        
        ident_res = cmu_connector.delete_identity(client_id)
        if not ident_res.get('success'):
            msg = f"Failed to delete identity {client_id}: {ident_res.get('error_message')}"
            logger.warning(msg)
            yield msg
        else:
            msg = f"Successfully deleted Keycloak identity {client_id}"
            logger.info(msg)
            yield msg

        vault_path = f"halo/{tenant_acronym}"
        msg = f"Deleting Vault secrets at {vault_path} via CMU..."
        logger.info(msg)
        yield msg
        
        vault_res = cmu_connector.delete_from_vault(vault_path)
        if not vault_res.get('success'):
            msg = f"Failed to delete vault secrets at {vault_path}: {vault_res.get('error_message')}"
            logger.warning(msg)
            yield msg
        else:
            msg = f"Successfully deleted Vault secrets at {vault_path}"
            logger.info(msg)
            yield msg

        # 2. Local File System Cleanup
        repo_path = self.config.get('git_workspace', '/ai/utilities/halo_admin_utility/cache/halo/deployment')
        tenant_path = os.path.join(repo_path, 'tenants', region, f"halo-{tenant_acronym}")
        
        if os.path.exists(tenant_path):
            msg = f"Removing GitOps directory {tenant_path}..."
            logger.info(msg)
            yield msg
            try:
                shutil.rmtree(tenant_path)
                msg = f"Successfully removed {tenant_path}"
                logger.info(msg)
                yield msg
            except Exception as e:
                msg = f"Failed to remove {tenant_path}: {e}"
                logger.error(msg)
                yield msg
        else:
            msg = f"GitOps directory {tenant_path} does not exist. Skipping."
            logger.info(msg)
            yield msg

        # 3. Database Teardown
        if tenant:
            msg = f"Deleting tenant {tenant_acronym} from DB..."
            logger.info(msg)
            yield msg
            try:
                session.delete(tenant)
                session.commit()
                msg = f"Successfully removed tenant {tenant_acronym} from DB."
                logger.info(msg)
                yield msg
            except Exception as e:
                session.rollback()
                msg = f"Failed to delete tenant from DB: {e}"
                logger.error(msg)
                yield msg
                raise
                
        yield "__DONE__"
