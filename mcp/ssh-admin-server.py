from protocol import ServerDefinition, ToolSchema
from datetime import datetime
import uuid
import utils.ssh as ssh

class SSHAdminServer(ServerDefinition):
    def __init__(self):
        super().__init__(
            name="ssh-admin",
            version="1.0",
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
                },
                {
                    "name": "port_restriction",
                    "pattern": r"--port (22|2222)",
                    "action": "require_approval"
                }
            ]
        )
        self.sessions = {}

    def connect(self, host, auth_type, auth_value):
        """Establish and track SSH connection"""
        session_id = str(uuid.uuid4())
        self.sessions[session_id] = {
            "host": host,
            "created": datetime.now(),
            "last_used": datetime.now()
        }
        # Delegate to existing SSH utility with validation
        ssh.connect(host, auth_type, auth_value)
        return session_id

    def execute(self, session_id, command):
        """Execute command on existing connection"""
        if session_id not in self.sessions:
            raise ValueError("Invalid session ID")
        
        self.sessions[session_id]["last_used"] = datetime.now()
        return ssh.execute(command)

def export_server():
    return SSHAdminServer()