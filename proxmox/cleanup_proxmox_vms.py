import argparse
from urllib.parse import urlparse
from typing import Tuple
from ssh_exec import ssh_connect, ssh_execute, ssh_disconnect

# Assume these are imported from your SSH module
# from your_ssh_module import ssh_connect, ssh_execute, ssh_disconnect

def cleanup_vm(proxmox_host: str, username: str, password: str = None, key_path: str = None, vmid: int = 9000, storage: str = "local-lvm"):
    success, client, msg = ssh_connect(proxmox_host, username, password, key_path)
    if not success:
        print(f"SSH connection failed: {msg}")
        return

    print("Connected to Proxmox host via SSH.")

    # Check if VM exists
    check_vm_cmd = f"qm status {vmid}"
    success, (exit_code, output), error = ssh_execute(client, check_vm_cmd)
    if success and exit_code == 0:
        print(f"Destroying VM {vmid}...")
        destroy_vm_cmd = f"qm destroy {vmid} --destroy-unreferenced-disks"
        ssh_execute(client, destroy_vm_cmd)
    else:
        print(f"VM {vmid} does not exist. Skipping destroy.")

    # Check for leftover disks
    list_disks_cmd = f"pvesm list {storage} | awk '/vm-{vmid}-/ {{print $1}}'"
    success, (exit_code, output), error = ssh_execute(client, list_disks_cmd)
    leftover_disks = output.strip().split('\n') if output.strip() else []

    if leftover_disks:
        print(f"Cleaning up leftover disks for VM {vmid}...")
        for vol in leftover_disks:
            print(f"Freeing volume {vol}...")
            free_disk_cmd = f"pvesm free {vol}"
            ssh_execute(client, free_disk_cmd)
    else:
        print(f"No leftover disks found for VM {vmid}.")

    ssh_disconnect(client)
    print(f"Cleanup completed for VM {vmid}.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Clean up a Proxmox VM and associated disks remotely via SSH")
    parser.add_argument("ssh_url", help="SSH URL in the form ssh://user@host")
    parser.add_argument("--password", help="SSH password")
    parser.add_argument("--key-path", help="Path to SSH key")
    parser.add_argument("--vmid", type=int, required=True, help="VM ID to clean up")
    parser.add_argument("--storage", default="local-lvm", help="Proxmox storage name (default: local-lvm)")

    args = parser.parse_args()

    parsed_url = urlparse(args.ssh_url)
    if parsed_url.scheme != "ssh" or not parsed_url.username or not parsed_url.hostname:
        print("Invalid SSH URL format. Use ssh://user@host")
        exit(1)

    username = parsed_url.username
    proxmox_host = parsed_url.hostname

    cleanup_vm(
        proxmox_host=proxmox_host,
        username=username,
        password=args.password,
        key_path=args.key_path,
        vmid=args.vmid,
        storage=args.storage
    )
