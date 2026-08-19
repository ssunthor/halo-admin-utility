import click
from cli.utils import handle_grpc_errors, get_hau_stub

@click.group(name='deploy', context_settings=dict(max_content_width=300, terminal_width=300))
def deploy_cli():
    """Tenant deployment and GitOps scaffolding operations."""
    pass

@deploy_cli.command(name='scaffold')
@click.option('--tenant', required=True, help="Tenant acronym (e.g. gtt3d0)")
@click.option('--region', required=True, help="Deployment region (e.g. slo)")
@click.option('--component', multiple=True, help="Component and image tag selection in format component:tag (e.g. backend:feat-fortinet).")
@click.option('--internal', is_flag=True, help="Flag this deployment as an internal tenant")
@click.option('--netbox-slug', default="", help="Optional specific Netbox tenant slug/ID to map to (defaults to gtt-corp for internals, or tenant acronym for customers)")
@handle_grpc_errors
@click.pass_context
def deploy_scaffold(ctx, tenant, region, component, internal, netbox_slug):
    """Scaffolds a new tenant using GitOps automation and synchronously generates CMU secrets."""
    import hau_pb2
    stub = get_hau_stub(ctx.obj['config'])
    
    image_selections = {}
    for comp in component:
        if ':' in comp:
            name, tag = comp.split(':', 1)
            image_selections[name] = tag
        else:
            click.secho(f"❌ Invalid component format '{comp}'. Must be component:tag", fg="red")
            return
            
    req = hau_pb2.DeployTenantScaffoldRequest(
        tenant_acronym=tenant,
        region=region,
        target_cluster="",
        image_selections=image_selections,
        variables={},
        is_internal=internal,
        netbox_slug=netbox_slug
    )
    
    click.echo(f"Initiating GitOps scaffold for {tenant} in {region}...")
    responses = stub.DeployTenantScaffold(req)
    
    final_success = False
    final_msg = ""
    for resp in responses:
        if "Successfully scaffolded" in resp.message:
            final_success = resp.success
            final_msg = resp.message
        elif not resp.success:
            click.secho(f"❌ Error: {resp.message}", fg="red")
            return
        else:
            click.secho(f"--> {resp.message}", fg="cyan")
            
    if final_success:
        click.secho(f"✅ Scaffold Success:\n{final_msg}", fg="green")
    else:
        click.secho("❌ Scaffold completed but final success message not found.", fg="red")
