from typing import Dict, Any, AsyncGenerator, List
import re
from uuid import UUID
from sqlalchemy.orm import Session

from app.agents.base_agent import BaseAgent


class BranchCodeReviewAgent(BaseAgent):
    """
    Agent de Code Review sur une BRANCHE directement (sans PR existante).
    
    Workflow:
    1. Prend une branche en input
    2. Compare avec la branche de base (ex: main)
    3. Analyse tous les fichiers modifiés
    4. Génère des fixes automatiques
    5. Crée une branche de review avec corrections
    6. Ouvre une PR vers la branche originale
    
    Use case: Review du code avant même de créer la PR initiale.
    
    Config attendue:
    {
        "project_id": "uuid",              // Pour RAG context (optionnel)
        "mcp_servers": ["github"],
        "review_focus": "general|security|performance|style",
        "auto_fix": true,
        "auto_create_pr": true,
        "review_branch_prefix": "ai-review-",
        "base_branch": "main"              // Branche de référence
    }
    
    MCP Config:
    {
        "github": {
            "token": "ghp_...",
            "repo": "owner/repo"
        }
    }
    """
    
    def __init__(
        self,
        agent_id: UUID,
        user_id: UUID,
        config: Dict[str, Any],
        mcp_config: Dict[str, Any],
        db: Session
    ):
        super().__init__(agent_id, user_id, config, mcp_config, db)
        
        # Extract config
        self.review_focus = config.get("review_focus", "general")
        self.auto_fix = config.get("auto_fix", True)
        self.auto_create_pr = config.get("auto_create_pr", True)
        self.review_branch_prefix = config.get("review_branch_prefix", "ai-review-")
        self.base_branch = config.get("base_branch", "main")
        self.max_files_per_review = config.get("max_files_per_review", 20)
        
        # LLM config
        self.use_llm = config.get("use_llm", True)
        self.llm_provider = config.get("llm_provider")  # None = use first active
        self.llm_model = config.get("llm_model")  # None = use provider default
        self.llm_temperature = config.get("llm_temperature", 0.3)  # Low temp for code review
    
    async def execute(self, input_data: Dict[str, Any]) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Exécute le code review sur une branche.
        
        input_data:
        {
            "branch": "feature/new-feature",  // Branche à reviewer
            "base_branch": "main"              // Optionnel, override config
        }
        """
        try:
            # Extract input
            repo = input_data.get("repo") or self.mcp_config.get("github", {}).get("repo")
            branch = input_data.get("branch")
            base_branch = input_data.get("base_branch", self.base_branch)
            
            if not repo or not branch:
                raise ValueError("Missing required fields: repo and branch")
            
            # Step 1: Get diff between base and branch
            yield {
                "type": "log",
                "data": self.log("info", f"🔍 Analyzing branch '{branch}' (base: {base_branch})"),
                "timestamp": self.logs[-1]["timestamp"]
            }
            
            # Get changed files
            changed_files_output = await self._get_changed_files(repo, base_branch, branch)
            
            if not changed_files_output:
                yield {
                    "type": "result",
                    "data": {
                        "status": "success",
                        "message": "✅ No changes detected between branches"
                    },
                    "timestamp": self.logs[-1]["timestamp"]
                }
                return
            
            files_changed = changed_files_output
            
            yield {
                "type": "progress",
                "data": {
                    "step": "branch_analyzed",
                    "branch": branch,
                    "base_branch": base_branch,
                    "files_count": len(files_changed)
                },
                "timestamp": self.logs[-1]["timestamp"]
            }
            
            # Limit files
            if len(files_changed) > self.max_files_per_review:
                files_changed = files_changed[:self.max_files_per_review]
            
            # Step 2: Analyze each file & generate fixes
            yield {
                "type": "log",
                "data": self.log("info", f"🔧 Analyzing {len(files_changed)} files..."),
                "timestamp": self.logs[-1]["timestamp"]
            }
            
            fixes = []
            
            for idx, file_info in enumerate(files_changed):
                file_path = file_info["filename"]
                
                yield {
                    "type": "progress",
                    "data": {
                        "step": "analyzing_file",
                        "current": idx + 1,
                        "total": len(files_changed),
                        "file": file_path
                    },
                    "timestamp": self.logs[-1]["timestamp"]
                }
                
                # Get file diff
                diff = await self._get_file_diff(repo, base_branch, branch, file_path)
                
                if not diff:
                    continue
                
                # Analyze and generate fixes
                file_fixes = await self._analyze_and_fix(file_path, diff)
                
                if file_fixes:
                    fixes.append({
                        "file": file_path,
                        "fixes": file_fixes
                    })
            
            if not fixes:
                yield {
                    "type": "result",
                    "data": {
                        "status": "success",
                        "message": "✅ No issues found - Code looks good!",
                        "files_analyzed": len(files_changed)
                    },
                    "timestamp": self.logs[-1]["timestamp"]
                }
                return
            
            # Step 3: Create review branch (if auto_fix enabled)
            if not self.auto_fix:
                yield {
                    "type": "result",
                    "data": {
                        "status": "success",
                        "message": f"Found {len(fixes)} files with issues (auto_fix disabled)",
                        "fixes": fixes
                    },
                    "timestamp": self.logs[-1]["timestamp"]
                }
                return
            
            # Generate unique review branch name
            import time
            timestamp = int(time.time())
            review_branch_name = f"{self.review_branch_prefix}{branch.replace('/', '-')}-{timestamp}"
            
            yield {
                "type": "log",
                "data": self.log("info", f"🌿 Creating review branch: {review_branch_name}"),
                "timestamp": self.logs[-1]["timestamp"]
            }
            
            # Create branch from target branch
            await self.call_mcp("github", "create_branch", {
                "repo": repo,
                "new_branch": review_branch_name,
                "from_branch": branch
            })
            
            # Step 4: Apply fixes & commit
            yield {
                "type": "log",
                "data": self.log("info", f"💾 Applying {len(fixes)} fixes..."),
                "timestamp": self.logs[-1]["timestamp"]
            }
            
            for fix_data in fixes:
                file_path = fix_data["file"]
                file_fixes = fix_data["fixes"]
                
                # Get current file content with SHA
                file_sha = None
                try:
                    file_data = await self.call_mcp("github", "get_file_content", {
                        "repo": repo,
                        "path": file_path,
                        "ref": review_branch_name
                    })
                    current_content = file_data["content"]
                    file_sha = file_data["sha"]
                except:
                    # File might be new
                    current_content = ""
                
                # Apply fixes
                fixed_content = self._apply_fixes(current_content, file_fixes)
                
                # Commit fix
                commit_message = f"🤖 AI Review: Fix {len(file_fixes)} issues in {file_path}"
                
                update_params = {
                    "repo": repo,
                    "path": file_path,
                    "content": fixed_content,
                    "message": commit_message,
                    "branch": review_branch_name
                }
                
                if file_sha:
                    update_params["sha"] = file_sha
                
                await self.call_mcp("github", "update_file", update_params)
                
                yield {
                    "type": "progress",
                    "data": {
                        "step": "fix_applied",
                        "file": file_path,
                        "fixes_count": len(file_fixes)
                    },
                    "timestamp": self.logs[-1]["timestamp"]
                }
            
            # Step 5: Create Review PR (if enabled)
            review_pr_url = None
            
            if self.auto_create_pr:
                yield {
                    "type": "log",
                    "data": self.log("info", "📝 Creating review Pull Request..."),
                    "timestamp": self.logs[-1]["timestamp"]
                }
                
                pr_body = self._generate_pr_description(fixes, branch)
                
                review_pr = await self.call_mcp("github", "create_pull_request", {
                    "repo": repo,
                    "title": f"🤖 AI Code Review - Branch {branch}",
                    "body": pr_body,
                    "head": review_branch_name,
                    "base": branch
                })
                
                review_pr_url = review_pr.get("html_url")
                review_pr_number = review_pr.get("number")
            
            # Final result
            yield {
                "type": "result",
                "data": {
                    "status": "success",
                    "message": f"✅ Review completed! Created {len(fixes)} fixes",
                    "branch_reviewed": branch,
                    "review_branch": review_branch_name,
                    "review_pr_url": review_pr_url,
                    "fixes_applied": sum(len(f["fixes"]) for f in fixes),
                    "files_fixed": len(fixes),
                    "summary": self.get_execution_summary()
                },
                "timestamp": self.logs[-1]["timestamp"]
            }
            
        except Exception as e:
            self.log("error", f"Branch review failed: {str(e)}")
            yield {
                "type": "error",
                "data": {
                    "message": str(e),
                    "summary": self.get_execution_summary()
                },
                "timestamp": self.logs[-1]["timestamp"]
            }
            raise
    
    async def _get_changed_files(
        self,
        repo: str,
        base_branch: str,
        target_branch: str
    ) -> List[Dict[str, str]]:
        """
        Récupère la liste des fichiers modifiés entre deux branches.
        
        Returns:
            [{"filename": "path/to/file.js", "status": "modified"}, ...]
        """
        # Use GitHub API to compare branches
        import httpx
        
        url = f"https://api.github.com/repos/{repo}/compare/{base_branch}...{target_branch}"
        
        github_config = self.mcp_config.get("github", {})
        token = github_config.get("token")
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github.v3+json"
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()
            
            files = data.get("files", [])
            
            return [
                {"filename": f["filename"], "status": f["status"]}
                for f in files
            ]
    
    async def _get_file_diff(
        self,
        repo: str,
        base_branch: str,
        target_branch: str,
        file_path: str
    ) -> str:
        """
        Récupère le diff d'un fichier spécifique.
        """
        import httpx
        
        url = f"https://api.github.com/repos/{repo}/compare/{base_branch}...{target_branch}"
        
        github_config = self.mcp_config.get("github", {})
        token = github_config.get("token")
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github.v3+json"
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()
            
            files = data.get("files", [])
            
            for f in files:
                if f["filename"] == file_path:
                    return f.get("patch", "")
            
            return ""
    
    async def _analyze_and_fix(self, file_path: str, patch: str) -> List[Dict[str, Any]]:
        """
        Analyse un fichier et génère des fixes automatiques.
        
        Utilise le LLM si use_llm=True, sinon pattern-based.
        """
        if self.use_llm:
            return await self._analyze_with_llm(file_path, patch)
        else:
            return await self._analyze_with_patterns(file_path, patch)
    
    async def _analyze_with_llm(self, file_path: str, patch: str) -> List[Dict[str, Any]]:
        """
        Analyse intelligente via LLM.
        """
        self.log("debug", f"Analyzing {file_path} with LLM (model: {self.llm_model or 'default'})")
        
        # Build prompt
        system_prompt = f"""You are an expert code reviewer specialized in {self.review_focus} review.

Analyze the following code diff and provide a JSON list of issues with fixes.

For each issue, provide:
- line: line number (integer)
- issue: type of issue (string)
- original: original code line (string)
- fix: fixed code line (string, empty to delete line)

Focus areas based on review_focus={self.review_focus}:
- general: code quality, best practices, syntax
- security: vulnerabilities, input validation, auth issues
- performance: optimization opportunities, inefficiencies
- style: formatting, naming conventions, readability

Return ONLY valid JSON array, no markdown, no explanation.
Example: [{{"line": 10, "issue": "debug statement", "original": "console.log('x')", "fix": ""}}]"""

        user_prompt = f"""File: {file_path}

Diff:
```
{patch}
```

Analyze and return JSON array of fixes."""

        try:
            response = await self.call_llm(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                provider_name=self.llm_provider,
                model=self.llm_model,
                temperature=self.llm_temperature,
                max_tokens=2000
            )
            
            # Parse JSON response
            import json
            import re
            
            # Clean markdown fences if present
            clean_response = re.sub(r'```json\s*|\s*```', '', response).strip()
            
            fixes = json.loads(clean_response)
            
            if not isinstance(fixes, list):
                self.log("warning", f"LLM returned non-list response, falling back to patterns")
                return await self._analyze_with_patterns(file_path, patch)
            
            self.log("info", f"LLM found {len(fixes)} issues in {file_path}")
            return fixes
            
        except Exception as e:
            self.log("error", f"LLM analysis failed: {str(e)}, falling back to patterns")
            return await self._analyze_with_patterns(file_path, patch)
    
    async def _analyze_with_patterns(self, file_path: str, patch: str) -> List[Dict[str, Any]]:
        """
        Analyse un fichier et génère des fixes automatiques.
        """
        fixes = []
        lines = patch.split('\n')
        current_line = 0
        
        for line in lines:
            # Track line numbers
            if line.startswith('@@'):
                match = re.search(r'\+(\d+)', line)
                if match:
                    current_line = int(match.group(1))
                continue
            
            if not line.startswith('+'):
                if not line.startswith('-'):
                    current_line += 1
                continue
            
            current_line += 1
            code = line[1:]  # Remove '+'
            
            # Auto-fix patterns
            
            # Fix 1: Remove console.log / console.debug
            if re.search(r'console\.(log|debug|warn|error)\(', code):
                fixed_line = re.sub(r'console\.(log|debug|warn|error)\([^)]*\);?\s*', '', code)
                if fixed_line.strip() != code.strip():
                    fixes.append({
                        "line": current_line,
                        "issue": "Debug statement",
                        "original": code,
                        "fix": fixed_line
                    })
            
            # Fix 2: Remove print statements (Python)
            if re.search(r'^\s*print\(', code):
                fixes.append({
                    "line": current_line,
                    "issue": "Debug print",
                    "original": code,
                    "fix": ""  # Remove entirely
                })
            
            # Fix 3: Fix trailing whitespace
            if code.rstrip() != code and code.strip():
                fixes.append({
                    "line": current_line,
                    "issue": "Trailing whitespace",
                    "original": code,
                    "fix": code.rstrip()
                })
            
            # Fix 4: Add missing semicolons (JS/TS)
            if file_path.endswith(('.js', '.jsx', '.ts', '.tsx')):
                stripped = code.strip()
                if stripped and not stripped.endswith((';', '{', '}', ',', ':', '//')):
                    # Check if it's a statement that needs semicolon
                    if not re.search(r'^(if|for|while|function|class|import|export|const|let|var|return|try|catch|finally)\s', stripped):
                        if not re.search(r'=>\s*$', stripped):  # Not arrow function
                            fixes.append({
                                "line": current_line,
                                "issue": "Missing semicolon",
                                "original": code,
                                "fix": code.rstrip() + ';'
                            })
            
            # Fix 5: == → === (JS/TS)
            if file_path.endswith(('.js', '.jsx', '.ts', '.tsx')):
                if '==' in code and '===' not in code and '!==' not in code:
                    fixed_line = code.replace('==', '===').replace('!=', '!==')
                    if fixed_line != code:
                        fixes.append({
                            "line": current_line,
                            "issue": "Use strict equality",
                            "original": code,
                            "fix": fixed_line
                        })
            
            # Fix 6: var → const (JS)
            if file_path.endswith(('.js', '.jsx')):
                if re.search(r'^\s*var\s+', code):
                    fixed_line = re.sub(r'\bvar\b', 'const', code)
                    fixes.append({
                        "line": current_line,
                        "issue": "Use const instead of var",
                        "original": code,
                        "fix": fixed_line
                    })
        
        return fixes
    
    def _apply_fixes(self, content: str, fixes: List[Dict[str, Any]]) -> str:
        """
        Applique les fixes au contenu du fichier.
        """
        lines = content.split('\n')
        
        # Apply fixes in reverse order to maintain line numbers
        for fix in sorted(fixes, key=lambda x: x["line"], reverse=True):
            line_idx = fix["line"] - 1
            
            if 0 <= line_idx < len(lines):
                if fix.get("fix") == "":
                    # Remove line
                    lines.pop(line_idx)
                else:
                    # Replace line
                    lines[line_idx] = fix["fix"]
        
        return '\n'.join(lines)
    
    def _generate_pr_description(
        self,
        fixes: List[Dict[str, Any]],
        original_branch: str
    ) -> str:
        """
        Génère la description de la PR de review.
        """
        total_fixes = sum(len(f["fixes"]) for f in fixes)
        
        body = f"## 🤖 Automated Code Review\n\n"
        body += f"This PR contains automated fixes for branch `{original_branch}`\n\n"
        body += f"### 📊 Summary\n\n"
        body += f"- **Files fixed:** {len(fixes)}\n"
        body += f"- **Total fixes:** {total_fixes}\n"
        body += f"- **Review focus:** {self.review_focus}\n\n"
        body += f"### 🔧 Fixes Applied\n\n"
        
        for fix_data in fixes:
            file_path = fix_data["file"]
            file_fixes = fix_data["fixes"]
            
            body += f"#### `{file_path}`\n\n"
            
            issues_count = {}
            for fix in file_fixes:
                issue_type = fix["issue"]
                issues_count[issue_type] = issues_count.get(issue_type, 0) + 1
            
            for issue_type, count in issues_count.items():
                body += f"- {issue_type}: {count} fix(es)\n"
            
            body += "\n"
        
        body += "### ✅ Next Steps\n\n"
        body += "1. Review the changes\n"
        body += "2. Merge this PR if fixes are correct\n"
        body += "3. The changes will be applied to your branch\n\n"
        body += "---\n"
        body += "*Generated by AI Code Review Agent*"
        
        return body