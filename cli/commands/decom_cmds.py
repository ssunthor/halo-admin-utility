import click
from cli.utils import handle_grpc_errors, get_hau_stub

@click.group(name='decom')
def decom_cli():
    """Decommission related commands."""
    pass

@decom_cli.command(name='tenant')
@click.option('--tenant', required=True, help="Tenant acronym (e.g. gtt)")
@click.option('--env', required=False, help="Environment (e.g. test, prod)")
@click.option('--region', required=True, help="Deployment region (e.g. slo)")
@handle_grpc_errors
@click.pass_context
def decom_tenant(ctx, tenant, env, region):
    """Decommissions a tenant and cleans up its GitOps files and CMU resources."""
    import hau_pb2
    stub = get_hau_stub(ctx.obj['config'])
    
    tenant_acronym = f"{tenant}-{env}" if env else tenant
    click.echo(f"Initiating decommission for {tenant_acronym} in {region}...")
    req = hau_pb2.DecommissionTenantRequest(
        tenant=tenant,
        env=env if env else "",
        region=region
    )
    
    responses = stub.DecommissionTenant(req)
    
    final_success = False
    final_msg = ""
    for res in responses:
        if "Successfully decommissioned" in res.message:
            final_success = res.success
            final_msg = res.message
        elif not res.success:
            click.secho(f"❌ Error: {res.message}", fg="red")
            return
        else:
            click.secho(f"--> {res.message}", fg="cyan")
            
    if final_success:
        click.secho(f"✅ {final_msg}", fg="green")
    else:
        click.secho("❌ Decommission completed but final success message not found.", fg="red")
