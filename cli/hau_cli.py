import click
import logging
import sys
import os
import subprocess

from utils.logging_setup import setup_logging

logger = logging.getLogger(__name__)

class NestedHelpGroup(click.Group):
    def format_commands(self, ctx, formatter):
        rows = []
        for subcommand in self.list_commands(ctx):
            cmd = self.get_command(ctx, subcommand)
            if cmd is None or getattr(cmd, 'hidden', False):
                continue
            
            help_str = cmd.get_short_help_str(limit=formatter.width) if hasattr(cmd, 'get_short_help_str') else ""
            rows.append((subcommand, help_str))
            
            if isinstance(cmd, click.Group):
                for sub_name in cmd.list_commands(ctx):
                    sub_cmd = cmd.get_command(ctx, sub_name)
                    if sub_cmd is None or getattr(sub_cmd, 'hidden', False):
                        continue
                    
                    sub_help_str = sub_cmd.get_short_help_str(limit=formatter.width) if hasattr(sub_cmd, 'get_short_help_str') else ""
                    rows.append((f"  {subcommand} {sub_name}", sub_help_str))
        
        if rows:
            with formatter.section('Commands'):
                formatter.write_dl(rows)

@click.group(cls=NestedHelpGroup, context_settings=dict(max_content_width=300, terminal_width=300))
@click.pass_context
def cli(ctx):
    """HAU CLI"""
    if ctx.obj is None:
        ctx.obj = {}
    config = ctx.obj.get('config')
    if config:
        from cli.utils import ensure_stubs_path_in_sys
        ensure_stubs_path_in_sys(config)

        try:
            from cli.utils import get_hau_stub, get_sera_stub
            ctx.obj['stub'] = get_hau_stub(config)
            ctx.obj['sera_stub'] = get_sera_stub(config)
        except Exception as e:
            logger.debug(f"Failed to initialize stubs during CLI startup: {e}")

@cli.command(name="start-grpc-server")
@click.pass_context
def start_grpc_server(ctx: click.Context):
    config = ctx.obj.get('config')
    if not config:
        logger.error("Config not found in context.")
        sys.exit(1)

    from cli.utils import ensure_stubs_path_in_sys
    ensure_stubs_path_in_sys(config)

    logger.info("CLI: Request to start the HAU gRPC server.")

    from grpc_api.generate_stubs import check_and_generate_stubs
    success, regenerated = check_and_generate_stubs(config)
    if not success:
        logger.critical("Aborting server start due to stub generation failure.")
        sys.exit(1)
        
    if regenerated:
        logger.info("Stubs were regenerated. Restarting Python process to load new stubs...")
        os.execv(sys.executable, [sys.executable, "-u"] + sys.argv)
        
    import importlib
    importlib.invalidate_caches()


    from core.database.database import get_engine, init_db
    try:
        engine = get_engine(config['database']['write_dsn'])
        init_db(engine)
        logger.info("Database tables initialized successfully.")
    except Exception as e:
        logger.critical(f"Failed to initialize database: {e}")
        sys.exit(1)

    from grpc_api.services import serve as run_grpc_server
    run_grpc_server(config)

@cli.command(name="init-db")
@click.option('--force', is_flag=True, help="Force wipe and recreate the database.")
@click.pass_context
def init_db_cmd(ctx, force):
    config = ctx.obj.get('config')
    if not config:
        click.secho("Config not found in context.", fg="red")
        sys.exit(1)
    
    from core.database.database import get_engine, init_db, reset_db
    try:
        engine = get_engine(config['database']['write_dsn'])
        if force:
            click.secho("Wiping and recreating all database tables...", fg="yellow")
            reset_db(engine)
            click.secho("✅ Database reset complete.", fg="green")
        else:
            click.secho("Initializing database tables (if they do not exist)...", fg="cyan")
            init_db(engine)
            click.secho("✅ Database initialization complete. (Use --force to wipe and reset)", fg="green")
    except Exception as e:
        click.secho(f"Failed to initialize database: {e}", fg="red")
        sys.exit(1)

from cli.commands.module_cmds import module_cli
from cli.commands.git_cmds import git_cli
from cli.commands.inventory_cmds import inventory_cli
from cli.commands.changelog_cmds import changelog_cmds
from cli.commands.features_cmds import features_cmds
from cli.commands.netbox_cmds import netbox_cli

cli.add_command(start_grpc_server)
cli.add_command(init_db_cmd)
cli.add_command(module_cli)
cli.add_command(git_cli)
cli.add_command(inventory_cli)
cli.add_command(changelog_cmds)
cli.add_command(features_cmds)
cli.add_command(netbox_cli)
