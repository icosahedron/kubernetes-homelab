import json
import re
import sys
from uuid import uuid4
from typing import Dict, Any
from ..utils.ssh import ssh_connect, ssh_execute, ssh_disconnect

COMMAND_WHITELIST = re.compile(
    r'^(qm (list|status \d+|start \d+|stop \d+|shutdown \d+|reboot \d+)'
    r'|pvesh (get /nodes/\w+/qemu|get /cluster/resources|get /storage/\w+/status)'
    r'|df -h|free -m|uptime|nproc|lsblk'
    r'|sudo -n (zgrep -h \'^[^#]\' /etc/apt/sources.list.d/\*|apt-get update --allow-releaseinfo-change-suite)'
    r'|zfs (list|get all|snapshot (backup/\d{8}|\w+@\d{8}))$'
)

class MCPProtocolHandler:
    def __init__(self):
        self.connections: Dict[str, Any] = {}

    def validate_command(self, command: str) -> bool:
        """Validate command against whitelist patterns and numeric constraints"""
        if not COMMAND_WHITELIST.match(command):
            return False
        
        numbers = [int(n) for n in re.findall(r'\b\d+\b', command)]
        if any(n < 1 or n > 9999 for n in numbers):
            return False
            
        return True

    def handle_message(self, message: Dict[str, Any]) -> Dict[str, Any]:
        try:
            if message.get('jsonrpc') != '2.0':
                return self._error_response('Invalid JSON-RPC version', code=-32600)

            method = message.get('method')
            params = message.get('params', {})
            
            if method == 'execute':
                return self._handle_execute(params, message.get('id'))
            elif method == 'connect':
                return self._handle_connect(params, message.get('id'))
            elif method == 'disconnect':
                return self._handle_disconnect(params, message.get('id'))
            
            return self._error_response('Method not found', code=-32601)
        
        except Exception as e:
            return self._error_response(f'Internal error: {str(e)}', code=-32603)

    def _handle_connect(self, params: Dict[str, Any], msg_id: str) -> Dict[str, Any]:
        config_host = params.get('config_host')
        if not config_host:
            return self._error_response('Missing config_host parameter', code=-32602)

        # Use config_host for both host and SSH config lookup
        success, client, message = ssh_connect(
            host=config_host,
            username='',  # Will be overridden by SSH config
            config_host=config_host
        )
        
        if not success:
            return self._error_response(f"Connection failed: {message}", code=401)
        
        conn_id = str(uuid4())
        self.connections[conn_id] = client
        return {
            'jsonrpc': '2.0',
            'id': msg_id,
            'result': {
                'connection_id': conn_id,
                'message': 'Connection established'
            }
        }

    def _handle_execute(self, params: Dict[str, Any], msg_id: str) -> Dict[str, Any]:
        conn_id = params.get('connection_id')
        command = params.get('command')
        timeout = params.get('timeout', 30)
        
        if not conn_id or not command:
            return self._error_response('Missing required parameters', code=-32602)
        
        if not 5 <= timeout <= 300:
            return self._error_response('Timeout out of bounds', code=-32600)
        
        if not self.validate_command(command):
            return self._error_response('Command not allowed', code=403)

        client = self.connections.get(conn_id)
        if not client:
            return self._error_response('Invalid connection ID', code=404)
        
        exec_success, (status, output), exec_msg = ssh_execute(client, command)
        
        if not exec_success:
            return self._error_response(f"Execution failed: {exec_msg}", code=500)
        
        return {
            'jsonrpc': '2.0',
            'id': msg_id,
            'result': {
                'status': status,
                'output': output[:4096]  # Limit output size
            }
        }

    def _handle_disconnect(self, params: Dict[str, Any], msg_id: str) -> Dict[str, Any]:
        conn_id = params.get('connection_id')
        if not conn_id:
            return self._error_response('Missing connection_id', code=-32602)
        
        client = self.connections.pop(conn_id, None)
        if not client:
            return self._error_response('Invalid connection ID', code=404)
        
        success, message = ssh_disconnect(client)
        if not success:
            return self._error_response(f"Disconnect failed: {message}", code=500)
        
        return {
            'jsonrpc': '2.0',
            'id': msg_id,
            'result': {
                'message': 'Connection closed'
            }
        }

    def _error_response(self, message: str, code: int) -> Dict[str, Any]:
        return {
            'jsonrpc': '2.0',
            'error': {
                'code': code,
                'message': message
            }
        }

def main():
    handler = MCPProtocolHandler()
    for line in sys.stdin:
        try:
            message = json.loads(line)
            response = handler.handle_message(message)
            print(json.dumps(response), flush=True)
        except json.JSONDecodeError:
            print(json.dumps({
                'jsonrpc': '2.0',
                'error': {'code': -32700, 'message': 'Parse error'}
            }), flush=True)

if __name__ == '__main__':
    main()