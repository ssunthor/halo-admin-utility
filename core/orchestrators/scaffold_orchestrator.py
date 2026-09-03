import os
import yaml
import logging
import logging
from core.database.models import HaloTenant, TenantCustomization
from core.connectors import cmu_connector, cmc_connector
from core.clients.netbox_client import NetboxClient
import secrets
import string
import json

logger = logging.getLogger(__name__)

class ScaffoldOrchestrator:
    def __init__(self, config, sql_writer=None):
        self.config = config
        self.sql_writer = sql_writer
        cmu_connector.init_cmu_connector(self.config)
        cmc_connector.init_cmc_connector(self.config)

    def scaffold_tenant(self, tenant, env, region, target_cluster, image_selections, variables, is_internal=False, netbox_slug=""):
        tenant_namespace = f"halo-{tenant}-{env}" if env else f"halo-{tenant}"
        yield f"Starting GitOps scaffold for {tenant_namespace} in {region}..."
        logger.info(f"Starting GitOps scaffold for {tenant_namespace} in {region}")
        
        # Derive internal if not explicitly passed but starts with gtt
        if not is_internal and tenant.startswith("gtt"):
            is_internal = True
            
        tenant_category = "INTERNAL" if is_internal else "CUSTOMER"
        
        # 1. Pre-flight Check: Does tenant exist in DB?
        yield "Checking local HAU database for existing tenant..."
        session = self.sql_writer.session
        existing = session.query(HaloTenant).filter_by(tenant_namespace=tenant_namespace).first()
        if existing:
            raise ValueError(f"Tenant {tenant_namespace} already exists in DB.")

        # 1.5. Pre-flight Check: Verify in NetBox and get basic info
        yield "Verifying tenant in NetBox..."
        netbox_config = self.config.get('external_services', {}).get('netbox', {})
        nb_url = netbox_config.get('url', '')
        nb_token = netbox_config.get('token', '')
        nb_verify_ssl = netbox_config.get('verify_ssl', False)
        
        if not nb_url or not nb_token:
            raise ValueError("Netbox URL or token not configured in settings.yaml")
            
        nb_client = NetboxClient(url=nb_url, token=nb_token, verify_ssl=nb_verify_ssl)
        
        actual_netbox_slug = netbox_slug if netbox_slug else (f"{tenant}-{env}" if env else tenant)
        if not netbox_slug and is_internal:
            actual_netbox_slug = "gtt-corp"
            
        nb_tenant = nb_client.get_tenant(actual_netbox_slug)
        
        if not nb_tenant:
            raise ValueError(f"Tenant {actual_netbox_slug} does not exist in NetBox. Please create it in NetBox first.")
            
        custom_fields = nb_tenant.get('custom_fields') or {}
        
        tenant_name = nb_tenant.get('name', tenant)
        netbox_id = nb_tenant.get('id')
        cmd_tenant_id = None
        cmd_group_id = None
        cmd_cst_id = custom_fields.get('cmd_cst_id')
        tenant_group = None
        
        if cmd_cst_id:
            msg = f"Tenant {tenant_namespace} has CMD ID {cmd_cst_id} in Netbox. Verifying against CMD..."
            logger.info(msg)
            yield msg
            
            cmc_info = cmc_connector.get_client_basic_info(int(cmd_cst_id))
            if not cmc_info or not cmc_info.get('success'):
                err = cmc_info.get('error_message') if cmc_info else "Failed to contact CMC"
                raise ValueError(f"Failed to fetch CMD info for client ID {cmd_cst_id}: {err}")
                
            cmd_cst_group_id = custom_fields.get('cmd_cst_group_id')
            if cmd_cst_group_id and str(cmd_cst_group_id) != str(cmc_info.get('group_id')):
                raise ValueError(f"Netbox group ID {cmd_cst_group_id} does not match CMD group ID {cmc_info.get('group_id')}!")
                
            tenant_name = cmc_info.get('client_name')
            tenant_group = cmc_info.get('group_name')
            cmd_tenant_id = str(cmd_cst_id)
            if cmd_cst_group_id:
                cmd_group_id = str(cmd_cst_group_id)
            elif cmc_info.get('group_id'):
                cmd_group_id = str(cmc_info.get('group_id'))
        else:
            msg = f"Tenant {tenant_namespace} has no CMD ID in Netbox. Proceeding as internal tenant."
            logger.info(msg)
            yield msg
            
            nb_group = nb_tenant.get('group')
            if nb_group:
                tenant_group = nb_group.get('name')

        # Save to DB
        new_tenant = HaloTenant(
            tenant_acronym=tenant,
            tenant_environment=env,
            tenant_namespace=tenant_namespace,
            tenant_name=tenant_name,
            tenant_group=tenant_group,
            cmd_tenant_id=cmd_tenant_id,
            cmd_group_id=cmd_group_id,
            netbox_id=netbox_id,
            netbox_slug=actual_netbox_slug,
            target_cluster=target_cluster
        )
        
        customization = TenantCustomization(
            tenant_id=new_tenant.id,
            tenant_category=tenant_category
        )
        new_tenant.customization = customization
        
        session.add(new_tenant)
        session.commit()
        logger.info(f"Registered tenant {tenant_namespace} ({tenant_name}) in HAU DB.")
        yield f"Registered tenant {tenant_namespace} ({tenant_name}) in HAU DB."

        # 2. Synchronous CMU Secret Generation
        yield from self._provision_cmu_secrets_sync(tenant, env, tenant_namespace, tenant_name, image_selections)

        # 3. GitOps Scaffolding
        yield "Generating GitOps manifests..."
        
        cluster_config = self.config.get('rancher_clusters', {}).get(region, {})
        halo_cluster_name = cluster_config.get('halo_cluster_name')
        if not halo_cluster_name:
            raise ValueError(f"halo_cluster_name is missing in settings.yaml for region {region}")
            
        repo_path = self.config.get('git_workspace', '/ai/utilities/halo_admin_utility/cache/halo/deployment')
        tenant_path = os.path.join(repo_path, 'tenants', region, tenant_namespace)
        app_path = os.path.join(tenant_path, 'app')
        gpu_path = os.path.join(tenant_path, 'gpu')
        
        os.makedirs(app_path, exist_ok=True)
        
        app_resources = []
        app_images = []
        gpu_resources = []
        gpu_images = []
        
        for component, image_tag in image_selections.items():
            is_vendor = (component == 'redis')
            base_dir = "vendor" if is_vendor else "halo"
            schema_path = os.path.join(repo_path, 'base', base_dir, component, 'schema.yaml')
            
            affinity = 'app'
            schema_data = {}
            if os.path.exists(schema_path):
                with open(schema_path, 'r') as f:
                    schema_data = yaml.safe_load(f) or {}
                affinity = schema_data.get('cluster_affinity', 'app')
            
            if affinity == 'gpu':
                os.makedirs(gpu_path, exist_ok=True)
                comp_path = os.path.join(gpu_path, component)
                resources_list = gpu_resources
                images_list = gpu_images
            else:
                comp_path = os.path.join(app_path, component)
                resources_list = app_resources
                images_list = app_images
                
            os.makedirs(comp_path, exist_ok=True)
            
            # Generate patch-env.yaml if needed
            env_vars = []
            for var in schema_data.get('variables', []):
                res = var.get('resolution')
                if res == 'ui_default':
                    val = var.get('default', '')
                    env_vars.append({"name": var['name'], "value": val})
                elif res == 'netbox_lookup':
                    val = str(netbox_id) if netbox_id else ""
                    env_vars.append({"name": var['name'], "value": val})
            
            has_patch = False
            if env_vars:
                patch_env = {
                    "apiVersion": "apps/v1",
                    "kind": "Deployment",
                    "metadata": {"name": component},
                    "spec": {
                        "template": {
                            "spec": {
                                "containers": [{
                                    "name": component,
                                    "env": env_vars
                                }]
                            }
                        }
                    }
                }
                with open(os.path.join(comp_path, "patch-env.yaml"), "w") as f:
                    yaml.dump(patch_env, f, default_flow_style=False, sort_keys=False)
                has_patch = True
            
            kust_content = {
                "apiVersion": "kustomize.config.k8s.io/v1beta1",
                "kind": "Kustomization",
                "namespace": tenant_namespace,
                "resources": [
                    f"../../../../base/{base_dir}/{component}"
                ]
            }
            if has_patch:
                kust_content["patchesStrategicMerge"] = ["patch-env.yaml"]
                
            if not is_vendor and image_tag and image_tag != "static":
                images_list.append({
                    "name": f"gitlab.gt-t.net:4567/ai/halo/{component}",
                    "newTag": image_tag
                })
                
            with open(os.path.join(comp_path, "kustomization.yaml"), "w") as f:
                yaml.dump(kust_content, f, default_flow_style=False, sort_keys=False)
                
            resources_list.append(component)
            
        # Write app kustomization
        if app_resources:
            with open(os.path.join(app_path, "kustomization.yaml"), "w") as f:
                app_kust = {
                    "namespace": tenant_namespace,
                    "commonAnnotations": {
                        "halo/target-cluster": halo_cluster_name,
                        "halo/source-file": f"deployment/tenants/{region}/{tenant_namespace}/app/kustomization.yaml"
                    },
                    "bases": app_resources
                }
                if app_images:
                    app_kust["images"] = app_images
                yaml.dump(app_kust, f, default_flow_style=False, sort_keys=False)

        # Write gpu kustomization
        if gpu_resources:
            gpu_cluster_name = cluster_config.get('gpu_cluster_name')
            if not gpu_cluster_name:
                raise ValueError(f"gpu_cluster_name is missing in settings.yaml for region {region}, but GPU components were selected.")
                
            with open(os.path.join(gpu_path, "kustomization.yaml"), "w") as f:
                gpu_kust = {
                    "namespace": tenant_namespace,
                    "commonAnnotations": {
                        "halo/target-cluster": gpu_cluster_name,
                        "halo/source-file": f"deployment/tenants/{region}/{tenant_namespace}/gpu/kustomization.yaml"
                    },
                    "bases": gpu_resources
                }
                if gpu_images:
                    gpu_kust["images"] = gpu_images
                yaml.dump(gpu_kust, f, default_flow_style=False, sort_keys=False)
                
        # Write root tenant kustomization
        tenant_root_resources = []
        if app_resources:
            tenant_root_resources.append("app")
        if gpu_resources:
            tenant_root_resources.append("gpu")
            
        with open(os.path.join(tenant_path, "kustomization.yaml"), "w") as f:
            yaml.dump({"resources": tenant_root_resources}, f, default_flow_style=False)
            
        logger.info(f"Successfully scaffolded {tenant} to {tenant_path}")
        yield f"Successfully scaffolded {tenant} to {tenant_path}"
        yield f"__DONE__:{tenant_path}"

    def _provision_cmu_secrets_sync(self, tenant, env, tenant_namespace, tenant_name, image_selections):
        msg = "Connecting to Configuration Management Utility (CMU) via gRPC..."
        logger.info(msg)
        yield msg
        
        repo_path = self.config.get('git_workspace', '/ai/utilities/halo_admin_utility/cache/halo/deployment')
        provisioned_paths = set()
        
        for component in image_selections.keys():
            is_vendor = (component == 'redis')
            base_dir = "vendor" if is_vendor else "halo"
            schema_path = os.path.join(repo_path, 'base', base_dir, component, 'schema.yaml')
            
            if not os.path.exists(schema_path):
                continue
                
            with open(schema_path, 'r') as f:
                schema_data = yaml.safe_load(f) or {}
                
            vp = f"{tenant}-{env}" if env else tenant
            for var in schema_data.get('variables', []):
                resolution = var.get('resolution')
                if resolution == 'cmu_generate':
                    fmt = var.get('format', '').replace('{tenant_acronym}', vp)
                    if var.get('cmu_type') == 'oidc_client_id':
                        if fmt in provisioned_paths:
                            continue
                        provisioned_paths.add(fmt)
                        
                        msg = f"Generating OIDC client {fmt} via CMU..."
                        logger.info(msg)
                        yield msg
                        
                        app_name = f"halo-{tenant}"
                        
                        description_str = f"Halo {tenant.upper()} {env.capitalize() if env else ''}".strip()
                        ident_resp = cmu_connector.create_identity(
                            app_name=app_name,
                            environment=env,
                            requestor="HAU",
                            description=description_str
                        )
                        if not ident_resp.get('success'):
                            raise Exception(f"Failed to create OIDC client in CMU: {ident_resp.get('error_message')}")

                elif resolution == 'hau_generate':
                    vault_path_template = var.get('vault_path', '')
                    if '{tenant_acronym}' in vault_path_template:
                        # Fallback just in case, but usually we map to the exact namespace or the new vault structure
                        # The plan specifies: f"halo/{req.tenant}-{req.env}" if req.env else f"halo/{req.tenant}"
                        vp = f"{tenant}-{env}" if env else tenant
                        vault_path = vault_path_template.replace('{tenant_acronym}', vp)
                    else:
                        vault_path = vault_path_template
                        
                    if vault_path in provisioned_paths:
                        continue
                    provisioned_paths.add(vault_path)
                    
                    alphabet = string.ascii_letters + string.digits
                    secure_pass = ''.join(secrets.choice(alphabet) for i in range(32))
                    
                    if vault_path:
                        if vault_path.startswith("secret/"):
                            vault_path = vault_path[len("secret/"):]
                            
                        msg = f"Writing internally generated secure password to Vault at {vault_path} via CMU..."
                        logger.info(msg)
                        yield msg
                        
                        key_name = var.get('name')
                        vault_resp = cmu_connector.write_to_vault(vault_path, {
                            key_name: secure_pass
                        })
                        if not vault_resp.get('success'):
                            raise Exception(f"Failed to write internal secret to Vault via CMU: {vault_resp.get('error_message')}")
                            
        msg = f"CMU successfully provisioned and vaulted secrets for tenant {tenant_namespace}"
        logger.info(msg)
        yield msg
