## MCP Servers

MCP (Model Context Protocol) servers extend agent capabilities by providing structured tool access to external services. Declare servers in your agent config or `.md` frontmatter — the backend resolves credentials and routes tool calls automatically.

| MCP Server | Key | Transport | Credential source | Tools |
|-----------|-----|-----------|------------------|-------|
| SSH | `ssh` | stdio | DB (encrypted) | `exec_command`, `get_system_info`, `upload_file`, `download_file`, `list_directory` |
| WinRM | `winrm` | stdio | DB (encrypted) | `exec_powershell`, `get_system_info`, `restart_service`, `list_services`, `get_event_logs`, `get_running_processes`, `exec_cleanup` |
| Gitea | `gitea` | HTTP | `mcp_config.gitea` | `clone_repository`, `get_repo_tree`, `get_file_content`, `update_file`, `commit_and_push`, `create_branch`, `create_pull_request` |
| GitHub | `github` | HTTP | `mcp_config.github` | `get_file_content`, `update_file`, `create_pull_request`, `list_issues`, `create_review` |
| DataGouv | `datagouv` | HTTP | none (public API) | `search_datasets`, `get_dataset`, `search_organizations`, `list_topics`, `get_topic` |
| WikiJS | `wikijs` | HTTP | `mcp_config.wikijs` | `search_pages`, `get_page`, `create_page`, `update_page` |
| SonarQube | `sonarqube` | HTTP | `mcp_config.sonarqube` (API token, Bearer → Basic auto-fallback) | `validate_auth`, `get_system_status`, `list_projects`, `get_project`, `list_branches`, `search_issues`, `fetch_all_issues`, `get_issue`, `get_issues_summary`, `list_security_hotspots`, `get_security_hotspot`, `get_rule`, `get_source_snippet`, `get_quality_gate`, `get_measures` |
| Linter | `linter` | stdio | none | `lint_file`, `format_file`, `lint_directory`, `check_syntax` |
| Test Runner | `test_runner` | stdio | none | `run_tests`, `run_single_test`, `get_coverage` |
