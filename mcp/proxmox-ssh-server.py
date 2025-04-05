import sys
import json
import re
from uuid import uuid4
from typing import Dict
from ..utils.ssh import SSHClientManager

COMMAND_WHITELIST = re.compile(
    r'^(qm (list|status \d+|start \d+|stop \d+|shutdown \d+|reboot \d+)'
    r'|pvesh (get /nodes/\w+/qemu|get /cluster/resources|get /storage/\w+/status)'
    r'|df -h|free -m|uptime|nproc|lsblk'
    r'|sudo -n (zgrep -h \'^[^#]\' /etc/apt/sources.list.d/\*|apt-get update --allow-releaseinfo-change-suite)'
    r'|zfs (list|get all|snapshot (backup/\d{8}|\w+@\d{8}))$'
)

class ProxmoxMCPServer:
    def __init__(self):
        self.connections: Dict[str, SSHClientManager] = {}
        
    def list_tools(self):
        return {
            "tools": [
                {
                    "name": "proxmox_connect",
                    "description": "Connect to Proxmox host via SSH config",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "config_host": {"type": "string"}
                        },
                        "required": ["config_host"]
                    }
                },
                {
                    "name": "proxmox_execute",
                    "description": "Execute validated command on Proxmox host",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "connection_id": {"type": "string"},
                            "command": {"type": "string"}
                        },
                        "required": ["connection_id", "command"]
                    }
                },
                {
                    "name": "proxmox_disconnect",
                    "description": "Close SSH connection",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "connection_id": {"type": "string"}
                        },
                        "required": ["connection_id"]
                    }
                }
            ]
        }

    def handle_request(self, request: dict):
        try:
            if request.get("method") == "listTools":
                return self.list_tools()
                
            if request.get("method") == "callTool":
                return self.call_tool(request["params"])

            return {"error": "Method not found"}
            
        except Exception as e:
            return {"error": str(e)}

    def call_tool(self, params: dict):
        tool_name = params.get("name")
        args = params.get("arguments", {})

        if tool_name == "proxmox_connect":
            return self.connect(args)
        elif tool_name == "proxmox_execute":
            return self.execute(args)
        elif tool_name == "proxmox_disconnect":
            return self.disconnect(args)
        else:
            return {"error": "Invalid tool"}

    def connect(self, args: dict):
        config_host = args.get("config_host")
        if not config_host:
            return {"error": "Missing config_host"}

        try:
            client = SSHClientManager(config_host=config_host)
            client.connect()
            conn_id = str(uuid4())
            self.connections[conn_id] = client
            return {"result": {"connection_id": conn_id}}
        except Exception as e:
            return {"error": f"Connection failed: {str(e)}"}

    def execute(self, args: dict):
        conn_id = args.get("connection_id")
        command = args.get("command")
        
        if not conn_id or not command:
            return {"error": "Missing parameters"}
            
        if not COMMAND_WHITELIST.match(command):
            return {"error": "Command not allowed"}

        client = self.connections.get(conn_id)
        if not client:
            return {"error": "Invalid connection ID"}

        try:
            status, output = client.execute_command(command)
            return {"result": {"status": status, "output": output}}
        except Exception as e:
            return {"error": str(e)}

    def disconnect(self, args: dict):
        conn_id = args.get("connection_id")
        if not conn_id:
            return {"error": "Missing connection_id"}

        client = self.connections.pop(conn_id, None)
        if not client:
            return {"error": "Invalid connection ID"}

        try:
            client.close()
            return {"result": "Disconnected"}
        except Exception as e:
            return {"error": str(e)}

if __name__ == "__main__":
    server = ProxmoxMCPServer()
    for line in sys.stdin:
        try:
            request = json.loads(line)
            response = server.handle_request(request)
            print(json.dumps(response), flush=True)
        except json.JSONDecodeError:
            print(json.dumps({"error": "Invalid JSON"}))