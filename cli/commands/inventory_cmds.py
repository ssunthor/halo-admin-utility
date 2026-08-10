import click
import logging
import json
import sys
from cli.utils import print_grpc_json, handle_grpc_errors, get_hau_stub

logger = logging.getLogger(__name__)

@click.group(name='inventory', context_settings=dict(max_content_width=300, terminal_width=300))
def inventory_cli():
    """Commands for managing the HALO deployment inventory."""
    pass

@inventory_cli.command(name='sync')
@click.option('--grpc', 'as_grpc', is_flag=True, help="Output raw gRPC response as JSON")
@click.pass_context
@handle_grpc_errors
def sync_inventory(ctx, as_grpc):
    """Sync the HALO database with live cluster data."""
    import hau_pb2
    stub = get_hau_stub(ctx.obj['config'])
    if not stub:
        click.echo("[FATAL] Could not connect to gRPC server.")
        return
        
    click.echo("Syncing inventory via gRPC...")
    req = hau_pb2.InventorySyncRequest()
    resp = stub.InventorySync(req)
    
    if as_grpc:
        print_grpc_json(resp)
        return
        
    if resp.success:
        click.echo(f"✅ {resp.message}")
    else:
        click.echo(f"❌ Failed: {resp.message}")

@inventory_cli.command(name='list')
@click.option('--tenant', help='Filter by tenant slug name (e.g. halo-cid)')
@click.option('--grpc', 'as_grpc', is_flag=True, help="Output raw gRPC response as JSON")
@click.pass_context
@handle_grpc_errors
def list_inventory(ctx, tenant, as_grpc):
    """List the current HALO inventory."""
    import hau_pb2
    stub = get_hau_stub(ctx.obj['config'])
    if not stub:
        click.echo("[FATAL] Could not connect to gRPC server.")
        return
        
    req = hau_pb2.InventoryListRequest(tenant_slug=tenant or "")
    resp = stub.InventoryList(req)
    
    if as_grpc:
        print_grpc_json(resp)
        return
        
    if resp.success:
        data = json.loads(resp.result_json)
        click.secho("\n=== HALO ECOSYSTEM COMPUTATIONAL TOPOLOGY (DATABASE) ===", bold=True)
        for slug, clusters in data.items():
            click.secho(f"\n[NAMESPACE: {slug.upper()}]", fg='cyan', bold=True)
            if not clusters:
                click.secho("  (No clusters discovered)", fg='yellow')
                continue
                
            for location, details in clusters.items():
                tier = details.get('tenant_tier', 'UNKNOWN')
                category = details.get('tenant_category', 'CUSTOMER')
                url = details.get('url')
                url_str = f" [{url}]" if url else ""
                click.secho(f"\n  ► CLUSTER: {location.upper()} [{tier.upper()}] [{category}]{url_str}", fg='blue', bold=True)
                
                resources = details.get('resources', {})
                for kind, items in resources.items():
                    click.secho(f"      {kind}:", fg='white')
                    for item in items:
                        name = item.pop("name", "Unknown")
                        ns = slug
                        item.pop("cluster", None)
                        details_str = ", ".join(f"{k}={v}" for k, v in item.items())
                        click.secho(f"        - [{ns}] {name} ({details_str})")
        click.secho("\n" + "="*80 + "\n")
    else:
        click.echo(f"❌ Failed: {resp.message}")
        sys.exit(1)

@inventory_cli.command(name='update-customization')
@click.argument('tenant_slug')
@click.option('--category', help='Tenant category (e.g. INTERNAL, CUSTOMER)')
@click.option('--tier', help='Tenant tier (e.g. SANDBOX, PRODUCTION)')
@click.option('--policy', help='Update policy (e.g. MANUAL_ONLY)')
@click.option('--owner', help='Owner of the tenant')
@click.option('--purpose', help='Purpose of the tenant')
@click.option('--maintenance-window', help='Maintenance window')
@click.option('--config-payload', help='JSON string for configuration payload')
@click.pass_context
@handle_grpc_errors
def update_customization(ctx, tenant_slug, category, tier, policy, owner, purpose, maintenance_window, config_payload):
    """Manually update a tenant's customization fields."""
    import hau_pb2
    stub = get_hau_stub(ctx.obj['config'])
    if not stub:
        click.echo("[FATAL] Could not connect to gRPC server.")
        return
        
    req = hau_pb2.UpdateTenantCustomizationRequest(
        tenant_slug=tenant_slug,
        tenant_category=category or "",
        tenant_tier=tier or "",
        update_policy=policy or "",
        owner=owner or "",
        purpose=purpose or "",
        maintenance_window=maintenance_window or "",
        configuration_payload=config_payload or ""
    )
    resp = stub.UpdateTenantCustomization(req)
    
    if resp.success:
        click.echo(f"✅ {resp.message}")
    else:
        click.echo(f"❌ Failed: {resp.message}")
