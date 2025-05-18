#!/usr/bin/env python3

import argparse
import time
import yaml
from urllib.parse import urlparse
from typing import Tuple, Optional
import os
from colorama import Fore, Style, init as colorama_init
from ssh_exec import ssh_connect, ssh_execute, ssh_disconnect

def check_if_exists(client, vmid: int) -> bool:
    check_vm_cmd = f"qm status {vmid}"
    success, (exit_code, output), error = ssh_execute(client, check_vm_cmd)
    return success and exit_code == 0

def delete_vm(client, vmid: int) -> bool:
    print(f"Force flag set. Stopping and destroying existing VM {vmid}...")
    ssh_execute(client, f"qm stop {vmid}")

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

    ssh_execute(client, f"qm destroy {vmid} --destroy-unreferenced-disks")
    return True

def lookup_vmid_by_name(client, template_name: str) -> int:
    success, (exit_code, output), error = ssh_execute(client, "qm list")
    if not success or exit_code != 0:
        print(f"Failed to list VMs: {error}\nOutput:\n{output}")
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
        print(Fore.RED + f"Failed to create VM: {error}\nOutput:\n{output}")
        return False

    print(Fore.GREEN + f"VM {vm_name} ({vmid}) created successfully.")
    return True

def init_vm(client, vmid: int, ciuser: str, ssh_public_key: str, include_guest_agent: bool) -> bool:
    print(f"Setting cloud-init user and SSH key for VM {vmid}...")

    remote_key_path = f"/tmp/vm-{vmid}-key.pub"
    upload_key_cmd = f"echo '{ssh_public_key}' > {remote_key_path}"
    success, (exit_code, output), error = ssh_execute(client, upload_key_cmd)
    if not success or exit_code != 0:
        print(Fore.RED + f"Failed to upload SSH key: {error}\nOutput:\n{output}")
        return False

    ssh_key_cmd = f"qm set {vmid} --ciuser {ciuser} --sshkeys {remote_key_path}"
    success, (exit_code, output), error = ssh_execute(client, ssh_key_cmd)
    if not success or exit_code != 0:
        print(Fore.RED + f"Failed to set cloud-init options: {error}\nOutput:\n{output}")
        return False

    print(f"Configuring console and guest agent for VM {vmid}")
    no_graphics_cmd = f"qm set {vmid} --vga serial0 --serial0 socket --args '-nographic'"
    success, (exit_code, output), error = ssh_execute(client, no_graphics_cmd)
    if not success or exit_code != 0:
        print(Fore.RED + f"Failed to set graphics options: {error}\nOutput:\n{output}")
        return False

    if include_guest_agent:
        guest_agent_cmd = f"qm set {vmid} --agent enabled=1"
        success, (exit_code, output), error = ssh_execute(client, guest_agent_cmd)
        if not success or exit_code != 0:
            print(Fore.RED + f"Failed to install guest agent: {error}\nOutput:\n{output}")
            return False

    cleanup_cmd = f"rm -f {remote_key_path}"
    ssh_execute(client, cleanup_cmd)

    return True

def start_vm(client, vmid: int) -> bool:
    print(f"Starting VM {vmid}...")
    start_vm_cmd = f"qm start {vmid}"
    success, (exit_code, output), error = ssh_execute(client, start_vm_cmd)
    if not success or exit_code != 0:
        print(Fore.RED + f"Failed to start VM: {error}\nOutput:\n{output}")
        return False

    print(Fore.GREEN + f"VM {vmid} started successfully.")
    return True

def upload_cloud_init_file(client,
                            cloud_init_file: str,
                            vmid: int) -> None:
    """
    Uploads a cloud-init user-data file to the Proxmox host snippets directory
    and configures the VM to use it via qm set --cicustom.
    Raises on failure.
    """
    local_path = os.path.expanduser(cloud_init_file)
    if not os.path.isfile(local_path):
        raise FileNotFoundError(f"Cloud-init file {local_path} not found.")
    remote_snippet_dir = "/var/lib/vz/snippets"
    remote_filename = os.path.basename(local_path)
    remote_path = f"{remote_snippet_dir}/{remote_filename}"

    print(f"Uploading cloud-init file {local_path} to {remote_path}...")
    success, msg = ssh_copy_file(client, local_path, remote_path)
    if not success:
        raise RuntimeError(f"Failed to upload cloud-init file: {msg}")

    print(f"Configuring VM {vmid} to use custom cloud-init user-data {remote_filename}...")
    cicustom_cmd = f"qm set {vmid} --cicustom user=snippets:{remote_filename}"
    success, (exit_code, output), error = ssh_execute(client, cicustom_cmd)
    if not success or exit_code != 0:
        # cleanup snippet on failure
        ssh_execute(client, f"rm -f {remote_path}")
        raise RuntimeError(
            f"Failed to set cloud-init custom file: {error}\nOutput:\n{output}"
        )

def provision_vm(
    proxmox_host: str,
    username: str,
    password: Optional[str] = None,
    key_path: Optional[str] = None,
    port: int = 22,
    vmid: int = 9000,
    template_name: str = "",
    vm_name: str = "",
    ciuser: str = "",
    ssh_public_key: str = "",
    force: bool = False,
    start: bool = False,
    storage: str = "local-lvm",
    include_guest_agent: bool = True,
    cloud_init_file: Optional[str] = None
) -> None:
    # Expand key path
    if key_path:
        key_path = os.path.expanduser(key_path)

    # Connect
    success, client, error = ssh_connect(
        proxmox_host,
        username,
        password=password,
        key_path=key_path,
        port=port
    )
    if not success:
        raise RuntimeError(f"SSH connection failed: {error}")

    try:
        # Handle cloud-init upload if requested
        if cloud_init_file:
            upload_cloud_init_file(client, cloud_init_file, vmid)

        # Proceed with VM create/configure
        if check_if_exists(client, vmid):
            if force:
                delete_vm(client, vmid)
            else:
                print(f"VM {vmid} already exists. Use the --force flag to delete it. Skipping.")
                return

        if not create_vm(client, template_name, vmid, vm_name):
            raise RuntimeError("create_vm failed")

        if not init_vm(client, vmid, ciuser, ssh_public_key, include_guest_agent):
            raise RuntimeError("init_vm failed")

        if start:
            if not start_vm(client, vmid):
                raise RuntimeError("start_vm failed")

        print(Fore.GREEN + f"Provisioning completed successfully for VM {vmid} ({vm_name}).")
    finally:
        ssh_disconnect(client)
        print("Disconnected from Proxmox host.")

def print_usage():
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
    guest_agent: false
""")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("config_file", nargs="?", help="YAML configuration file")
    parser.add_argument("--help", action="store_true", help="Show example config and exit")
    parser.add_argument(
        '--force', action='store_true',
        help='Override force-destroy setting in config'
    )

    args = parser.parse_args()

    colorama_init(autoreset=True)

    if args.help or not args.config_file:
        print_usage()
        exit(0)

    with open(args.config_file, 'r') as f:
        config = yaml.safe_load(f)

    proxmox_config = config.get("proxmox", {})
    vms_config = config.get("vms", [])

    parsed_url = urlparse(proxmox_config.get("ssh_url", ""))
    if parsed_url.scheme != "ssh" or not parsed_url.username or not parsed_url.hostname:
        print(Fore.RED + "Invalid SSH URL format in config. Use ssh://user@host[:port]")
        exit(1)

    username = parsed_url.username
    proxmox_host = parsed_url.hostname
    port = parsed_url.port if parsed_url.port else 22

    key_path = proxmox_config.get("key_path")
    if key_path:
        key_path = os.path.expanduser(key_path)

    password = proxmox_config.get("password")
    storage = proxmox_config.get("storage", "local-lvm")

    success, client, msg = ssh_connect(proxmox_host, username, password, key_path, port)
    if not success:
        print(Fore.RED + f"SSH connection failed: {msg}")
        exit(1)

    print(Fore.GREEN + "Connected to Proxmox host via SSH.")

    successful_vms = []
    failed_vms = []

    try:
        for vm in vms_config:
            ssh_key_path = vm.get("ssh_key_file")
            if ssh_key_path:
                ssh_key_path = os.path.expanduser(ssh_key_path)

            if not ssh_key_path or not os.path.isfile(ssh_key_path):
                print(Fore.RED + f"SSH key file {ssh_key_path} not found for VM {vm.get('vm_name', vm.get('vmid'))}.")
                failed_vms.append(vm.get('vm_name', vm.get('vmid')))
                continue

            with open(ssh_key_path, 'r') as key_file:
                ssh_public_key = key_file.read().strip()

            try:
                provision_vm(
                    proxmox_host=proxmox_host,
                    username=username,
                    password=password,
                    key_path=key_path,
                    port=port,
                    vmid=vm["vmid"],
                    template_name=vm["template_name"],
                    vm_name=vm["vm_name"],
                    ciuser=vm["ciuser"],
                    ssh_public_key=ssh_public_key,
                    force=True if args.force else vm.get("force", False),
                    start=vm.get("start", False),
                    storage=storage,
                    include_guest_agent=vm.get("guest_agent")
                )
                successful_vms.append(vm.get('vm_name', vm.get('vmid')))
            except Exception as e:
                print(Fore.RED + f"Error provisioning VM {vm.get('vm_name', vm.get('vmid'))}: {e}")
                failed_vms.append(vm.get('vm_name', vm.get('vmid')))
    finally:
        ssh_disconnect(client)
        print(Fore.GREEN + "Disconnected from Proxmox host.")

    print("\nSummary:")
    if successful_vms:
        print(Fore.GREEN + f"Successfully provisioned: {', '.join(map(str, successful_vms))}")
    else:
        print(Fore.RED + "No VMs provisioned successfully.")

    if failed_vms:
        print(Fore.RED + f"Failed to provision: {', '.join(map(str, failed_vms))}")
