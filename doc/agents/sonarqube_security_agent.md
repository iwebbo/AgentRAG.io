## 3. Code Quality & Security Agent (SonarQube)

**Purpose**: Automated static code analysis, vulnerability detection, and intelligent remediation generation for maintaining high software quality standards across CI/CD pipelines. This agent integrates SonarQube's deep insights into actionable development tasks.

**Workflow**:
1. **Authentication & Discovery**: Connects to the SonarQube instance using a secure token and lists all available projects (`mode=projects`).
2. **Issue Identification (Scanning)**: Executes targeted scans on specific components, branches, or pull requests to identify issues (Vulnerabilities, Hotspots) based on severity filters (`mode=issues`, `mode=hotspots`).
3. **Project Health Assessment**: Retrieves a comprehensive project overview, checking the Quality Gate status and key metrics (coverage, technical debt).
4. **Root Cause Analysis & Remediation**: For identified issues, it retrieves detailed rule information, source code snippets, and root causes. It then utilizes an LLM (optionally enhanced by RAG) to generate precise, context-aware code fixes (`mode=remediate`).

**Configuration**:
```json
{
  "mcp_servers": ["sonarqube"], // SonarQube instance
  "credential_source": "sonar_token", 
  "default_project_key": "MON_PROJET",
  "analysis_modes": {
    "vulnerability": {
      "type": "VULNERABILITY",
      "severities": ["BLOCKER", "CRITICAL", "MAJOR"]
    },
    "hotspot": {
      "status": "TO_REVIEW"
    }
  },
  "remediation_settings": {
    "use_rag": true, // Uses RAG to inject rule and repository context
    "max_remediations": 3,
    "llm_provider": "lmstudio",
    "llm_model": "qwen3.5-4b-claude-4.6-opus-reasoning-distilled"
  }
}
```

**Use Cases**:
- **CI/CD Gate Check:** Automatically verify if new code introduces critical vulnerabilities or blocks the Quality Gate before merging.
- **Vulnerability Audit:** List all unresolved security flaws (XSS, Injection) in a given project (`mode=issues`).
- **Code Refactoring & Fixation:** Receive a specific issue and immediately generate a functional fix with applicable `diff` instructions.
- **Hotspot Review:** Identify areas of code requiring manual attention or in-depth security review (Security Hotspots).

---