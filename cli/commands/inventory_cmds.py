import click
import logging
import json
import sys
from cli.utils import print_grpc_json, handle_grpc_errors, get_hau_stub

logger = logging.getLogger(__name__)

@click.group(name='inventory')
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
        for location, tenants in data.items():
            click.secho(f"\n[{location.upper()} CLUSTER]", fg='cyan', bold=True)
            if not tenants:
                click.secho("  (No HALO tenants discovered)", fg='yellow')
                continue
                
            for slug, details in tenants.items():
                env = details.get('environment', 'unknown')
                internal = "INTERNAL" if details.get('is_internal') else "EXTERNAL"
                url = details.get('url')
                url_str = f" [{url}]" if url else ""
                click.secho(f"\n  ► TENANT: {slug} [{env.upper()}] [{internal}]{url_str}", fg='blue', bold=True)
                
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
