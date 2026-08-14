import logging
import ipaddress
from collections import defaultdict
from core.clients.netbox_client import NetboxClient
from core.connectors.cmc_connector import init_cmc_connector, get_segment_a_site, get_gnid_a_site

logger = logging.getLogger(__name__)

class NetboxAuditManager:
    def __init__(self, config: dict):
        self.config = config
        init_cmc_connector(self.config)
        
        netbox_config = self.config.get('external_services', {}).get('netbox', {})
        self.nb_url = netbox_config.get('url', '')
        self.nb_token = netbox_config.get('token', '')
        self.verify_ssl = netbox_config.get('verify_ssl', False)
        
    def audit_tenant(self, tenant: str, ip_audit: bool = False):
        if not self.nb_url or not self.nb_token:
            raise ValueError("Netbox URL or token not configured in settings.yaml")
            
        client = NetboxClient(url=self.nb_url, token=self.nb_token, verify_ssl=self.verify_ssl)
        
        # Fetch data
        logger.info(f"Fetching devices and VMs for tenant: {tenant}")
        devices = client.get_devices(tenant=tenant)
        vms = client.get_vms(tenant=tenant)
        
        ip_audit_report = []
        if ip_audit:
            logger.info("Performing detailed IP audit...")
            dev_ids = [d['id'] for d in devices]
            vm_ids = [v['id'] for v in vms]
            
            dev_interfaces = client.get_device_interfaces(dev_ids)
            vm_interfaces = client.get_vm_interfaces(vm_ids)
            
            dev_ips = client.get_device_ips(dev_ids)
            vm_ips = client.get_vm_ips(vm_ids)
            ips = dev_ips + vm_ips
            
            # Map IP to interface
            iface_to_ips = defaultdict(list)
            for ip in ips:
                ip_str = ip.get('address', '')
                if '/' in ip_str:
                    ip_str = ip_str.split('/')[0]
                try:
                    ip_obj = ipaddress.ip_address(ip_str)
                    is_private = ip_obj.is_private
                except ValueError:
                    is_private = True
                    
                ip_tenant = ip.get('tenant', {})
                is_mismatched = False
                if ip_tenant:
                    if ip_tenant.get('slug', '').lower() != tenant.lower():
                        is_mismatched = True
                else:
                    is_mismatched = True # IP has no tenant, therefore mismatched
                
                if ip.get('assigned_object_type') in ['dcim.interface', 'virtualization.vminterface'] and ip.get('assigned_object'):
                    iface_id = ip['assigned_object'].get('id')
                    if iface_id:
                        iface_to_ips[iface_id].append({'is_private': is_private, 'address': ip_str, 'is_mismatched': is_mismatched})
            
            # Group by device
            dev_iface_map = defaultdict(list)
            for iface in dev_interfaces:
                if iface.get('device'):
                    dev_iface_map[iface['device']['id']].append(iface)
                    
            for d in devices:
                did = d['id']
                ifaces = dev_iface_map.get(did, [])
                if not ifaces:
                    continue
                pub_count = 0
                priv_count = 0
                missing_count = 0
                mismatch_count = 0
                for iface in ifaces:
                    assigned = iface_to_ips.get(iface['id'], [])
                    if not assigned:
                        missing_count += 1
                    else:
                        for a in assigned:
                            if a['is_private']:
                                priv_count += 1
                            else:
                                pub_count += 1
                            if a['is_mismatched']:
                                mismatch_count += 1
                if missing_count > 0 or mismatch_count > 0:
                    ip_audit_report.append({
                        "id": did,
                        "name": d['name'],
                        "url": d['url'],
                        "type": "device",
                        "public_ips": pub_count,
                        "private_ips": priv_count,
                        "missing_ips": missing_count,
                        "mismatched_tenant_ips": mismatch_count
                    })
                    
            # Group by VM
            vm_iface_map = defaultdict(list)
            for iface in vm_interfaces:
                if iface.get('virtual_machine'):
                    vm_iface_map[iface['virtual_machine']['id']].append(iface)
                    
            for v in vms:
                vid = v['id']
                ifaces = vm_iface_map.get(vid, [])
                if not ifaces:
                    continue
                pub_count = 0
                priv_count = 0
                missing_count = 0
                mismatch_count = 0
                for iface in ifaces:
                    assigned = iface_to_ips.get(iface['id'], [])
                    if not assigned:
                        missing_count += 1
                    else:
                        for a in assigned:
                            if a['is_private']:
                                priv_count += 1
                            else:
                                pub_count += 1
                            if a['is_mismatched']:
                                mismatch_count += 1
                if missing_count > 0 or mismatch_count > 0:
                    ip_audit_report.append({
                        "id": vid,
                        "name": v['name'],
                        "url": v['url'],
                        "type": "vm",
                        "public_ips": pub_count,
                        "private_ips": priv_count,
                        "missing_ips": missing_count,
                        "mismatched_tenant_ips": mismatch_count
                    })
        
        missing_slid = []
        missing_gnid = []
        missing_cmd_address = []
        missing_gnid_address = []
        mismatched_cmd_tenant = []
        mismatched_gnid_tenant = []
        
        def check_cmd_address(item_id, item_name, item_url, item_type, cf):
            slid = cf.get('cmd_slid')
            if not slid:
                missing_slid.append({"id": item_id, "name": item_name, "url": item_url, "type": item_type})
            else:
                try:
                    segment = slid.split('-')[1] if '-' in slid else slid
                    segment_id = int(segment)
                    res = get_segment_a_site(segment_id)
                    if res and res.get("success"):
                        data = res.get("segment_data", {})
                        if not data.get("a_address"):
                            missing_cmd_address.append({"id": item_id, "name": item_name, "url": item_url, "type": item_type, "segment": segment_id})
                            
                        # Check for tenant mismatch on Segment
                        client_data = data.get("client", {})
                        if client_data:
                            network_code = client_data.get("network_code", "")
                            if network_code and network_code.lower() != tenant.lower():
                                mismatched_cmd_tenant.append({
                                    "id": item_id, 
                                    "name": item_name, 
                                    "url": item_url, 
                                    "type": item_type, 
                                    "segment": segment_id, 
                                    "network_code": network_code
                                })
                    else:
                        logger.warning(f"Failed to fetch CMC data for segment {segment_id}")
                except Exception as e:
                    logger.warning(f"Error checking segment for {item_name}: {e}")
                    
            gnid = cf.get('cmd_gnid')
            if not gnid:
                missing_gnid.append({"id": item_id, "name": item_name, "url": item_url, "type": item_type})
            else:
                try:
                    gnid_id = int(gnid)
                    res = get_gnid_a_site(gnid_id)
                    if res and res.get("success"):
                        data = res.get("site_data", {})
                        
                        # Check for missing address
                        if not data.get("address1"):
                            missing_gnid_address.append({"id": item_id, "name": item_name, "url": item_url, "type": item_type, "gnid": gnid_id})
                            
                        # Check for tenant mismatch
                        client_data = data.get("client", {})
                        if client_data:
                            network_code = client_data.get("network_code", "")
                            if network_code and network_code.lower() != tenant.lower():
                                mismatched_gnid_tenant.append({
                                    "id": item_id, 
                                    "name": item_name, 
                                    "url": item_url, 
                                    "type": item_type, 
                                    "gnid": gnid_id, 
                                    "network_code": network_code
                                })
                    else:
                        logger.warning(f"Failed to fetch CMC data for GNID {gnid_id}")
                except Exception as e:
                    logger.warning(f"Error checking GNID for {item_name}: {e}")

        for d in devices:
            dev_id = d.get('id')
            cf = d.get('custom_fields') or {}
            check_cmd_address(dev_id, d.get('name'), d.get('url'), "device", cf)
                
        for v in vms:
            vm_id = v.get('id')
            cf = v.get('custom_fields') or {}
            check_cmd_address(vm_id, v.get('name'), v.get('url'), "vm", cf)
        
        return {
            "missing_slid": missing_slid,
            "missing_gnid": missing_gnid,
            "missing_cmd_address": missing_cmd_address,
            "missing_gnid_address": missing_gnid_address,
            "mismatched_cmd_tenant": mismatched_cmd_tenant,
            "mismatched_gnid_tenant": mismatched_gnid_tenant,
            "ip_audit_report": ip_audit_report,
            "stats": {
                "total_devices": len(devices),
                "total_vms": len(vms)
            }
        }
