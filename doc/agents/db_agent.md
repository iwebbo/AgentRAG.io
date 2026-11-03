# AgentRAGIO Platform Documentation: Database & AI Agents

**Purpose**: This documentation provides a comprehensive guide for interacting with the AgentRAGIO backend API. It covers the necessary steps to authenticate, register database connection hosts (MySQL, PostgreSQL, etc.), and deploy specialized AI agents (Skills) capable of executing complex operational queries against various databases.

*Note: All sensitive credentials (tokens, passwords, IPs) have been anonymized or replaced with placeholders.*

---

## 🔑 Authentication & Setup

Before interacting with any API endpoint, an access token must be obtained using the dedicated login endpoint. This token is required in the `Authorization` header for all subsequent requests.

### Step 1: Obtain Access Token

**API Endpoint**: `POST /api/auth/login`

This request authenticates a user and returns a temporary Bearer token.

```bash
# Variables Setup (Replace with actual values)
export BASE="https://<host>:30443"

TOKEN=$(curl -sk -X POST "$BASE/api/auth/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=<YOUR_USERNAME>&password=<YOUR_PASSWORD>" \
  | jq -r '.access_token')

echo "TOKEN=$TOKEN"
```

**Required Header:** `Authorization: Bearer $TOKEN`

---

## 💾 Database Host Management (Hosts)

This section details how to register and test connections to various database instances.

### 1. Registering a New Host

Use this endpoint to add a new database connection profile (e.g., MySQL, PostgreSQL).

**API Endpoint**: `POST /api/hosts/`

```bash
# Example: Adding a MySQL Production Host
curl -X POST "$BASE/api/hosts/" \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{
    "name":"mysql-prod",
    "protocol":"db",
    "host":"<DB_IP_ADDRESS>",
    "username":"monitor",
    "credential_type":"password",
    "password":"***","
    "db_type":"mysql",
    "db_name":"appdb",
    "tags":["db"]
  }'
```

**Key Parameters:**

| Parameter | Description | Required? | Notes |
| :--- | :--- | :--- | :--- |
| `name` | Human-readable name for the host. | Yes | e.g., `mysql-prod`. |
| `protocol` | Must be set to `"db"`. | Yes | Indicates a database connection. |
| `host` | The IP address or hostname of the DB server. | Yes | e.g., `10.0.0.30`. |
| `username` | Database monitoring username. | Yes | |
| `credential_type` | Authentication method (e.g., `password`). | Yes | |
| `password` | The password for the monitor user. | Yes | **Sensitive: Use placeholders.** |
| `db_type` | Type of database (e.g., `mysql`, `postgresql`). | Yes | Determines connection dialect. |
| `db_name` | Default database name to connect to. | Yes | |

### 2. Listing Existing Hosts

Retrieve a list of all configured hosts and their basic metadata.

**API Endpoint**: `GET /api/hosts/`

```bash
curl -sk "$BASE/api/hosts/" \
  -H "Authorization: Bearer $TOKEN" | jq '.[] | {id, name, protocol, host, username, last_connected}'
```

### 3. Testing Connectivity

Verify that the connection details for a specific host are valid and accessible by the agent system.

**API Endpoint**: `POST /api/hosts/<host_id>/test`

```bash
# Replace <HOST_ID> with the ID obtained from listing hosts
curl -X POST "$BASE/api/hosts/<HOST_ID>/test" \
  -H "Authorization: Bearer $TOKEN" | jq
```

---

## 🤖 Agent Deployment (Skills)

This section covers the process of creating and registering a specialized AI agent (Skill) that knows how to interact with specific database types.

### Step 1: Defining the Skill File (`.md`)

The skill logic must be defined in a Markdown file which includes a structured mapping of common operational queries to native SQL statements.

**Example Structure (PostgreSQL Operations):**
*(This structure is used for `db_postgres_ops.md`)*

```markdown
---
skill_id: db_postgres_ops
name: PostgreSQL Ops Agent
type: agent
mcp_servers: [db]
description: "PostgreSQL operations through native SQL (DB connector)"
version: "1.0"
tags: [postgres, postgresql, db, sql]
---

## Mapping
- status        → SELECT version() AS version, current_database() AS db, current_user AS usr, now() - pg_postmaster_start_time() AS uptime
- connections   → SELECT state, count(*) AS nb FROM pg_stat_activity GROUP BY state ORDER BY nb DESC
- taille bases  → SELECT datname, pg_size_pretty(pg_database_size(datname)) AS size FROM pg_database ORDER BY pg_database_size(datname) DESC
# ... (other mappings)

## Format
✅ Success | ⚠️ Warning | ❌ Error + message + fix
```

### Step 2: Registering the Skill Agent

Once the skill file is ready, it must be uploaded and registered with the API. This process creates a persistent agent ID.

**API Endpoint**: `POST /api/skills/register`

```bash
# Example: Uploading the PostgreSQL Ops Skill
curl -sk -X POST "$BASE/api/skills/register" \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@db_postgres_ops.md" \
  -F "auto_create_agent=true" \
  -F "llm_provider=lmstudio" \
  -F "llm_model=openai/gpt-oss-20b" \
  | jq '{skill_id, agent_id, message}'
```

**Key Parameters:**

| Parameter | Type | Description | Notes |
| :--- | :--- | :--- | :--- |
| `file` | File Upload | The local path to the skill definition (`.md`). | Mandatory. |
| `auto_create_agent` | Boolean | If set to `true`, an agent is automatically created upon registration. | Highly recommended for usability. |
| `llm_provider` | String | The LLM service used (e.g., `lmstudio`). | Defines the AI backend. |
| `llm_model` | String | Specific model identifier (e.g., `openai/gpt-oss-20b`). | Determines generation quality. |

---

## 🚀 Agent Execution Workflow

This final step executes the registered agent against a specific host, allowing the LLM to interpret the request and generate the appropriate SQL query using the defined skill mapping.

### Executing an Agent Query (Direct API Call)

**API Endpoint**: `POST /api/agents/<agent_id>/execute`

```bash
# Variables Setup: Get the agent ID from the registration step
export PG_AGENT_ID="<agent_id retourné>" 

curl -sk -X POST "$BASE/api/agents/$PG_AGENT_ID/execute" \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{
    "input_data": {
      "query":"status", 
      "host":"homelabPG"
    }
  }' | jq
```

**Input Payload Structure:**

The request body must be a JSON object containing the `input_data`, which specifies:

| Field | Description | Example Value | Purpose |
| :--- | :--- | :--- | :--- |
| `query` | The operational query requested by the user. | `"status"` or `"slow queries"` | Must match a key defined in the skill's mapping section. |
| `host` | The ID of the target database host. | `"homelabPG"` (or its internal ID) | Specifies which connection to use for execution. |

---
