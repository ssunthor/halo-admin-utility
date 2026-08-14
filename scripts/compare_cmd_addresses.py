#!/usr/bin/env python3
import argparse
import sys
import os
import yaml

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
MODULE_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, '..'))
if MODULE_ROOT not in sys.path:
    sys.path.insert(0, MODULE_ROOT)

try:
    import bootstrap_helper
    bootstrap_helper.bootstrap_and_reexecute_if_needed()
except ImportError:
    pass

from core.connectors.cmc_connector import init_cmc_connector, get_segment_a_site, get_gnid_a_site
from core.clients.netbox_client import NetboxClient

def main():
    parser = argparse.ArgumentParser(description="Compare CMD addresses between GNID and Segment for all devices in a Netbox tenant.")
    parser.add_argument("--tenant", type=str, required=True, help="Tenant slug in Netbox (e.g., statrb)")
    args = parser.parse_args()
    
    config_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'config', 'settings.yaml'))
    if not os.path.exists(config_path):
        print(f"Config not found at {config_path}")
        sys.exit(1)
        
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
        
    print("Initializing Connectors...")
    init_cmc_connector(config)
    
    netbox_config = config.get('external_services', {}).get('netbox', {})
    nb_url = netbox_config.get('url', '')
    nb_token = netbox_config.get('token', '')
    verify_ssl = netbox_config.get('verify_ssl', False)
    
    if not nb_url or not nb_token:
        print("Netbox URL or token not configured in settings.yaml")
        sys.exit(1)
        
    nb_client = NetboxClient(url=nb_url, token=nb_token, verify_ssl=verify_ssl)
    
    print(f"Fetching devices for tenant: {args.tenant}...")
    devices = nb_client.get_devices(tenant=args.tenant)
    print(f"Total devices found: {len(devices)}")
    
    devices_to_check = []
    for d in devices:
        cf = d.get('custom_fields') or {}
        slid = cf.get('cmd_slid')
        gnid = cf.get('cmd_gnid')
        
        if slid and gnid:
            try:
                segment_id = int(slid.split('-')[1] if '-' in slid else slid)
                gnid_id = int(gnid)
                devices_to_check.append({
                    "name": d.get('name'),
                    "segment": segment_id,
                    "gnid": gnid_id
                })
            except ValueError:
                pass
                
    print(f"Devices with BOTH cmd_slid and cmd_gnid: {len(devices_to_check)}")
    
    if not devices_to_check:
        print("Nothing to compare!")
        return

    mismatch_count = 0
    match_count = 0
    error_count = 0
    
    for item in devices_to_check:
        print(f"\n--- Checking Device: {item['name']} (Seg: {item['segment']}, GNID: {item['gnid']}) ---")
        gnid_res = get_gnid_a_site(item['gnid'])
        seg_res = get_segment_a_site(item['segment'])
        
        if not gnid_res or not gnid_res.get("success"):
            print(f"  [ERROR] Failed to fetch GNID A-Site.")
            error_count += 1
            continue
            
        if not seg_res or not seg_res.get("success"):
            print(f"  [ERROR] Failed to fetch Segment A-Site.")
            error_count += 1
            continue
            
        gnid_data = gnid_res.get("site_data", {})
        seg_data = seg_res.get("segment_data", {})
        
        gnid_addr = gnid_data.get("address1")
        gnid_city = gnid_data.get("city")
        gnid_state = gnid_data.get("state")
        gnid_zip = gnid_data.get("postal_code")
        
        seg_addr = seg_data.get("a_address")
        seg_city = seg_data.get("a_city")
        seg_state = seg_data.get("a_state")
        seg_zip = seg_data.get("a_postal_code")
        
        match = True
        
        def check_match(name, val1, val2):
            nonlocal match
            if val1 != val2:
                print(f"  ❌ {name} Mismatch: GNID='{val1}' | Segment='{val2}'")
                match = False
                
        check_match("Address", gnid_addr, seg_addr)
        check_match("City", gnid_city, seg_city)
        check_match("State", gnid_state, seg_state)
        check_match("Postal Code", gnid_zip, seg_zip)
        
        if match:
            print("  ✅ All fields match perfectly.")
            match_count += 1
        else:
            mismatch_count += 1
            
    print("\n" + "="*40)
    print("=== FINAL REPORT ===")
    print(f"Matches:    {match_count}")
    print(f"Mismatches: {mismatch_count}")
    print(f"Errors:     {error_count}")
    print("="*40)

if __name__ == "__main__":
    main()
