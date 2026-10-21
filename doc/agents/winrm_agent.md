
### 6. WinRM Agent — Windows Server Operations

**Purpose**: Financial analysis, invoice processing, and regulatory compliance.

**Workflow**:
1. Create host Linux / Windows
2. Create .md skills
3. Upload & Import
4. Run Agent

**Host**:
```bash
# WinRM NTLM 
POST /api/hosts
{
  "name": "win-srv-01",
  "protocol": "winrm",
  "host": "10.0.0.20",
  "port": 5985,
  "username": "Administrator",
  "credential_type": "ntlm",
  "password": "W1nd0wsP4ss!",
  "domain": "CORP",
  "winrm_transport": "ntlm",
  "winrm_server_cert_validation": "ignore",
  "tags": ["windows", "production", "iis"],
  "notes": "IIS production server"
}

# WinRM HTTPS (port 5986 + cert)
POST /api/hosts
{
  "name": "win-srv-01-secure",
  "protocol": "winrm",
  "host": "10.0.0.20",
  "port": 5986,
  "username": "Administrator",
  "credential_type": "ntlm",
  "password": "W1nd0wsP4ss!",
  "winrm_transport": "ntlm",
  "winrm_server_cert_validation": "validate",
  "tags": ["windows", "production"]
}
```
**Skill**:

```bash
POST /api/skills/register
Content-Type: multipart/form-data

file=@windows_server_agent.md
auto_create_agent=true
llm_provider=ollama
llm_model=llama3.1
```

```md
skill_id: windows_server_ops
type: agent
description: "Operates Windows servers via WinRM — PowerShell execution, IIS management, event logs, service control"
mcp_servers: [winrm]
tags: [winrm, windows, powershell, iis, ops]
version: "1.0"
project_required: false
---

## Purpose
Operate and monitor Windows servers via WinRM/PowerShell.
Manage IIS, Windows Services, event logs, processes, and run arbitrary PowerShell.

## Workflow
1. Identify the target host from the request
2. Call `get_system_info` on first contact to collect OS/hardware context
3. Execute PowerShell scripts or built-in methods as needed
4. Parse JSON output and build a structured report
5. Suggest corrective actions for any detected issues

## Available MCP Tools (WinRM)

| Method | Parameters | Description |
|--------|-----------|-------------|
| `exec_powershell` | `host`, `script` | Run arbitrary PowerShell — returns stdout/stderr/exit_code |
| `exec_cmd` | `host`, `cmd`, `args[]?` | Run a classic cmd.exe command |
| `check_service` | `host`, `service` | Get Windows service status (JSON) |
| `restart_service` | `host`, `service` | Restart a Windows service |
| `start_service` | `host`, `service` | Start a Windows service |
| `stop_service` | `host`, `service` | Stop a Windows service |
| `get_event_logs` | `host`, `log_name?`, `level?`, `count?` | Query Windows Event Logs |
| `get_system_info` | `host` | Collect OS/CPU/RAM/disk info (persisted in DB) |
| `get_running_processes` | `host`, `top_n?` | Top N processes by memory usage |
| `list_services` | `host`, `status?` | List all/filtered Windows services |
| `exec_cleanup` | `host` | Clean temp files + force GC |

## Instructions

**Check IIS status and restart if needed:**
check_service:   host=<name> service=W3SVC
restart_service: host=<name> service=W3SVC

## Output Format
Always return:
- **Host**: name + resolved IP
- **OS**: Windows version from `get_system_info`
- **Status**: OK / WARNING / CRITICAL
- **Findings**: anomalies or relevant state
- **Actions taken**: each method called + result summary
- **Recommendations**: next steps or escalation path
```

### Windows WinRM Agents
 
| Skill | Purpose |
|-------|---------|
| `iis_ops` | Manage IIS — app pool lifecycle, site bindings, SSL certificates, access log analysis, FREB |
| `windows_incident` | Triage Windows incidents — CPU/memory/disk pressure, event log errors, stuck processes, service failures |
| `sqlserver_ops` | Monitor SQL Server — blocking queries, AG replication lag, failed jobs, index fragmentation, backup status |
| `windows_deploy_rollback` | Deploy & rollback — robocopy staging, app pool recycle, health check, auto-rollback, backup snapshots |
| `windows_log_analyzer` | Analyse Windows logs — Event Log queries, failed logins, lockouts, IIS W3C logs, custom app logs |
 
---