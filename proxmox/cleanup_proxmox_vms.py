#!/usr/bin/env python3
import sys
import argparse
from urllib.parse import urlparse
from ssh_exec import ssh_connect, ssh_execute, ssh_disconnect


def cleanup_vm(proxmox_host: str,
               username: str,
               password: str = None,
               key_path: str = None,
               vmid: int = 9000,
               storage: str = "local-lvm",
               destroy_options: str = "--destroy-unreferenced-disks --purge") -> None:
    """
    Stop and destroy a VM on a Proxmox host, cleaning up disks.
    """
    # Connect via SSH
    success, client, msg = ssh_connect(proxmox_host, username, password, key_path)
    if not success:
        print(f"SSH connection failed: {msg}")
        return

    print(f"Connected to Proxmox host {proxmox_host} as {username}.")

    # Stop the VM
    print(f"Stopping VM {vmid}...")
    stop_cmd = f"qm stop {vmid}"
    success, (exit_code, output), error = ssh_execute(client, stop_cmd)
    if not success or exit_code != 0:
        print(f"Warning: failed to stop VM {vmid}: {error or output}")
    else:
        print(f"Stop command output: {output}")

    # Destroy the VM and its disks
    print(f"Destroying VM {vmid} with options '{destroy_options}'...")
    destroy_cmd = f"qm destroy {vmid} {destroy_options}"
    success, (exit_code, output), error = ssh_execute(client, destroy_cmd)
    if not success or exit_code != 0:
        print(f"Error: failed to destroy VM {vmid}: {error or output}")
    else:
        print(f"Destroy command output: {output}")

    ssh_disconnect(client)
    print("Cleanup complete.")


def main():
    parser = argparse.ArgumentParser(
        description="Stop and clean up a Proxmox VM by ID over SSH"
    )
    # SSH URL as a required positional argument
    parser.add_argument(
        'ssh_url',
        help='SSH URL to Proxmox host (e.g. ssh://root@proxmox.example.com:22)'
    )
    # Authentication: either key-path or password
    auth_group = parser.add_mutually_exclusive_group()
    auth_group.add_argument(
        '--key-path', '-k',
        help='Path to SSH private key file for authentication'
    )
    auth_group.add_argument(
        '--password', '-p',
        help='SSH password (mutually exclusive with key-path)'
    )
    parser.add_argument(
        '--id', '-i', dest='vmid', required=True, type=int,
        help='ID of the VM to stop and destroy'
    )
    parser.add_argument(
        '--storage', '-s', default='local-lvm',
        help='Storage pool name for disk cleanup (default: local-lvm)'
    )
    parser.add_argument(
        '--destroy-options', '-d',
        default='--destroy-unreferenced-disks --purge',
        help='Additional options for qm destroy'
    )
    args = parser.parse_args()

    # Parse SSH URL
    parsed = urlparse(args.ssh_url)
    if parsed.scheme != 'ssh' or not parsed.username or not parsed.hostname:
        print("Invalid SSH URL format. Use ssh://user@host[:port]")
        sys.exit(1)

    proxmox_host = parsed.hostname
    username = parsed.username
    port = parsed.port or 22

    # Connect and cleanup
    cleanup_vm(
        proxmox_host=proxmox_host,
        username=username,
        password=args.password,
        key_path=args.key_path,
        vmid=args.vmid,
        storage=args.storage,
        destroy_options=args.destroy_options
    )


if __name__ == '__main__':
    main()
