from cli.utils import print_grpc_json, handle_grpc_errors
import click
import json

@click.group(name="module")
def module_cli():
    """Module-specific commands (Info, Health)"""
    pass

@module_cli.command(name="info")
@click.option('--grpc', 'as_grpc', is_flag=True, help="Output raw gRPC response")
@handle_grpc_errors
@click.pass_context
def get_info(ctx, as_grpc):
    """Retrieves App Info via the SERA Standard gRPC"""
    config = ctx.obj.get('config')
    try:
        from google.protobuf.empty_pb2 import Empty
        stub = ctx.obj.get('sera_stub')
        response = stub.GetAppInfo(Empty())
        
        if as_grpc:
            print_grpc_json(response)
            return
            
        click.secho(f"=== {response.acronym} Info ===", fg="cyan", bold=True)
        click.echo(f"Name/Desc: {response.description}")
        click.echo(f"Version:   {response.version}")
        click.echo(f"Category:  {response.category}")
        click.echo(f"Dependencies: {', '.join(response.downstream_dependencies)}")
    except Exception as e:
        click.secho(f"Failed to get info: {e}", fg="red")

@module_cli.command(name="check-health")
@click.option('--grpc', 'as_grpc', is_flag=True, help="Output raw gRPC response")
@handle_grpc_errors
@click.pass_context
def check_health(ctx, as_grpc):
    """Retrieves Deep Health via the SERA Standard gRPC"""
    config = ctx.obj.get('config')
    try:
        from google.protobuf.empty_pb2 import Empty
        stub = ctx.obj.get('sera_stub')
        response = stub.GetDeepHealth(Empty())
        
        if as_grpc:
            print_grpc_json(response)
            return
        
        color = "green" if response.overall_status == "HEALTHY" else "red"
        click.secho(f"Overall Status: {response.overall_status}", fg=color, bold=True)
        
        for dep in response.dependency_health_matrix:
            dep_color = "green" if dep.status == "OK" else "yellow"
            click.echo(f" - {dep.dependency_name}: ", nl=False)
            click.secho(f"{dep.status}", fg=dep_color, nl=False)
            click.echo(f" ({dep.details})")
    except Exception as e:
        click.secho(f"Failed to get deep health: {e}", fg="red")
