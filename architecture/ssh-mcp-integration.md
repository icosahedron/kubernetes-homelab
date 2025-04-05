# SSH MCP Server Architecture

## Overview
```mermaid
graph TD
    A[User] --> B[MCP Client]
    B --> C[Protocol Handler]
    C --> D[Command Validator]
    D --> E[.cline/rules]
    C --> F[Connection Pool]
    F --> G[SSHClientManager]
    G --> H[Proxmox Nodes]
```

## Security Model
### Command Whitelist Patterns
```regex
^(qm (list|status \d+|start \d+|stop \d+|shutdown \d+|reboot \d+)
|pvesh (get /nodes/\w+/qemu)
|df -h|free -m|uptime$
```

### Validation Rules
1. All commands must match exact patterns
2. Numeric parameters limited to VM IDs (1-9999)
3. Maximum command duration: 300s
4. No root access except via sudo-n

## Protocol Implementation
### Message Flow
```mermaid
sequenceDiagram
    participant U as User
    participant M as MCP Server
    participant P as Proxmox
    
    U->>M: { "method": "execute", "params": { "command": "qm list" }}
    M->>M: Validate against .cline/rules
    M->>P: SSH via Connection Pool
    P->>M: Command Results
    M->>U: { "result": "...", "status": 0 }
```

## Deployment Configuration
```yaml
# .cline/mcp/ssh.yaml
connection_pool:
  max_connections: 5
  keepalive: 60
  timeout: 300

security:
  command_validation: strict
  log_sanitization: true
```

## Compliance
- Matches ssh-command-validation.mdc Rule #4
- Follows proxmox-ssh.mdc Host Patterns
- Implements Connection Pooling from RFC-ssh-pool-2025