### 2. Branch Code Review Agent

**Purpose**: Automated PR review with intelligent suggestions based on coding standards and best practices.

**Workflow**:
1. Fetch PR details via GitHub MCP
2. Retrieve coding standards from RAG project
3. Analyze changed files with LLM + context
4. Generate review comments
5. Post comments to PR via GitHub MCP
6. Optionally approve/request changes

**Configuration**:
```json
{
  "project_id": "uuid",  // Project with coding standards docs
  "mcp_servers": ["github"],
  "repo": "owner/repo",
  "review_style": "constructive",  // constructive|strict|minimal
  "auto_approve": false,
  "check_tests": true,
  "check_coverage": true
}
```

**Input**:
```json
{
  "pr_number": 123,
  "focus_areas": ["security", "performance", "testing"]
}
```

**Use Cases**:
- Automated first-pass PR reviews
- Enforce coding standards consistently
- Catch security vulnerabilities early
- Reduce manual review load

---