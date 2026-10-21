### 1. Code Generator Agent

**Purpose**: Generate production-ready code from natural language prompts with automatic testing and quality checks.

**Workflow**:
1. Fetch entire repository via GitHub MCP
2. Embed code files into RAG project (if not already done)
3. Retrieve relevant code context via semantic search
4. Generate code using LLM with context
5. Run tests automatically (pytest, jest, junit)
6. Lint and format code (flake8, eslint, prettier)
7. Commit changes to new branch
8. Optionally create Pull Request

**Configuration**:
```json
{
  "project_id": "uuid",
  "mcp_servers": ["github", "test_runner", "linter"],
  "repo": "owner/repo",
  "target_branch": "ai-feature",
  "base_branch": "main",
  "auto_test": true,
  "auto_lint": true,
  "auto_commit": true,
  "auto_create_pr": false,
  "test_framework": "auto",  // pytest|jest|junit|auto
  "language": "auto"  // python|javascript|typescript|auto
}
```

**Input**:
```json
{
  "prompt": "Add OAuth2 authentication with JWT tokens",
  "target_files": ["backend/auth.py", "backend/middleware.py"],
  "create_new_files": true,
  "test_mode": true,
  "commit_message": "feat: add OAuth2 authentication"
}
```

**Output** (streaming):
```json
{"type": "log", "data": {"message": "Fetching repository...", "level": "info"}}
{"type": "log", "data": {"message": "Retrieved 12 relevant code files from RAG", "level": "info"}}
{"type": "progress", "data": {"step": "generating_code", "percent": 30}}
{"type": "log", "data": {"message": "Generated 234 lines of code", "level": "info"}}
{"type": "log", "data": {"message": "Running tests...", "level": "info"}}
{"type": "log", "data": {"message": "✅ All 15 tests passed", "level": "success"}}
{"type": "result", "data": {"files_created": ["backend/auth.py"], "tests_passed": 15}}
```

**Use Cases**:
- Feature development from natural language specs
- Refactoring large codebases with context awareness
- Automated bug fixes with test coverage
- API endpoint generation with documentation

---