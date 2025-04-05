from fabric import Connection
from typing import Optional, Tuple
import sys
import argparse
from urllib.parse import urlparse
from mcp.server import FastMCP

mcp = FastMCP("ssh-server")

@mcp.tool("ssh_remote_command", description="Execute remote command via SSH")
def execute(host: str, user: str, command: str, key_path: str) -> (bool, str):
    """
    Execute a command on a remote server via SSH.

    Args:
        host (str): The hostname or IP address of the remote server.
        user (str): The username to use for SSH authentication.
        command (str): The command to execute on the remote server.
        key_path (Optional[str]): The path to the private key file for SSH authentication.

    Returns:
        ToolResult: The result of the command execution.
    """
    try:
        conn = Connection(
            host=args["host"],
            user=args["user"],
            connect_kwargs={"key_filename": key_path}
        )
        result = conn.run(args["command"], hide=True)
        return (
            True,
            f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )
    except Exception as e:
        return (
            False,
            f"Connection failed: {str(e)}"
        )

if __name__ == "__main__":
    if len(sys.argv) > 1:
        # Parse command line arguments
        parser = argparse.ArgumentParser(description='Execute remote command via SSH')
        parser.add_argument('url', help='SSH URL in format ssh://user@host')
        parser.add_argument('command', help='Command to execute on remote host')
        parser.add_argument('--key', help='Path to private key file')
        parser.add_argument('--port', type=int, default=22, help='SSH port (default: 22)')
        args = parser.parse_args()

        # Parse SSH URL
        parsed_url = urlparse(args.url)
        if parsed_url.scheme != 'ssh':
            print("Error: Invalid URL scheme - must be 'ssh://'", file=sys.stderr)
            sys.exit(1)

        user = parsed_url.username
        host = parsed_url.hostname
        if not user or not host:
            print("Error: URL must include username and hostname", file=sys.stderr)
            sys.exit(1)

        # Prepare parameters dictionary matching ToolSchema
        params = {
            'host': host,
            'user': user,
            'command': args.command,
            'private_key': args.key,
            'port': args.port
        }

        # Execute command and print results
        try:
            result = execute(host, user, args.command, args.key)
            print(result)
        except Exception as e:
            print(f"Error executing command: {str(e)}", file=sys.stderr)
            sys.exit(1)
    else:
        # Start MCP server if no arguments provided
        mcp.run(transport="stdio")

