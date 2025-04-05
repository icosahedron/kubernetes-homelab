#!/usr/bin/env python3

import argparse
import time
import yaml
from urllib.parse import urlparse
from typing import Tuple
import os
from ssh_exec import ssh_connect, ssh_execute, ssh_disconnect

def check_if_exists(client, vmid: int) -> bool:
    check_vm_cmd = f"qm status {vmid}"
    success, (exit_code, output), error = ssh_execute(client, check_vm_cmd)
    return success and exit_code == 0

def force_remove_vm(client, vmid: int) -> bool:
    print(f"Force flag set. Stopping and destroying existing VM {vmid}...")
    stop_vm_cmd = f"qm stop {vmid}"
    ssh_execute(client, stop_vm_cmd)

    for _ in range(10):
        success, (exit_code, output), error = ssh_execute(client, f"qm status {vmid}")
        if success and "status: stopped" in output:
            print(f"VM {vmid} successfully stopped.")
            break
        print("Waiting for VM to stop...")
        time.sleep(2)
    else:
        print(f"Timeout waiting for VM {vmid} to stop.")
        return False

    destroy_vm_cmd = f"qm destroy {vmid} --destroy-unreferenced-disks"
    ssh_execute(client, destroy_vm_cmd)
    return True

def lookup_vmid_by_name(client, template_name: str) -> int:
    success, (exit_code, output), error = ssh_execute(client, "qm list")
    if not success or exit_code != 0:
        print(f"Failed to list VMs: {error}\nOutput: {output}")
        return None

    for line in output.splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[1] == template_name:
            return int(parts[0])

    print(f"Template '{template_name}' not found in qm list.")
    return None

def create_vm(client, template_name: str, vmid: int, vm_name: str) -> bool:
    print(f"Looking up VMID for template '{template_name}'...")
    template_vmid = lookup_vmid_by_name(client, template_name)
    if template_vmid is None:
        return False

    print(f"Creating VM {vm_name} from template {template_name} (VMID {template_vmid})...")
    create_vm_cmd = f"qm clone {template_vmid} {vmid} --name {vm_name} --full true"
    success, (exit_code, output), error = ssh_execute(client, create_vm_cmd)
    if not success or exit_code != 0:
        print(f"Failed to create VM: {error}\nOutput: {output}")
        return False

    print(f"VM {vm_name} ({vmid}) created successfully.")
    return True

def init_vm(client, vmid: int, ciuser: str, ssh_public_key: str) -> bool:
    print(f"Setting cloud-init user and SSH key for VM {vmid}...")
    ssh_key_cmd = f"qm set {vmid} --ciuser {ciuser} --sshkeys '{ssh_public_key}'"
    success, (exit_code, output), error = ssh_execute(client, ssh_key_cmd)
    if not success or exit_code != 0:
        print(f"Failed to set cloud-init options: {error}\nOutput: {output}")
        return False
    return True

def start_vm(client, vmid: int) -> bool:
    print(f"Starting VM {vmid}...")
    start_vm_cmd = f"qm start {vmid}"
    success, (exit_code, output), error = ssh_execute(client, start_vm_cmd)
    if not success or exit_code != 0:
        print(f"Failed to start VM: {error}\nOutput: {output}")
        return False

    print(f"VM {vmid} started successfully.")
    return True

def provision_vm(proxmox_host: str, username: str, password: str = None, key_path: str = None, port: int = 22, vmid: int = 9000, template_name: str = "", vm_name: str = "", ciuser: str = "", ssh_public_key: str = "", force: bool = False, start: bool = False, storage: str = "local-lvm"):
    if key_path:
        key_path = os.path.expanduser(key_path)

    success, client, msg = ssh_connect(proxmox_host, username, password, key_path, port)
    if not success:
        print(f"SSH connection failed: {msg}")
        return

    print("Connected to Proxmox host via SSH.")

    try:
        if check_if_exists(client, vmid):
            if force:
                if not force_remove_vm(client, vmid):
                    return
            else:
                print(f"VM {vmid} already exists. Use 'force: true' in config to recreate it.")
                return

        if not create_vm(client, template_name, vmid, vm_name):
            return

        if not init_vm(client, vmid, ciuser, ssh_public_key):
            return

        if start:
            if not start_vm(client, vmid):
                return

        print(f"Provisioning completed successfully for VM {vmid} ({vm_name}).")
    finally:
        ssh_disconnect(client)
        print("Disconnected from Proxmox host.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("config_file", nargs="?", help="YAML configuration file")
    parser.add_argument("--help", action="store_true", help="Show example config and exit")
    args = parser.parse_args()

    if args.help or not args.config_file:
        print("""
YAML configuration file is required.
Example:

proxmox:
  ssh_url: ssh://root@proxmox-server
  password: yourpassword
  key_path: /path/to/private/key
  storage: local-lvm

vms:
  - vmid: 9001
    template_name: ubuntu-cloud-template
    vm_name: ubuntu-test-1
    ciuser: ubuntu
    ssh_key_file: /path/to/public/key.pub
    force: true
    start: true
""")
        exit(0)

    with open(args.config_file, 'r') as f:
        config = yaml.safe_load(f)

    proxmox_config = config.get("proxmox", {})
    vms_config = config.get("vms", [])

    parsed_url = urlparse(proxmox_config.get("ssh_url", ""))
    if parsed_url.scheme != "ssh" or not parsed_url.username or not parsed_url.hostname:
        print("Invalid SSH URL format in config. Use ssh://user@host[:port]")
        exit(1)

    username = parsed_url.username
    proxmox_host = parsed_url.hostname
    port = parsed_url.port if parsed_url.port else 22

    key_path = proxmox_config.get("key_path")
    if key_path:
        key_path = os.path.expanduser(key_path)

    for vm in vms_config:
        ssh_key_path = vm.get("ssh_key_file")
        if ssh_key_path:
            ssh_key_path = os.path.expanduser(ssh_key_path)

        if not ssh_key_path or not os.path.isfile(ssh_key_path):
            print(f"SSH key file {ssh_key_path} not found for VM {vm.get('vm_name', vm.get('vmid'))}.")
            continue

        with open(ssh_key_path, 'r') as key_file:
            ssh_public_key = key_file.read().strip()

        provision_vm(
            proxmox_host=proxmox_host,
            username=username,
            password=proxmox_config.get("password"),
            key_path=key_path,
            port=port,
            vmid=vm["vmid"],
            template_name=vm["template_name"],
            vm_name=vm["vm_name"],
            ciuser=vm["ciuser"],
            ssh_public_key=ssh_public_key,
            force=vm.get("force", False),
            start=vm.get("start", False),
            storage=proxmox_config.get("storage", "local-lvm")
        )
