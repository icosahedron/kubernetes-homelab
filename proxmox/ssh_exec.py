"""
SSH client utility using Paramiko for secure remote command execution
"""
import sys
import paramiko
import os
import argparse
from urllib.parse import urlparse # Add urlparse import
from paramiko import SSHClient, AutoAddPolicy, AuthenticationException, SSHException
from typing import Tuple, Optional


class SSHClientManager:
    def __init__(self, hostname: str, username: str, password: Optional[str] = None, key_path: Optional[str] = None, port: int = 22):
        self.hostname = hostname
        self.username = username
        self.password = password
        self.key_path = key_path
        self.port = port
        self.client = None

    def connect(self) -> Tuple[bool, str]:
        try:
            self.client = paramiko.SSHClient()
            self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

            if self.key_path:
                private_key = paramiko.RSAKey.from_private_key_file(self.key_path)
                self.client.connect(self.hostname, port=self.port, username=self.username, pkey=private_key)
            else:
                self.client.connect(self.hostname, port=self.port, username=self.username, password=self.password)

            return True, "Connected successfully"
        except (paramiko.SSHException, socket.error) as e:
            return False, str(e)

    def execute(self, command: str) -> Tuple[int, str, str]:
        if not self.client:
            raise Exception("SSH client not connected")

        stdin, stdout, stderr = self.client.exec_command(command)
        exit_status = stdout.channel.recv_exit_status()
        return exit_status, stdout.read().decode(), stderr.read().decode()

    def copy_file(self, local_path: str, remote_path: str) -> Tuple[bool, str]:
        if not self.client:
            raise Exception("SSH client not connected")

        try:
            sftp = self.client.open_sftp()
            sftp.put(local_path, remote_path)
            sftp.close()
            return True, f"Successfully copied {local_path} to {remote_path}"
        except Exception as e:
            return False, str(e)

    def close(self):
        if self.client:
            self.client.close()
            self.client = None

def ssh_connect(hostname: str, username: str, password: Optional[str] = None, key_path: Optional[str] = None, port: int = 22) -> Tuple[bool, Optional[SSHClientManager], str]:
    ssh_manager = SSHClientManager(hostname, username, password, key_path, port)
    success, message = ssh_manager.connect()
    if success:
        return True, ssh_manager, message
    else:
        return False, None, message

def ssh_execute(ssh_manager: SSHClientManager, command: str) -> Tuple[bool, Tuple[int, str], str]:
    try:
        exit_status, output, error = ssh_manager.execute(command)
        return True, (exit_status, output), error
    except Exception as e:
        return False, (1, ""), str(e)

def ssh_copy_file(ssh_manager: SSHClientManager, local_path: str, remote_path: str) -> Tuple[bool, str]:
    try:
        success, message = ssh_manager.copy_file(local_path, remote_path)
        return success, message
    except Exception as e:
        return False, str(e)

def ssh_disconnect(ssh_manager: SSHClientManager):
    ssh_manager.close()

def ssh_remote_command(host: str, user: str, command: str, key_path: str = None) -> Tuple[bool, str]:
    try:  
        # Establish connection using utility functions
        conn_success, client, conn_msg = ssh_connect(
            host=hostname,
            username=username,
            password=args.password,
            key_path=args.key_path
        )

        if not conn_success:
            return (False, conn_msg)

        # Execute command using utility function
        exec_success, (status, output), exec_msg = ssh_execute(client, command)
        
        if exec_success:
            return (True, output)
        else:
            return (False, exec_msg)

    except ValueError as e:
        return (False, f"Argument Error: {str(e)}")
    except Exception as e:
        return (False, f"Unexpected Error: {str(e)}")
    finally:
        if client:
            disc_success, disc_msg = ssh_disconnect(client)
            if not disc_success:
                print(f"Disconnection Warning: {disc_msg}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        parser = argparse.ArgumentParser(
            description="Connect to an SSH server using an SSH URL and execute a command.",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
    Examples:
    python ssh.py ssh://admin@192.168.1.100:2222 "cat /etc/os-release" --key-path ~/.ssh/id_rsa_admin
    """
        )
        parser.add_argument("ssh_url", help="SSH connection URL (e.g., ssh://user@host:port)")
        parser.add_argument("command", help="Command to execute on the remote server")
        
        # Authentication group: Allow either password or key file, but not both.
        # This group is not required, allowing for SSH agent authentication.
        auth_group = parser.add_mutually_exclusive_group()
        auth_group.add_argument("--password", help="SSH password for authentication")
        auth_group.add_argument("--key-path", help="Path to SSH private key file for authentication")

        args = parser.parse_args()

        exit_code = 0
        client = None
        try:
            # Parse the SSH URL
            parsed_url = urlparse(args.ssh_url)

            if parsed_url.scheme != "ssh":
                raise ValueError("Invalid URL scheme. Must start with 'ssh://'")
            
            hostname = parsed_url.hostname
            port = parsed_url.port or 22
            username = parsed_url.username

            if not hostname:
                raise ValueError("Hostname missing in SSH URL")
            if not username:
                raise ValueError("Username missing in SSH URL")

            (success, output) = ssh_remote_command(hostname, username, args.command, args.key_path)
            if success:
                print(output)
            else:
                print(f"Command execution failed: {output}")
                exit_code = 1

        finally:
            exit(exit_code)
    else:
        # Start MCP server if no arguments provided
        mcp.run(transport="stdio")
