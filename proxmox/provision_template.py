#!/usr/bin/env python3
import sys
import argparse
import yaml
from urllib.parse import urlparse
from typing import Dict, Any
from ssh_exec import ssh_connect, ssh_execute, ssh_disconnect


def provision_ubuntu_template(config: Dict[str, Any], force: bool = False) -> None:
    ssh_cfg = config.get('ssh', {})
    url = ssh_cfg.get('url')
    parsed = urlparse(url)
    hostname = parsed.hostname
    username = parsed.username
    port = parsed.port or 22
    password = ssh_cfg.get('password')
    import os
    key_path = os.path.expanduser(ssh_cfg.get('key_path') or "") or None

    success, client, msg = ssh_connect(hostname, username, password, key_path, port=port)
    if not success:
        print(f"SSH connection failed: {msg}")
        return

    print("Connected to Proxmox host via SSH.")

    vm_cfg = config.get('vm', {})
    vmid = vm_cfg.get('id')
    vm_name = vm_cfg.get('name', f"vm-{vmid}")
    image_cfg = config.get('image', {})
    image_url = image_cfg.get('url')
    local_image_path = image_cfg.get('local_path')
    storage_pool = vm_cfg.get('storage_pool', 'local-lvm')

    # Check if VM already exists
    check_vm_cmd = f"qm status {vmid}"
    success, (exit_code, output), error = ssh_execute(client, check_vm_cmd)
    if success and exit_code == 0:
        if force:
            print(f"VM {vmid} already exists, removing it first...")
            delete_cmd = f"qm destroy {vmid} --destroy-unreferenced-disks --purge"
            ssh_execute(client, delete_cmd)
        else:
            print(f"Template VM {vmid} already exists. Use --force to recreate.")
            ssh_disconnect(client)
            return

    # Download image if not exists
    check_image_cmd = f"[ -f {local_image_path} ] && echo 'exists' || echo 'missing'"
    success, (exit_code, output), error = ssh_execute(client, check_image_cmd)
    if "missing" in output:
        download_cmd = f"wget -O {local_image_path} {image_url}"
        ssh_execute(client, download_cmd)

    # Provision the VM (simplified)
    commands = [
        f"qm create {vmid} --name {vm_name} --memory 2048 --net0 virtio,bridge=vmbr0",
        f"qm importdisk {vmid} {local_image_path} {storage_pool}",
        f"qm set {vmid} --scsihw virtio-scsi-pci --scsi0 {storage_pool}:vm-{vmid}-disk-0",
        f"qm set {vmid} --ide2 {storage_pool}:cloudinit",
        f"qm set {vmid} --boot c --bootdisk scsi0",
        f"qm set {vmid} --serial0 socket --vga serial0",
        f"qm template {vmid}",
    ]
    for cmd in commands:
        ssh_execute(client, cmd)

    ssh_disconnect(client)
    print("Provision complete.")


def delete_template(config: Dict[str, Any]) -> None:
    ssh_cfg = config.get('ssh', {})
    url = ssh_cfg.get('url')
    parsed = urlparse(url)
    hostname = parsed.hostname
    username = parsed.username
    port = parsed.port or 22
    password = ssh_cfg.get('password')
    import os
    key_path = os.path.expanduser(ssh_cfg.get('key_path') or "") or None

    success, client, msg = ssh_connect(hostname, username, password, key_path, port=port)
    if not success:
        print(f"SSH connection failed: {msg}")
        return

    vm_cfg = config.get('vm', {})
    vmid = vm_cfg.get('id')

    # Check if VM exists and delete
    check_vm_cmd = f"qm status {vmid}"
    success, (exit_code, output), error = ssh_execute(client, check_vm_cmd)
    if success and exit_code == 0:
        print(f"Deleting VM {vmid}...")
        delete_cmd = f"qm destroy {vmid} --destroy-unreferenced-disks --purge"
        ssh_execute(client, delete_cmd)
    else:
        print(f"VM {vmid} does not exist or already deleted.")

    ssh_disconnect(client)


def main():
    parser = argparse.ArgumentParser(description="Create or delete a VM template")
    subparsers = parser.add_subparsers(dest="command", required=True)

    create_parser = subparsers.add_parser("create", help="Create a VM template")
    create_parser.add_argument("config", help="Path to YAML config file")
    create_parser.add_argument("--force", action="store_true", help="Force delete existing template before creating")

    delete_parser = subparsers.add_parser("delete", help="Delete a VM template")
    delete_parser.add_argument("config", help="Path to YAML config file")

    args = parser.parse_args()
    try:
        with open(args.config) as f:
            config = yaml.safe_load(f)
    except Exception as e:
        print(f"Failed to read config: {e}")
        sys.exit(1)

    if args.command == "create":
        provision_ubuntu_template(config, force=args.force)
    elif args.command == "delete":
        delete_template(config)


if __name__ == "__main__":
    main()
