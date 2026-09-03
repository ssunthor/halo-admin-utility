import click
import logging
import sys
from cli.utils import print_grpc_json, handle_grpc_errors, get_hau_stub
from google.protobuf.json_format import MessageToDict

logger = logging.getLogger(__name__)

@click.group(name='tenant', context_settings=dict(max_content_width=300, terminal_width=300))
def tenant_cli():
    """Commands for managing HALO tenants."""
    pass

@tenant_cli.command(name='list')
@click.option('--tenant', help='Filter by tenant acronym (e.g. gtt)')
@click.option('--env', help='Filter by environment (e.g. test)')
@click.option('--namespace', help='Filter by exact namespace (e.g. halo-gtt-test)')
@click.option('--grpc', 'as_grpc', is_flag=True, help="Output raw gRPC response as JSON")
@click.pass_context
@handle_grpc_errors
def list_tenants(ctx, tenant, env, namespace, as_grpc):
    """List detailed database information for tenants."""
    import hau_pb2
    stub = get_hau_stub(ctx.obj['config'])
    if not stub:
        click.echo("[FATAL] Could not connect to gRPC server.")
        return
        
    req = hau_pb2.TenantListRequest(
        tenant=tenant or "",
        env=env or "",
        tenant_namespace=namespace or ""
    )
    resp = stub.TenantList(req)
    
    if as_grpc:
        print_grpc_json(resp)
        return
        
    if resp.success:
        click.secho("\n=== HALO TENANTS (DATABASE) ===", bold=True)
        for t in resp.tenants:
            click.secho(f"\n[NAMESPACE: {t.tenant_namespace.upper()}]", fg='cyan', bold=True)
            click.echo(f"  ID: {t.id}")
            click.echo(f"  Name: {t.tenant_name}")
            click.echo(f"  Acronym: {t.tenant_acronym}")
            click.echo(f"  Environment: {t.tenant_environment}")
            click.echo(f"  Group: {t.tenant_group}")
            click.echo(f"  Target Cluster: {t.target_cluster}")
            click.echo(f"  CMD Tenant ID: {t.cmd_tenant_id}")
            click.echo(f"  CMD Group ID: {t.cmd_group_id}")
            click.echo(f"  NetBox ID: {t.netbox_id}")
            click.echo(f"  NetBox Slug: {t.netbox_slug}")
            click.echo(f"  Halo Version: {t.halo_version}")
            click.echo(f"  Lifecycle State: {t.lifecycle_state}")
            click.echo(f"  Created At: {t.created_at}")
            click.echo(f"  Updated At: {t.updated_at}")
            click.echo(f"  URL: {t.url}")
            click.secho(f"  --- Customization ---", fg='blue')
            click.echo(f"  Category: {t.tenant_category}")
            click.echo(f"  Tier: {t.tenant_tier}")
            click.echo(f"  Update Policy: {t.update_policy}")
            click.echo(f"  Owner: {t.owner}")
            click.echo(f"  Purpose: {t.purpose}")
            click.echo(f"  Maintenance Window: {t.maintenance_window}")
        click.secho("\n" + "="*40 + "\n")
        click.echo(f"{resp.message}")
    else:
        click.echo(f"❌ Failed: {resp.message}")
        sys.exit(1)
