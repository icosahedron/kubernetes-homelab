import click
from .ssh_admin_server import SSHAdminServer

@click.group()
def cli():
    """SSH Admin MCP Client"""

@cli.command()
@click.option("--host", required=True)
@click.option("--auth-type", type=click.Choice(["key", "password"]), required=True)
@click.option("--auth-value", required=True)
def connect(host, auth_type, auth_value):
    """Establish SSH connection"""
    server = SSHAdminServer()
    session_id = server.connect(host, auth_type, auth_value)
    print(f"Session established: {session_id}")

@cli.command()
@click.option("--session-id", required=True)
@click.argument("command")
def execute(session_id, command):
    """Execute command on session"""
    server = SSHAdminServer()
    try:
        output = server.execute(session_id, command)
        print(output)
    except Exception as e:
        print(f"Error: {str(e)}")

if __name__ == "__main__":
    cli()