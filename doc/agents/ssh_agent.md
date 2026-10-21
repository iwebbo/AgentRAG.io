### 5. SSH Agent — Linux Server Monitoring

**Purpose**: Operate and monitor Linux servers via natural language. Covers Apache/Nginx web server management, Kubernetes node inspection, Docker container lifecycle, PostgreSQL/MySQL health checks, log analysis, disk/CPU/memory diagnostics, zero-downtime deployments, and automated incident remediation — all executed through SSH without leaving your chat interface.

**Use Cases**:
"nginx is returning 502 on prod-web-01, check error logs and reload config"
"list all pods in CrashLoopBackOff on the k8s node"
"rotate logs on all app servers and check disk space after"
"restart the PostgreSQL service and verify replication lag"
"deploy the latest Docker image to staging and confirm the container is healthy"
"check Apache virtual hosts config and test syntax before reload"
"analyze the last 100 lines of /var/log/syslog for OOM kills"

**Workflow**:
1. Create host Linux / Windows
2. Create .md skills
3. Upload & Import
4. Run Agent

**Host**:
```bash
{
# SSH par clé privée
POST /api/hosts
{
  "name": "prod-web-01",
  "protocol": "ssh",
  "host": "192.168.1.10",
  "port": 22,
  "username": "deploy",
  "credential_type": "key",
  "key_content": "-----BEGIN RSA PRIVATE KEY-----\n...\n-----END RSA PRIVATE KEY-----",
  "key_passphrase": "optional_passphrase",
  "tags": ["production", "web"],
  "notes": "Web server prod cluster A"
}

# OU SSH par mot de passe
POST /api/hosts
{
  "name": "prod-web-01",
  "protocol": "ssh",
  "host": "192.168.1.10",
  "port": 22,
  "username": "deploy",
  "credential_type": "password",
  "password": "s3cur3p4ss",
  "tags": ["production", "web"]
}
```
**Skill**:

```bash
POST /api/skills/register
Content-Type: multipart/form-data

file=@linux_server_agent.md
auto_create_agent=true
llm_provider=ollama
llm_model=llama3.1
```

```md
skill_id: k8s_ops
type: agent
mcp_servers: [ssh]
description: "Ops noeuds Kubernetes via kubectl"
tags: [kubernetes,k8s,kubectl,ssh]
---
## Mapping
- pods             → kubectl get pods -A
- logs <pod>       → kubectl logs <pod> --tail=50
- describe <pod>   → kubectl describe pod <pod>
- nodes            → kubectl get nodes -o wide
- drain <node>     → kubectl drain <node> --ignore-daemonsets --delete-emptydir-data
- events           → kubectl get events --sort-by=.lastTimestamp -A | tail -20
## Format
✅ Succès | ⚠️ Warning | ❌ Erreur + stderr + fix
```

### Linux SSH Agents
 
| Skill | Purpose |
|-------|---------|
| `nginx_ops` | Manage Nginx — config test, reload, log analysis, upstream health, SSL expiry check |
| `apache_ops` | Manage Apache — VHost management, mod_status, graceful restart, SSL, access log analysis |
| `kubernetes_node_ops` | Inspect Kubernetes — pod triage, CrashLoopBackOff diagnosis, node drain, rolling restarts, rollback |
| `docker_ops` | Operate Docker — container lifecycle, image pull, health checks, Compose redeploy, prune |
| `postgres_ops` | Monitor PostgreSQL — replication lag, slow queries, lock contention, bloat, backup status |
| `mysql_ops` | Monitor MySQL/MariaDB — processlist, replica lag, slow log, InnoDB metrics, backup check |
| `linux_incident` | Triage Linux incidents — CPU/memory/disk pressure, OOM kills, systemd failures, network saturation |
| `log_analyzer` | Analyse any log — grep/awk/tail, error patterns, log rotation, SFTP download |
| `deploy_rollback` | Deploy & rollback — git pull, build, service restart, health check, auto-rollback on failure |


---