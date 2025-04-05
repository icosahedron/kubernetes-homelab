from protocol import ServerDefinition, ToolSchema
from datetime import datetime, timedelta
import uuid
import utils.ssh as ssh
import logging
from typing import Dict

class SSHAdminServer(ServerDefinition):
    def __init__(self):
        super().__init__(
            name="ssh-admin",
            version="1.1",
            tools=[
                ToolSchema(
                    name="connect",
                    description="Establish SSH connection with validation",
                    parameters={
                        "host": {"type": "string", "format": "ssh://user@host[:port]"},
                        "auth_type": {"type": "choice", "options": ["key", "password"]},
                        "auth_value": {"type": "string", "secret": True}
                    },
                    validation_rules=["ssh_command_validation"]
                ),
                ToolSchema(
                    name="execute",
                    description="Execute validated command on active connection",
                    parameters={
                        "session_id": {"type": "string"},
                        "command": {"type": "string", "max_length": 100}
                    },
                    validation_rules=["ssh_command_validation", "destructive_command_block"]
                )
            ],
            safety_rules=[
                {
                    "name": "destructive_command_block",
                    "pattern": r"(rm -rf|chmod 777|dd if=/dev/)",
                    "action": "reject"
                }
            ]
        )
        self.sessions: Dict[str, dict] = {}

    def connect(self, host: str, auth_type: str, auth_value: str) -> str:
        """Establish and track SSH connection"""
        session_id = str(uuid.uuid4())
        self.sessions[session_id] = {
            "host": host,
            "created": datetime.now(),
            "last_used": datetime.now(),
            "process": ssh.connect(host, auth_type, auth_value)
        }
        return session_id

    def execute(self, session_id: str, command: str) -> str:
        """Execute command on existing connection"""
        if session_id not in self.sessions:
            raise ValueError("Invalid session ID")
        
        session = self.sessions[session_id]
        if datetime.now() - session["last_used"] > timedelta(minutes=15):
            self.cleanup_session(session_id)
            raise TimeoutError("Session expired")
        
        session["last_used"] = datetime.now()
        return ssh.execute(session["process"], command)

    def cleanup_session(self, session_id: str) -> None:
        """Terminate and remove session"""
        if session_id in self.sessions:
            ssh.close_session(session_id)
            del self.sessions[session_id]

# MCP Service Integration
def start_server():
    server = SSHAdminServer()
    server.register()
    return server

if __name__ == "__main__":
    start_server().serve_forever()