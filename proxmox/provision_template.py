#!/usr/bin/env python3
import os
import sys
import argparse
import yaml
from urllib.parse import urlparse
from typing import Dict, Any

# Assume these are imported from your SSH module
to_import = ["ssh_connect", "ssh_execute", "ssh_disconnect"]
from ssh_exec import ssh_connect, ssh_execute, ssh_disconnect


def provision_ubuntu_template(config: Dict[str, Any]) -> None:
    """
    Provision an Ubuntu cloud template on a Proxmox host using settings from config.
    """
    # ----- SSH Connection Settings -----
    ssh_cfg = config.get('ssh', {})
    url = ssh_cfg.get('url')
    if url:
        parsed = urlparse(url)
        hostname = parsed.hostname
        username = parsed.username
        port = parsed.port or 22
    else:
        hostname = ssh_cfg.get('host')
        username = ssh_cfg.get('username')
        port = ssh_cfg.get('port', 22)

    password = ssh_cfg.get('password')
    key_path = os.path.expanduser(ssh_cfg.get('key_path'))
    if not os.path.exists(key_path):
        print(f"Key path {key_path} not found.")
        return

    success, client, msg = ssh_connect(hostname, username, password, key_path, port=port)
    if not success:
        print(f"SSH connection failed: {msg}")
        return

    print("Connected to Proxmox host via SSH.")

    # ----- Image Download & Storage -----
    img_cfg = config.get('image', {})
    image_url = img_cfg.get('url')
    local_image_path = img_cfg.get('local_path')
    download_enabled = img_cfg.get('download', True)

    # ----- VM Template Parameters -----
    vm_cfg = config.get('vm', {})
    vmid = vm_cfg.get('id')
    vm_name = vm_cfg.get('name', f"vm-{vmid}")
    memory = vm_cfg.get('memory_mb', 2048)
    cores = vm_cfg.get('cores')
    sockets = vm_cfg.get('sockets')
    storage_pool = vm_cfg.get('storage_pool')
    net = vm_cfg.get('network', {})
    network_model = net.get('model', 'virtio')
    network_bridge = net.get('bridge', 'vmbr0')
    scsihw = vm_cfg.get('scsihw', 'virtio-scsi-pci')
    scsi_device = vm_cfg.get('scsi_device', 'scsi0')
    cloudinit_cfg = vm_cfg.get('cloudinit', {})
    cloudinit_enable = cloudinit_cfg.get('enable', True)
    cloudinit_device = cloudinit_cfg.get('device', 'ide2')
    boot_cfg = vm_cfg.get('boot', {})
    boot_order = boot_cfg.get('order', 'c')
    boot_disk = boot_cfg.get('disk', 'scsi0')
    serial_cfg = vm_cfg.get('serial', {})
    serial_type = serial_cfg.get('type', 'socket')
    serial_device = serial_cfg.get('device', 'serial0')
    vga = vm_cfg.get('vga', 'serial0')

    # ----- Force Destroy -----
    force_cfg = config.get('force', {})
    force_destroy = force_cfg.get('destroy_existing', False)
    force_options = force_cfg.get('destroy_options', "--destroy-unreferenced-disks --purge")

    if force_destroy and vmid is not None:
        delete_cmd = f"qm destroy {vmid} {force_options}"
        print(f"Force deleting existing VM: {delete_cmd}")
        ssh_execute(client, delete_cmd)

    # ----- Check & Download Image -----
    check_cmd = f"[ -f {local_image_path} ] && echo exists || echo missing"
    success, (exit_code, output), error = ssh_execute(client, check_cmd)
    if not success:
        print(f"Image check failed: {error}")
        ssh_disconnect(client)
        return

    if "missing" in output and download_enabled:
        download_cmd = f"wget -O {local_image_path} {image_url}"
        print(f"Downloading image: {download_cmd}")
        success, (exit_code, output), error = ssh_execute(client, download_cmd)
        if not success:
            print(f"Download failed: {error}")
            ssh_disconnect(client)
            return
    else:
        print("Image already exists or download disabled. Skipping.")

    # ----- Build Proxmox Commands -----
    commands = []
    create_cmd = f"qm create {vmid} --name {vm_name} --memory {memory}"
    if cores:
        create_cmd += f" --cores {cores}"
    if sockets:
        create_cmd += f" --sockets {sockets}"
    create_cmd += f" --net0 {network_model},bridge={network_bridge}"
    commands.append(create_cmd)

    commands.append(f"qm importdisk {vmid} {local_image_path} {storage_pool}")
    commands.append(f"qm set {vmid} --scsihw {scsihw} --scsi0 {storage_pool}:vm-{vmid}-disk-0")
    if cloudinit_enable:
        commands.append(f"qm set {vmid} --{cloudinit_device} {storage_pool}:cloudinit")
    commands.append(f"qm set {vmid} --boot {boot_order} --bootdisk {boot_disk}")
    commands.append(f"qm set {vmid} --serial0 {serial_type} --vga {vga}")
    commands.append(f"qm template {vmid}")

    cleanup_cfg = config.get('cleanup', {})
    remove_local = cleanup_cfg.get('remove_local_image', False)
    if remove_local:
        commands.append(f"rm {local_image_path}")

    # ----- Execute Commands -----
    for cmd in commands:
        print(f"Executing: {cmd}")
        success, (exit_code, output), error = ssh_execute(client, cmd)
        if not success or exit_code != 0:
            print(f"Command failed: {cmd}\nError: {error}\nOutput: {output}")
            ssh_disconnect(client)
            return
        print(f"Command succeeded: {output}")

    ssh_disconnect(client)
    print("Ubuntu template provisioned successfully.")


def main():
    parser = argparse.ArgumentParser(
        description="Provision Ubuntu template on Proxmox from YAML config"
    )
    parser.add_argument(
        '--config', '-c', required=True,
        help='Path to YAML configuration file'
    )
    parser.add_argument(
        '--force', action='store_true',
        help='Override force-destroy setting in config'
    )
    args = parser.parse_args()

    try:
        with open(args.config) as f:
            config = yaml.safe_load(f)
    except Exception as e:
        print(f"Failed to load config: {e}")
        sys.exit(1)

    if args.force:
        config.setdefault('force', {})['destroy_existing'] = True

    provision_ubuntu_template(config)


if __name__ == '__main__':
    main()
