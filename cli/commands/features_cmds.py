import click
import json
import logging

logger = logging.getLogger(__name__)

@click.group(name="features")
def features_cmds():
    """Manage Feature Catalog via gRPC"""
    pass

@features_cmds.command(name="list")
@click.option("--grpc", "as_grpc", is_flag=True, help="Output raw gRPC response as JSON")
@click.pass_context
def list_features(ctx, as_grpc):
    """List all features in the catalog"""
    import hau_pb2
    stub = ctx.obj.get('stub')
    if not stub:
        click.secho("gRPC stub not initialized.", fg="red")
        return

    req = hau_pb2.ListFeaturesRequest()
    try:
        resp = stub.ListFeatures(req)
        
        if as_grpc:
            from cli.utils import print_grpc_json
            print_grpc_json(resp)
            return

        if not resp.success:
            click.secho(f"Failed to list features: {resp.message}", fg="red")
            return
        
        if not resp.features:
            click.secho("No features found in the catalog.", fg="yellow")
            return

        click.echo(f"{'Product Category':<40} | {'UI Grouping':<20} | {'Feature Name':<30} | {'Env Variable':<30} | {'Paid':<5} | {'Default':<7}")
        click.echo("-" * 145)
        for f in resp.features:
            paid = "Yes" if f.is_paid_addon else "No"
            default = "Yes" if f.enabled_by_default else "No"
            click.echo(f"{f.product_category:<40} | {f.ui_grouping:<20} | {f.feature_name:<30} | {f.env_variable:<30} | {paid:<5} | {default:<7}")
            
    except Exception as e:
        click.secho(f"Error communicating with HAU service: {e}", fg="red")

@features_cmds.command(name="upsert")
@click.option('--name', required=True, help="Friendly name for the feature")
@click.option('--env-var', required=True, help="Environment variable (e.g. VITE_SHOW_NETFLOW_DNA)")
@click.option('--category', required=True, help="Product category (e.g. Defense Halo Detect Service)")
@click.option('--grouping', required=True, help="UI grouping (e.g. Network Analytics)")
@click.option('--desc', default="", help="Description")
@click.option('--deps-json', default="{}", help="GitOps dependencies JSON")
@click.option('--pricing-json', default="{}", help="Pricing tiers JSON")
@click.option('--is-paid', is_flag=True, help="Mark as paid add-on")
@click.option('--is-default', is_flag=True, help="Enabled by default")
@click.pass_context
def upsert_feature(ctx, name, env_var, category, grouping, desc, deps_json, pricing_json, is_paid, is_default):
    """Upsert a feature entry"""
    import hau_pb2
    stub = ctx.obj.get('stub')
    if not stub:
        click.secho("gRPC stub not initialized.", fg="red")
        return
        
    try:
        json.loads(deps_json) # Validate JSON before sending
    except json.JSONDecodeError as e:
        click.secho(f"Invalid JSON for --deps-json: {e}", fg="red")
        return

    try:
        json.loads(pricing_json) # Validate JSON before sending
    except json.JSONDecodeError as e:
        click.secho(f"Invalid JSON for --pricing-json: {e}", fg="red")
        return

    req = hau_pb2.UpsertFeatureRequest(
        feature_name=name,
        env_variable=env_var,
        product_category=category,
        ui_grouping=grouping,
        description=desc,
        gitops_dependencies_json=deps_json,
        pricing_tiers_json=pricing_json,
        is_paid_addon=is_paid,
        enabled_by_default=is_default
    )
    
    try:
        resp = stub.UpsertFeature(req)
        if not resp.success:
            click.secho(f"Failed to upsert feature: {resp.message}", fg="red")
        else:
            click.secho(f"Successfully upserted feature: {resp.feature.feature_name}", fg="green")
    except Exception as e:
        click.secho(f"Error communicating with HAU service: {e}", fg="red")
