import click
import logging
import json
import sys
from cli.utils import print_grpc_json, handle_grpc_errors, get_hau_stub

logger = logging.getLogger(__name__)

@click.group(name='netbox', context_settings=dict(max_content_width=300, terminal_width=300))
def netbox_cli():
    """Commands for NetBox audits and syncs."""
    pass

@netbox_cli.command(name='audit-tenant')
@click.option('--tenant', help='Tenant acronym (e.g. gtt)')
@click.option('--env', help='Environment (e.g. test)')
@click.option('--namespace', help='Exact namespace (e.g. halo-gtt-test)')
@click.option('--grpc', 'as_grpc', is_flag=True, help="Output raw gRPC response as JSON")
@click.option('--ip-audit', is_flag=True, help="Perform a deep scan of all interfaces to find missing IPs.")
@click.pass_context
@handle_grpc_errors
def audit_tenant(ctx, tenant, env, namespace, as_grpc, ip_audit):
    """Audit a Netbox tenant for missing slids and IPs."""
    import hau_pb2
    stub = get_hau_stub(ctx.obj['config'])
    if not stub:
        click.echo("[FATAL] Could not connect to gRPC server.")
        return
        
    click.echo("Triggering Netbox audit via gRPC...")
    if ip_audit:
        click.echo("Running deep interface IP audit (this may take a bit longer)...")
    req = hau_pb2.NetboxAuditTenantRequest(
        tenant=tenant or "",
        env=env or "",
        tenant_namespace=namespace or "",
        ip_audit=ip_audit
    )
    resp = stub.NetboxAuditTenant(req)
    
    if as_grpc:
        print_grpc_json(resp)
        return
        
    if resp.success:
        data = json.loads(resp.result_json)
        
        missing_slid = data.get("missing_slid", [])
        missing_gnid = data.get("missing_gnid", [])
        missing_cmd_address = data.get("missing_cmd_address", [])
        mismatched_cmd_tenant = data.get("mismatched_cmd_tenant", [])
        missing_gnid_address = data.get("missing_gnid_address", [])
        mismatched_gnid_tenant = data.get("mismatched_gnid_tenant", [])
        ip_audit_report = data.get("ip_audit_report", [])
        stats = data.get("stats", {})
        
        def _get_counts_str(items):
            if not items:
                return ""
            devices = sum(1 for i in items if i.get('type') == 'device')
            vms = sum(1 for i in items if i.get('type') == 'vm')
            parts = []
            if devices > 0:
                parts.append(f"{devices} Device{'s' if devices != 1 else ''}")
            if vms > 0:
                parts.append(f"{vms} VM{'s' if vms != 1 else ''}")
            if not parts:
                return ""
            return f" [{', '.join(parts)}]"
            
        click.secho("\n=== NETBOX TENANT AUDIT ===", bold=True)
        click.echo(f"Devices checked: {stats.get('total_devices', 0)}")
        click.echo(f"VMs checked: {stats.get('total_vms', 0)}")
        click.echo(f"IPs loaded: {stats.get('total_ips', 0)}")
        
        click.secho(f"\n[MISSING CMD_SLID]{_get_counts_str(missing_slid)}", fg='red', bold=True)
        if not missing_slid:
            click.secho("  (None found - all good!)", fg='green')
        else:
            for item in missing_slid:
                click.echo(f"  - [{item['type'].upper()}] {item['name']} ({item['url']})")
                
        click.secho(f"\n[MISSING CMD_GNID]{_get_counts_str(missing_gnid)}", fg='red', bold=True)
        if not missing_gnid:
            click.secho("  (None found - all good!)", fg='green')
        else:
            for item in missing_gnid:
                click.echo(f"  - [{item['type'].upper()}] {item['name']} ({item['url']})")
                
        click.secho(f"\n[MISSING CMD ADDRESS (A-Site)]{_get_counts_str(missing_cmd_address)}", fg='bright_red', bold=True)
        if not missing_cmd_address:
            click.secho("  (None found - all good!)", fg='green')
        else:
            for item in missing_cmd_address:
                click.echo(f"  - [{item['type'].upper()}] {item['name']} ({item['url']}) -> Segment: {item.get('segment', 'Unknown')}")
                
        click.secho(f"\n[MISMATCHED CMD TENANT]{_get_counts_str(mismatched_cmd_tenant)}", fg='bright_red', bold=True)
        if not mismatched_cmd_tenant:
            click.secho("  (None found - all good!)", fg='green')
        else:
            for item in mismatched_cmd_tenant:
                click.echo(f"  - [{item['type'].upper()}] {item['name']} ({item['url']}) -> Segment: {item.get('segment', 'Unknown')} (CMD Network Code: '{item.get('network_code', 'Unknown')}')")
                
        click.secho(f"\n[MISSING GNID ADDRESS (A-Site)]{_get_counts_str(missing_gnid_address)}", fg='bright_red', bold=True)
        if not missing_gnid_address:
            click.secho("  (None found - all good!)", fg='green')
        else:
            for item in missing_gnid_address:
                click.echo(f"  - [{item['type'].upper()}] {item['name']} ({item['url']}) -> GNID: {item.get('gnid', 'Unknown')}")
                
        click.secho(f"\n[MISMATCHED GNID TENANT]{_get_counts_str(mismatched_gnid_tenant)}", fg='bright_red', bold=True)
        if not mismatched_gnid_tenant:
            click.secho("  (None found - all good!)", fg='green')
        else:
            for item in mismatched_gnid_tenant:
                click.echo(f"  - [{item['type'].upper()}] {item['name']} ({item['url']}) -> GNID: {item.get('gnid', 'Unknown')} (CMD Network Code: '{item.get('network_code', 'Unknown')}')")
                
        if ip_audit:
            click.secho(f"\n[IP AUDIT REPORT (Interfaces with Missing IPs)]{_get_counts_str(ip_audit_report)}", fg='yellow', bold=True)
            if not ip_audit_report:
                click.secho("  (None found - all good!)", fg='green')
            else:
                for item in ip_audit_report:
                    mismatch_str = ""
                    if item.get('mismatched_tenant_ips', 0) > 0:
                        mismatch_str = f", {item['mismatched_tenant_ips']} Mismatched Tenant IPs"
                    click.echo(f"  - [{item['type'].upper()}] {item['name']} ({item['url']}) -> {item['public_ips']} Public, {item['private_ips']} Private, {item['missing_ips']} Missing{mismatch_str}")
                    
        click.secho("\n" + "="*27 + "\n")
    else:
        click.echo(f"❌ Failed: {resp.message}")
        sys.exit(1)
