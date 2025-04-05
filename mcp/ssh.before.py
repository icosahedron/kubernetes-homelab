"""
SSH client utility using Paramiko for secure remote command execution
"""
import paramiko
import os
import argparse
from urllib.parse import urlparse # Add urlparse import
from paramiko import SSHClient, AutoAddPolicy, AuthenticationException, SSHException
from typing import Tuple

class SSHClientManager:
    """
    Context manager for SSH connections with automatic cleanup
    
    Example usage:
    with SSHClientManager('host', 'user', 'password') as client:
        status, output = client.execute_command('ls -la')
    """
    
    def __init__(self, host: str, username: str = None, password: str = None, key_path: str = None,
                port: int = 22, config_host: str = None):
        """Initialize SSH client with optional SSH config lookup
        
        Args:
            host: Server hostname or IP.
            username: Username for SSH login.
            password: Password for SSH login (alternative to key_path).
            key_path: Path to the private key file.
            port: SSH port number.
            config_host: Name of host entry in SSH config (~/.ssh/config) to load parameters from.
                         Parameters from config will override direct arguments if found.
        """
        self.client = SSHClient()
        self.client.set_missing_host_key_policy(AutoAddPolicy())
        
        # Initialize with direct arguments as defaults
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.key_path = key_path

        # Override with parameters from SSH config if config_host is specified
        if config_host:
            try:
                config = paramiko.SSHConfig()
                config_path = os.path.expanduser("~/.ssh/config")
                with open(config_path) as f:
                    config.parse(f)
                cfg = config.lookup(config_host)
                
                # Override parameters if they exist in the config
                self.host = cfg.get('hostname', self.host)
                self.username = cfg.get('user', self.username)
                self.port = int(cfg.get('port', self.port))
                # SSH config typically uses IdentityFile for key path
                # Use the first key file specified if multiple exist
                identity_files = cfg.get('identityfile')
                if identity_files:
                    self.key_path = os.path.expanduser(identity_files[0])
                # Password is generally not stored in ssh config for security reasons
                # If a key is found in config, prioritize it by nullifying password
                if self.key_path:
                    self.password = None
                    
            except FileNotFoundError:
                print(f"Warning: SSH config file not found at {config_path}. Using direct arguments.")
            except KeyError:
                 print(f"Warning: Host '{config_host}' not found in SSH config. Using direct arguments.")
            except Exception as e:
                print(f"Warning: Error reading SSH config file: {e}. Using direct arguments.")
            self.key_path = key_path

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def connect(self):
        """Establish SSH connection with authentication fallback"""
        try:
            if self.key_path:
                self.client.connect(self.host, 
                                  port=self.port,
                                  username=self.username,
                                  key_filename=self.key_path)
            elif self.password:
                self.client.connect(self.host,
                                  port=self.port,
                                  username=self.username,
                                  password=self.password)
            else:
                raise AuthenticationException("No authentication method provided")
        except (AuthenticationException, SSHException) as e:
            raise ConnectionError(f"SSH connection failed: {str(e)}") from e

    def execute_command(self, command: str) -> Tuple[int, str]:
        """Execute remote command and return (status_code, output)"""
        if not self.client.get_transport() or not self.client.get_transport().is_active():
            raise ConnectionError("SSH connection not established")

        try:
            _, stdout, stderr = self.client.exec_command(command)
            exit_code = stdout.channel.recv_exit_status()
            output = stdout.read().decode().strip() or stderr.read().decode().strip()
            return exit_code, output
        except SSHException as e:
            raise RuntimeError(f"Command execution failed: {str(e)}") from e

    def close(self):
        """Close SSH connection gracefully"""
        if self.client.get_transport() and self.client.get_transport().is_active():
            self.client.close()

def ssh_connect(host: str, username: str, password: str = None, key_path: str = None, port: int = 22) -> Tuple[bool, SSHClientManager, str]:
    """Establish SSH connection and return (success, client, message) tuple"""
    try:
        client = SSHClientManager(host, username, password, key_path, port)
        client.connect()
        return (True, client, "Connection successful")
    except Exception as e:
        return (False, None, str(e))

def ssh_execute(client: SSHClientManager, command: str) -> Tuple[bool, Tuple[int, str], str]:
    """Execute command on existing connection, return (success, (status, output), error)"""
    try:
        if not client.client.get_transport() or not client.client.get_transport().is_active():
            return (False, (-1, ""), "Connection not active")
        
        status, output = client.execute_command(command)
        return (True, (status, output), "")
    except Exception as e:
        return (False, (-1, ""), str(e))

def ssh_disconnect(client: SSHClientManager) -> Tuple[bool, str]:
    """Close SSH connection and return (success, message)"""
    try:
        client.close()
        return (True, "Disconnected successfully")
    except Exception as e:
        return (False, str(e))

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Connect to an SSH server using an SSH URL and execute a command.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python utils/ssh.py ssh://user@example.com "ls -l"
  python utils/ssh.py ssh://admin@192.168.1.100:2222 "cat /etc/os-release" --key-path ~/.ssh/id_rsa_admin
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

        # Establish connection using utility functions
        conn_success, client, conn_msg = ssh_connect(
            host=hostname,
            username=username,
            password=args.password,
            key_path=args.key_path,
            port=port
        )

        if not conn_success:
            print(f"Connection Failed: {conn_msg}")
            exit_code = 2
            exit(exit_code)

        print(f"Executing command: '{args.command}' on {username}@{hostname}:{port}...")
        
        # Execute command using utility function
        exec_success, (status, output), exec_msg = ssh_execute(client, args.command)
        
        if exec_success:
            print("\n--- Output ---")
            print(output)
            print("--------------")
            print(f"Exit Status: {status}")
            exit_code = 0 if status == 0 else 1
        else:
            print(f"Execution Failed: {exec_msg}")
            exit_code = 2

    except ValueError as e:
        print(f"Argument Error: {str(e)}")
        exit_code = 1
    except Exception as e:
        print(f"Unexpected Error: {str(e)}")
        exit_code = 4
    finally:
        if client:
            disc_success, disc_msg = ssh_disconnect(client)
            if not disc_success:
                print(f"Disconnection Warning: {disc_msg}")

    exit(exit_code)