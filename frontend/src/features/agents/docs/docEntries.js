import { AGENT_TYPES } from '../registry';

// Contenu statique de l'onglet Docs.

const SKILL_MD_EXAMPLES = [
  {
    key: 'web_server_ops',
    filename: 'web_server_ops.md',
    content: `---
skill_id: web_server_ops
name: web_server_ops
type: agent
mcp_servers: [ssh]
description: "Ops serveurs web nginx/apache"
version: "1.0"
tags: [nginx,apache,web,ssh]
---
## Mapping
- reload nginx     → nginx -t && systemctl reload nginx
- logs access      → tail -n 100 /var/log/nginx/access.log
- logs error       → tail -n 100 /var/log/nginx/error.log
- config nginx     → cat /etc/nginx/nginx.conf
- check sites      → ls /etc/nginx/sites-enabled/
- status           → systemctl status nginx --no-pager
## Format
✅ Succès | ⚠️ Warning | ❌ Erreur + stderr + fix`
  },
  {
    key: 'k8s_ops',
    filename: 'k8s_ops.md',
    content: `---
skill_id: k8s_ops
name: k8s_ops
type: agent
mcp_servers: [ssh]
description: "Ops noeuds Kubernetes via kubectl"
version: "1.0"
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
✅ Succès | ⚠️ Warning | ❌ Erreur + stderr + fix`
  },
  {
    key: 'postgres_ops',
    filename: 'postgres_ops.md',
    content: `---
skill_id: postgres_ops
name: postgres_ops
type: agent
mcp_servers: [ssh]
description: "Ops base PostgreSQL via psql"
version: "1.0"
tags: [postgres,postgresql,db,sql,ssh]
---
## Mapping
- status           → systemctl status postgresql --no-pager
- restart          → systemctl restart postgresql
- connexions       → psql -U postgres -c "SELECT count(*), state FROM pg_stat_activity GROUP BY state"
- taille bases     → psql -U postgres -c "SELECT datname, pg_size_pretty(pg_database_size(datname)) FROM pg_database ORDER BY pg_database_size(datname) DESC"
- locks            → psql -U postgres -c "SELECT pid, usename, application_name, state, wait_event_type, query FROM pg_stat_activity WHERE wait_event_type='Lock'"
- slow queries     → psql -U postgres -c "SELECT pid, now()-query_start AS duration, query FROM pg_stat_activity WHERE state='active' ORDER BY duration DESC LIMIT 10"
- vacuum           → psql -U postgres -c "VACUUM ANALYZE"
- logs             → tail -n 100 /var/log/postgresql/postgresql-*.log
- disk             → df -h /var/lib/postgresql
## Format
✅ Succès | ⚠️ Warning | ❌ Erreur + stderr psql + fix`
  }
];

const SKILL_REGISTER_CURL = `curl -X POST https://<host>/api/skills/register \\
  -H "Authorization: Bearer <token>" \\
  -F "file=@web_server_ops.md" \\
  -F "auto_create_agent=true" \\
  -F "llm_provider=lmstudio" \\
  -F "llm_model=openai/gpt-oss-20b"`;

const MCP_SERVERS_STATIC = [
  { key: 'ssh',         transport: 'stdio', credential: 'DB (encrypted)',       tools: 'exec_command, get_system_info, upload_file, download_file, list_directory' },
  { key: 'winrm',       transport: 'stdio', credential: 'DB (encrypted)',       tools: 'exec_powershell, get_system_info, restart_service, list_services, get_event_logs, get_running_processes, exec_cleanup' },
  { key: 'psrp',        transport: 'stdio', credential: 'DB (encrypted)',       tools: 'exec_powershell, exec_multi, exec_cmd, get_system_info, check_service, restart_service, stop_service, start_service, list_services, get_event_logs, get_running_processes, exec_cleanup, upload_file, download_file' },
  { key: 'db',          transport: 'stdio', credential: 'DB (encrypted)',       tools: 'query, execute, exec_multi, list_databases, list_tables, describe_table, get_system_info, test_connection' },
  { key: 'gitea',       transport: 'HTTP',  credential: 'mcp_config.gitea',     tools: 'clone_repository, get_repo_tree, get_file_content, update_file, commit_and_push, create_branch, create_pull_request, get_pr, list_prs, list_commits' },
  { key: 'github',      transport: 'HTTP',  credential: 'mcp_config.github',    tools: 'get_file_content, update_file, create_pull_request, list_issues, create_review, get_pr, list_prs, list_commits, clone_repository, commit_and_push' },
  { key: 'datagouv',    transport: 'HTTP',  credential: 'none (public API)',    tools: 'search_datasets, get_dataset, search_organizations, list_topics, get_topic' },
  { key: 'wikijs',      transport: 'HTTP',  credential: 'mcp_config.wikijs',    tools: 'search_pages, get_page, create_page, update_page' },
  { key: 'sonarqube',   transport: 'HTTP',  credential: 'mcp_config.sonarqube', tools: 'validate_auth, get_system_status, list_projects, get_project, list_branches, search_issues, fetch_all_issues, get_issue, get_issues_summary, list_security_hotspots, get_security_hotspot, get_rule, get_source_snippet, get_quality_gate, get_measures' },
  { key: 'bitbucket',   transport: 'HTTP',  credential: 'mcp_config.bitbucket', tools: 'parse_url, list_projects, list_repositories, get_repository, list_branches, get_path_type, list_directory, get_file_content, list_commits, list_pull_requests, get_pull_request, get_pull_request_diff, create_branch, write_file, create_pull_request, add_pull_request_comment' },
  { key: 'linter',      transport: 'stdio', credential: 'none',                 tools: 'lint_file, format_file, lint_directory, check_syntax' },
  { key: 'test_runner', transport: 'stdio', credential: 'none',                 tools: 'run_tests, run_single_test, get_coverage' },
];

export const DOC_ENTRIES = [
  {
    key: 'skill', icon: '⌥', title: 'Skill agents (SSH / WinRM / PSRP / DB / Ops)',
    desc: 'Register .md skills with a ## Mapping section. The "Command" field at execution must match a mapping entry. Skills: ssh_admin, winrm_admin, psrp_admin, db_mysql_ops, k8s_ops, postgres_ops, web_server_ops…',
    steps: [
      { n: 1, text: 'Register a .md skill via POST /api/skills/register with auto_create_agent=true. The skill_id in the frontmatter becomes the agent identifier.' },
      { n: 2, text: 'The "Command" field at execution = a phrase matching a line from ## Mapping in your .md. e.g. disk · restart nginx · pods · logs sshd · cleanup' },
      { n: 3, text: 'Host = select from the Hosts tab. Resolution uses GET /api/hosts/ — name or IP, protocol must match the MCP of the skill (ssh, winrm, psrp or db).' },
      { n: 4, text: 'Skill ID is optional at execution — leave empty for auto semantic search, or set it explicitly to force e.g. k8s_ops vs ssh_admin on the same host.' }
    ]
  },
  {
    key: 'skill_examples', icon: '📄', title: 'Skill .md examples — ready-to-register templates',
    desc: 'Copy one of these, adjust the ## Mapping to your infra, then register it via POST /api/skills/register (multipart form, see curl below).',
    curl: SKILL_REGISTER_CURL,
    examples: SKILL_MD_EXAMPLES
  },
  {
    key: 'sonarqube', icon: '◈', title: 'SonarQube Security (fixed agent)',
    desc: 'Fixed agent backed by MCP SonarQube (API token). Bearer → Basic auth fallback is automatic, as is projects/search → components/search_projects on 403. The token needs Browse on target projects, plus See Source Code for mode=remediate.',
    steps: [
      { n: 1, text: 'Create the agent with mcp_config.sonarqube = { base_url, token }. Token: My Account → Security → Generate Token (User token). base_url must not include /api.' },
      { n: 2, text: 'mode=projects → inventory, optional query filter and quality gate per project. mode=overview + project_key → quality gate, metrics, issue facets, hotspots, LLM posture analysis.' },
      { n: 3, text: 'mode=issues + project_key → filtered issues (types, severities, branch, new code). mode=hotspots → security hotspots with risk description and fix recommendations.' },
      { n: 4, text: 'mode=remediate + project_key (top N vulnerabilities) or issue_keys → SonarQube rule + real source snippet (+ optional repository RAG) → LLM fix per issue. Enable Repository RAG + RAG project ID in the agent configuration to align fixes with your codebase conventions.' }
    ]
  },
  {
    key: 'bitbucket', icon: '⬡', title: 'Bitbucket Assistant (fixed agent)',
    desc: 'Fixed agent backed by MCP Bitbucket (Bitbucket Server / Data Center REST API 1.0, HTTP access token). Three modes: read, pull_request, write. Merging a PR is deliberately not exposed.',
    steps: [
      { n: 1, text: 'Create the agent with mcp_config.bitbucket = { base_url, token }. base_url has no /rest (keep the context path if any, e.g. /bitbucket). Token: Profile → Manage account → HTTP access tokens (or Project / Repository settings). Optional: verify_ssl, ca_bundle (internal PKI, takes precedence over verify_ssl), timeout.' },
      { n: 2, text: 'Token permissions: Repository read for modes read and pull_request (post_comment excepted). Repository write for mode write, for open_pr and for post_comment. Repository admin is not needed.' },
      { n: 3, text: 'Target: paste a Bitbucket URL (.../projects/KEY/repos/REPO/browse/<path>?at=<ref>, .../pull-requests/<id>, .../users/NAME/repos/REPO, .../scm/KEY/REPO.git) or set project + repo (+ path, ref, pr_id). Explicit fields override what is deduced from the URL.' },
      { n: 4, text: 'mode=read → file: LLM analysis. Folder / repo: tree + key files (README, Dockerfile, Chart.yaml, values.yaml, Jenkinsfile, bitbucket-pipelines.yml, pom.xml, package.json, pyproject.toml, requirements.txt, go.mod) → LLM analysis. Optional question focuses the answer.' },
      { n: 5, text: 'mode=pull_request → LLM code review of the diff (risks, bugs, security, Docker / Helm CI/CD impact). The review is only posted on the PR if "Post the review as a comment" is ticked.' },
      { n: 6, text: 'mode=write + instruction + file path → the LLM rewrites the whole file, committed on a dedicated branch (auto mcp/<timestamp>-<file> unless branch is given), created from the base ref. A push on the default branch is refused unless allow_push_default=true in the agent configuration. open_pr opens the Pull Request. No dry run: every successful write creates a commit; if the LLM output equals the current file, nothing is committed.' }
    ]
  },
  {
    key: 'changelog', icon: '☰', title: 'Changelog agents (GitHub / Gitea)',
    desc: 'Fixed agents github_changelog and gitea_changelog (same workflow, different MCP server). They build a CHANGELOG.md section from a Pull Request and push it to the PR source branch. No tag and no release are created.',
    steps: [
      { n: 1, text: 'Create the agent with mcp_config.github = { token, repo } (github_changelog) or mcp_config.gitea = { url, token, repo } (gitea_changelog). repo is owner/repo. Use exactly these keys: any other key prevents the MCP server from being registered.' },
      { n: 2, text: 'Execution: Version is required and must be a semantic version (v1.1.81). PR number is optional — by default the agent takes the latest PR (highest number) targeting the base branch, within the configured PR state (open | closed | all). Date is optional (DD/MM/YYYY, default: today).' },
      { n: 3, text: 'Dry run is enabled by default: the section is generated and rendered in the output, nothing is committed. Untick it to clone the PR branch, update the changelog file and push (MCP commit_and_push). A run for a version already present replaces that section; if nothing changes, nothing is pushed.' },
      { n: 4, text: 'The entry is written by the LLM as validated JSON (summary, features, fixes) and always rendered as Markdown by the code. If Use LLM is off, or the output is invalid, a deterministic conventional-commits fallback is used. PRs coming from a fork are refused.' }
    ]
  },
  {
    key: 'branch_generator', icon: '⎇', title: 'Branch generator agents (GitHub / Gitea)',
    desc: 'Fixed agents github_branch_generator and gitea_branch_generator (same workflow, different MCP server). The generation context is embedded in the agent: you only give the need. Files are generated by the LLM in /tmp, pushed to a NEW branch, with an optional Pull Request.',
    steps: [
      { n: 1, text: 'Create the agent with mcp_config.github = { token, repo } (github_branch_generator) or mcp_config.gitea = { url, token, repo } (gitea_branch_generator). Credentials live in the agent MCP config, never in the execute payload. repo is owner/repo.' },
      { n: 2, text: 'Execution: prompt (the need) and branch (new branch name, must not exist) are required. base_branch, repo, commit_message, pr_title and context are optional. create_pr overrides config.auto_create_pr.' },
      { n: 3, text: 'Dry run is enabled by default: files are generated and rendered in the output, nothing is created on the remote. Untick it to run create_branch, clone the new branch, commit_and_push the generated files and (option) create_pull_request.' },
      { n: 4, text: 'Safety: an existing branch is refused (the agent never force-pushes), paths are sanitized (no absolute path, no .., no .git), file count and size are capped (max_files, max_total_kb). If the generated files are identical to the base, nothing is committed.' }
    ]
  },
  {
    key: 'reference', icon: '⌬', title: 'Agent types reference',
    desc: 'All agent_type keys, their badge (fixed / skill), MCP servers used and execute payload shape.',
    columns: ['agent_type', 'name', 'badge', 'MCP servers'],
    table: Object.entries(AGENT_TYPES).map(([key, t]) => ({ key, name: t.name, badge: t.badge, mcp: t.mcp.join(', ') || '—' }))
  },
  {
    key: 'mcp_servers', icon: '🔌', title: 'Available MCP servers',
    desc: 'Static reference — there is currently no DB-backed endpoint listing registered MCP servers, so this table is maintained manually in code and may drift from the actual backend deployment. Cross-check with the backend MCP registry if in doubt.',
    static: true,
    columns: ['key', 'transport', 'credential', 'tools'],
    table: MCP_SERVERS_STATIC
  }
];
