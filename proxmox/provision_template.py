import sys
import argparse
from urllib.parse import urlparse # Add urlparse import
from typing import Tuple

# Assume these are imported from your SSH module
from ssh_exec import ssh_connect, ssh_execute, ssh_disconnect

def provision_ubuntu_template(proxmox_host: str, username: str, password: str = None, key_path: str = None, vmid: int = 9000, force: bool = False):
    success, client, msg = ssh_connect(proxmox_host, username, password, key_path)
    if not success:
        print(f"SSH connection failed: {msg}")
        return

    print("Connected to Proxmox host via SSH.")

    # Variables
    ubuntu_image_url = "https://cloud-images.ubuntu.com/jammy/current/jammy-server-cloudimg-amd64.img"
    local_image_path = "/var/lib/vz/template/iso/jammy-server-cloudimg-amd64.img"
    storage = "local-lvm"

    if force:
        delete_cmd = f"qm destroy {vmid} --destroy-unreferenced-disks --purge"
        print(f"Force deleting existing VM: {delete_cmd}")
        ssh_execute(client, delete_cmd)

    check_image_cmd = f"[ -f {local_image_path} ] && echo 'exists' || echo 'missing'"
    success, (exit_code, output), error = ssh_execute(client, check_image_cmd)
    if not success:
        print(f"Image check failed: {error}")
        ssh_disconnect(client)
        return

    if "missing" in output:
        download_cmd = f"wget -O {local_image_path} {ubuntu_image_url}"
        print(f"Downloading image: {download_cmd}")
        success, (exit_code, output), error = ssh_execute(client, download_cmd)
        if not success or exit_code != 0:
            print(f"Download failed: {error}\nOutput: {output}")
            ssh_disconnect(client)
            return
        else:
            print("Image downloaded successfully.")
    else:
        print("Image already exists. Skipping download.")

    commands = [
        f"qm create {vmid} --name ubuntu-cloud-template --memory 2048 --net0 virtio,bridge=vmbr0",
        f"qm importdisk {vmid} {local_image_path} {storage}",
        f"qm set {vmid} --scsihw virtio-scsi-pci --scsi0 {storage}:vm-{vmid}-disk-0",
        f"qm set {vmid} --ide2 {storage}:cloudinit",
        f"qm set {vmid} --boot c --bootdisk scsi0",
        f"qm set {vmid} --serial0 socket --vga serial0",
        f"qm template {vmid}",
        f"rm {local_image_path}",  # Optional cleanup
    ]

    for cmd in commands:
        print(f"Executing: {cmd}")
        success, (exit_code, output), error = ssh_execute(client, cmd)
        if not success or exit_code != 0:
            print(f"Command failed: {cmd}\nError: {error}\nOutput: {output}")
            ssh_disconnect(client)
            return
        else:
            print(f"Command succeeded: {output}")

    ssh_disconnect(client)
    print("Ubuntu template provisioned successfully.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Connect to an SSH server using an SSH URL and execute a command.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
    Examples:
    python template_provision.py ssh://admin@192.168.1.100:2222 --key-path ~/.ssh/id_rsa_admin --id 101
    """)
    if len(sys.argv) <= 1:
        print(parser.epilog)
        exit()

    parser.add_argument("ssh_url", help="SSH connection URL (e.g., ssh://user@host:port)")
    parser.add_argument("--force", action="store_true", help="Force the template to be created over an existing one.")
    parser.add_argument("--id", help="ID of VM", default=9000)
        
    # Authentication group: Allow either password or key file, but not both.
    # This group is not required, allowing for SSH agent authentication.a
    auth_group = parser.add_mutually_exclusive_group()
    auth_group.add_argument("--password", help="SSH password for authentication")
    auth_group.add_argument("--key-path", help="Path to SSH private key file for authentication")

    args = parser.parse_args()

    exit_code = 0
    client = None

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

    provision_ubuntu_template(
        proxmox_host=hostname,
        username=username,
        password=args.password,
        key_path=args.key_path,
        vmid=args.id,
        force=args.force
    )
