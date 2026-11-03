# Windows Administration Agent (PSRP) Documentation

**Purpose**: This agent provides advanced remote administration capabilities for Windows environments using PowerShell Remoting (PSRP). It allows users to execute complex administrative tasks—such as managing services, analyzing event logs, monitoring processes, and running custom scripts—on target hosts without direct access, acting as an expert Windows administrator via structured API calls.

**Workflow Overview**:
1. **Authentication**: Obtain a secure API token.
2. **Configuration**: Register the target Windows host using PSRP credentials.
3. **Skill Definition**: Define the agent's capabilities by mapping administrative requests to specific PowerShell/CMD functions.
4. **Execution**: Execute commands, scripts, or service controls on the remote machine.

---

## Prerequisites & Authentication

All interactions require a valid API token for authorization.

### Obtaining an Access Token

**API Endpoint**: `POST /api/auth/login`

```bash
# Variables de base (à remplacer)
export BASE="https://agentragio.aecoding.local:30443" 

TOKEN=$(curl -sk -X POST "$BASE/api/auth/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=[USERNAME]&password=[PASSWORD]" \
  | jq -r '.access_token')

echo "TOKEN=$TOKEN"
```

---

## Host Management (PSRP Configuration)

This section details how to register and manage connections to Windows hosts using the PSRP protocol.

### 1. Creating a New Windows Host

The host must be registered with `protocol="psrp"` and use NTLM authentication for Windows credentials.

**API Endpoint**: `POST /api/hosts/`

```bash
# Exemple de connexion à un hôte Windows
curl -X POST "$BASE/api/hosts/" \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{
    "name":"win-01","protocol":"psrp",
    "host":"10.0.0.20","username":"Administrator",
    "credential_type":"ntlm","password":"[PASSWORD]","tags":["windows"]}'
```

### 2. Listing Existing Hosts

To view all configured hosts, including Windows machines:

**API Endpoint**: `GET /api/hosts/`

```bash
curl -sk "$BASE/api/hosts/" \
  -H "Authorization: Bearer $TOKEN" | jq '.[] | {id, name, protocol, host, username, last_connected}'
```

---

## Skill & Agent Definition (PSRP Admin)

The agent's intelligence is defined by its mapping file (`.md`), which translates natural language requests into structured administrative calls.

### 1. The PSRP Admin Skill Blueprint

This skill defines the scope of administration, covering services, logs, processes, and custom scripting.

**Skill ID**: `psrp_admin`
**Description**: Administration Windows distante via PowerShell Remoting (PSRP).
**Objective**: Act as an expert Windows administrator by translating requests into PSRP/PowerShell calls and reporting results clearly on the target host.

### 2. Core Mappings & Capabilities

The agent is capable of handling the following administrative tasks:

| User Request | Internal Mapping / Function | Description |
| :--- | :--- | :--- |
| `restart <service>` | `restart_service` | Restarts a specified Windows service. |
| `stop <service>` | `stop_service` | Stops a running Windows service. |
| `start <service>` | `start_service` | Starts a stopped or disabled service. |
| `check <service>` | `check_service` | Verifies the status of a specified service. |
| `services stopped` | `list_services` (status=Stopped) | Lists all services in a stopped state. |
| `all services` | `list_services` (status=All) | Provides a comprehensive list of all installed services. |
| `error logs` | `get_event_logs` (log_name=System, level=2) | Retrieves critical system error entries. |
| `application errors` | `get_event_logs` (log_name=Application, level=2) | Retrieves application-specific error entries. |
| `processes` | `get_running_processes` (top_n=15) | Lists the top 15 processes consuming the most resources. |
| `system info` | `get_system_info` | Gathers general OS, CPU, RAM, and disk information. |
| `custom PowerShell` | `exec_powershell` | Executes arbitrary, structured PowerShell scripts. |
| `cmd.exe command` | `exec_cmd` | Runs standard Windows Command Prompt commands. |
| `send file to host` | `upload_file` | Transfers a local file to the remote machine. |
| `fetch file from host` | `download_file` | Retrieves a file from the remote machine. |

### 3. Available MCP Tools (PSRP Methods)

The agent utilizes the following structured methods for execution:

| Method | Parameters | Description | Use Case Example |
| :--- | :--- | :--- | :--- |
| `exec_powershell` | `host`, `script`, `timeout?` | Executes a full PowerShell script block. | Getting detailed volume information (`Get-Volume...`). |
| `exec_multi` | `host`, `commands[]`, `timeout?` | Runs multiple commands sequentially in one shared runspace (variables persist). | Restarting a service and then checking its status immediately after. |
| `exec_cmd` | `host`, `cmd`, `args?`, `encoding?` | Executes standard Command Prompt (`cmd.exe`) commands. | Checking network connectivity (`ipconfig`). |
| `list_services` | `host`, `status` (All/Running/Stopped) | Lists services based on their current state. | Auditing all running services. |
| `get_event_logs` | `host`, `log_name?`, `level?`, `count?` | Retrieves specific event log entries. | Checking for critical system failures in the last 20 entries. |
| `get_running_processes` | `host`, `top_n?` | Lists processes, optionally sorted by resource usage. | Identifying memory leaks or runaway processes. |
| `upload_file / download_file` | `host`, `paths` | Handles file transfer operations between local and remote systems. | Retrieving a log file from the server for analysis. |

---

## Agent Execution (Running Operations)

### 1. Registering the Skill/Agent

The first step is to upload the structured skill definition (`psrp_admin.md`) to make the agent available.

**API Endpoint**: `POST /api/skills/register`

```bash
# Exemple de registration du skill PSRP Admin
curl -sk -X POST "$BASE/api/skills/register" \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@psrp_admin.md" \
  -F "auto_create_agent=true" \
  -F "llm_provider=lmstudio" \
  -F "llm_model=openai/gpt-oss-20b" \
  | jq '{skill_id, agent_id, message}'
```

### 2. Executing a Command via the Agent

Once registered, execution is performed by calling the general execution endpoint and providing the necessary context (the desired action).

**API Endpoint**: `POST /api/agents/<AGENT_ID>/execute`

```bash
# Remplace <AGENT_ID> par l'ID retourné lors de la registration du skill
export PSRP_AGENT_ID="<agent_id retourné>" 

curl -sk -X POST "$BASE/api/agents/$PSRP_AGENT_ID/execute" \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{
    "input_data": {
      "query":"error logs", 
      "host":"win-01"
    }
  }' | jq
```

**Key Input Data Fields:**

| Field | Description | Purpose |
| :--- | :--- | :--- |
| `query` | The natural language request (e.g., "error logs"). | This triggers the agent's internal mapping logic to select the correct tool/function. |
| `host` | The name of the target host. | Specifies which Windows machine should execute the command. |

***Disclaimer:** All credentials, tokens, and specific host names used in these examples are placeholders (`[USERNAME]`, `[PASSWORD]`) or anonymized. Replace them with your actual environment variables.*