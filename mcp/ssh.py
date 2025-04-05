import subprocess
from datetime import datetime
import uuid
import logging
from typing import Dict, Optional

# Session tracking for MCP integration
active_sessions: Dict[str, dict] = {}

def connect(host: str, auth_type: str, auth_value: str) -> str:
    """Establish SSH connection with session tracking"""
    session_id = str(uuid.uuid4())
    
    # Validate connection parameters
    if not host.startswith("ssh://"):
        raise ValueError("Invalid host format - must start with ssh://")
    
    cmd = ["ssh", host]
    if auth_type == "key":
        cmd.extend(["-i", auth_value])
    elif auth_type == "password":
        # Password handling would use SSH_ASKPASS in real implementation
        raise NotImplementedError("Password auth requires interactive setup")
    
    # Start persistent connection
    proc = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    
    active_sessions[session_id] = {
        "process": proc,
        "host": host,
        "created": datetime.now(),
        "last_used": datetime.now()
    }
    
    return session_id

def execute(session_id: str, command: str) -> str:
    """Execute command on existing SSH session with validation"""
    if session_id not in active_sessions:
        raise ValueError("Invalid session ID")
    
    session = active_sessions[session_id]
    session["last_used"] = datetime.now()
    
    try:
        # Send command and read output
        proc = session["process"]
        proc.stdin.write(command + "\n")
        proc.stdin.flush()
        
        output = []
        while True:
            line = proc.stdout.readline()
            if not line:
                break
            output.append(line.strip())
            
        return "\n".join(output)
    except BrokenPipeError:
        logging.error("SSH connection broken")
        del active_sessions[session_id]
        raise ConnectionError("SSH connection terminated unexpectedly")

def validate_command(command: str) -> bool:
    """Check command against MCP safety rules"""
    # These patterns should match .cline rule definitions
    dangerous_patterns = [
        r"rm -rf",
        r"chmod 777",
        r"> /dev/",
        r"dd if=/dev/"
    ]
    
    return not any(pattern in command for pattern in dangerous_patterns)

def close_session(session_id: str) -> None:
    """Cleanup SSH connection"""
    if session_id in active_sessions:
        try:
            active_sessions[session_id]["process"].terminate()
        except ProcessLookupError:
            pass
        del active_sessions[session_id]

# MCP integration hooks
def mcp_get_active_sessions() -> Dict[str, dict]:
    """Return copy of active sessions for MCP monitoring"""
    return {k: v.copy() for k, v in active_sessions.items()}