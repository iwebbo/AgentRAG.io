from typing import Dict, Any, AsyncGenerator, List, Optional
import re
import json
import tempfile
import shutil
import asyncio
from uuid import UUID
from sqlalchemy.orm import Session
from pathlib import Path

from app.agents.base_agent import BaseAgent
from app.models import Project, Document


class CodeGeneratorAgent(BaseAgent):
    """
    Agent de génération de code basé sur un repository (RAG context).
    
    Inspiré de Roocode mais amélioré avec:
    - RAG automatique sur le repo complet
    - LLM génération via context
    - Tests unitaires auto via MCP
    - Lint/format auto via MCP
    - Git commit/push auto
    
    Workflow:
    1. Fetch repo complet via GitHub MCP
    2. Embed tout le code dans Project RAG
    3. Génère code via LLM + RAG context
    4. Lance tests unitaires (pytest, jest, etc.)
    5. Lint/format le code généré
    6. Commit & push auto sur nouvelle branche
    7. Crée PR optionnellement
    
    Config attendue:
    {
        "project_id": "uuid",              // Project RAG (créé auto si absent)
        "mcp_servers": ["github", "test_runner", "linter"],
        "repo": "owner/repo",              // Repo GitHub à cloner
        "target_branch": "ai-feature",     // Branche de travail
        "base_branch": "main",             // Branche de base
        "auto_test": true,                 // Lancer tests avant commit
        "auto_lint": true,                 // Lint/format auto
        "auto_commit": true,               // Commit auto
        "auto_create_pr": false,           // Créer PR auto
        "test_framework": "auto",          // pytest|jest|junit|auto
        "language": "auto"                 // python|javascript|typescript|auto
    }
    
    MCP Config:
    {
        "github": {
            "token": "ghp_...",
            "repo": "owner/repo"
        }
    }
    
    Input data:
    {
        "prompt": "Add OAuth2 authentication with JWT",
        "target_files": ["backend/auth.py"],  // Optionnel: fichiers à modifier
        "create_new_files": true,             // Autoriser création de fichiers
        "test_mode": true,                    // Lancer tests avant commit
        "commit_message": "feat: add OAuth2"  // Message commit custom
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
        self.repo = config.get("repo") or mcp_config.get("github", {}).get("repo")
        self.target_branch = config.get("target_branch", "ai-feature")
        self.base_branch = config.get("base_branch", "main")
        self.auto_test = config.get("auto_test", True)
        self.auto_lint = config.get("auto_lint", True)
        self.auto_commit = config.get("auto_commit", True)
        self.auto_create_pr = config.get("auto_create_pr", False)
        self.test_framework = config.get("test_framework", "auto")
        self.language = config.get("language", "auto")
        self.max_context_chunks = config.get("max_context_chunks", 15)
        
        # LLM config
        self.llm_provider = config.get("llm_provider")
        self.llm_model = config.get("llm_model")
        self.llm_temperature = config.get("llm_temperature", 0.2)
        
        # Temp workspace
        self.temp_dir: Optional[str] = None
        
        if not self.repo:
            raise ValueError("Missing 'repo' in config or mcp_config.github.repo")
    
    async def execute(self, input_data: Dict[str, Any]) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Exécute la génération de code.
        
        input_data:
        {
            "prompt": "Add OAuth2 authentication",
            "target_files": ["backend/auth.py"],  // optionnel
            "create_new_files": true,
            "test_mode": true,
            "commit_message": "feat: OAuth2"
        }
        """
        try:
            prompt = input_data.get("prompt")
            if not prompt:
                raise ValueError("Missing required field: prompt")
            
            target_files = input_data.get("target_files", [])
            create_new = input_data.get("create_new_files", True)
            test_mode = input_data.get("test_mode", self.auto_test)
            commit_msg = input_data.get("commit_message")
            
            # Step 1: Fetch ou créer Project RAG
            yield {
                "type": "log",
                "data": self.log("info", f"🔍 Initializing RAG context for {self.repo}"),
                "timestamp": self.logs[-1]["timestamp"]
            }
            
            project = await self._get_or_create_project()
            
            yield {
                "type": "progress",
                "data": {
                    "step": "rag_initialized",
                    "project_id": str(project.id),
                    "repo": self.repo
                },
                "timestamp": self.logs[-1]["timestamp"]
            }
            
            # Step 2: Clone repo localement
            yield {
                "type": "log",
                "data": self.log("info", f"📦 Cloning repository {self.repo}"),
                "timestamp": self.logs[-1]["timestamp"]
            }
            
            repo_path = await self._clone_repo()
            
            # Step 3: Générer code via LLM + RAG
            yield {
                "type": "log",
                "data": self.log("info", f"🧠 Generating code with LLM + RAG context"),
                "timestamp": self.logs[-1]["timestamp"]
            }
            
            code_changes = await self._generate_code(
                project_id=project.id,
                prompt=prompt,
                repo_path=repo_path,
                target_files=target_files,
                create_new_files=create_new
            )
            
            if not code_changes:
                yield {
                    "type": "result",
                    "data": {
                        "status": "success",
                        "message": "⚠️ No code changes generated",
                        "project_id": str(project.id)
                    },
                    "timestamp": self.logs[-1]["timestamp"]
                }
                return
            
            yield {
                "type": "progress",
                "data": {
                    "step": "code_generated",
                    "files_count": len(code_changes["changes"]),
                    "changes": code_changes["changes"]
                },
                "timestamp": self.logs[-1]["timestamp"]
            }
            
            # Step 4: Appliquer les changements
            yield {
                "type": "log",
                "data": self.log("info", f"✏️ Applying {len(code_changes['changes'])} file changes"),
                "timestamp": self.logs[-1]["timestamp"]
            }
            
            modified_files = await self._apply_changes(repo_path, code_changes["changes"])
            
            # Step 5: Tests unitaires (si activé ET si test_runner disponible)
            test_results = None
            if test_mode and "test_runner" in self.mcp_servers:
                yield {
                    "type": "log",
                    "data": self.log("info", f"🧪 Running tests ({self.test_framework})"),
                    "timestamp": self.logs[-1]["timestamp"]
                }
                
                test_results = await self._run_tests(repo_path)
                
                if not test_results.get("passed", False):
                    yield {
                        "type": "result",
                        "data": {
                            "status": "failed",
                            "reason": "Tests failed",
                            "test_results": test_results,
                            "modified_files": modified_files
                        },
                        "timestamp": self.logs[-1]["timestamp"]
                    }
                    return
                
                yield {
                    "type": "progress",
                    "data": {
                        "step": "tests_passed",
                        "test_results": test_results
                    },
                    "timestamp": self.logs[-1]["timestamp"]
                }
            elif test_mode and "test_runner" not in self.mcp_servers:
                self.log("warning", "test_mode=true but test_runner MCP not enabled, skipping tests")
            
            # Step 6: Lint/Format (si activé ET si linter disponible)
            if self.auto_lint and "linter" in self.mcp_servers:
                yield {
                    "type": "log",
                    "data": self.log("info", f"🔧 Linting and formatting code"),
                    "timestamp": self.logs[-1]["timestamp"]
                }
                
                await self._lint_and_format(repo_path, modified_files)
            elif self.auto_lint and "linter" not in self.mcp_servers:
                self.log("warning", "auto_lint=true but linter MCP not enabled, skipping lint")
            
            # Step 7: Git commit/push
            commit_hash = None
            pr_url = None
            
            if self.auto_commit:
                yield {
                    "type": "log",
                    "data": self.log("info", f"📤 Committing to branch '{self.target_branch}'"),
                    "timestamp": self.logs[-1]["timestamp"]
                }
                
                final_commit_msg = commit_msg or f"feat: {prompt[:50]}"
                
                commit_result = await self._commit_and_push(
                    repo_path,
                    modified_files,
                    commit_msg=final_commit_msg
                )
                
                commit_hash = commit_result.get("commit_hash")
                
                # Créer PR si demandé
                if self.auto_create_pr and commit_hash:
                    yield {
                        "type": "log",
                        "data": self.log("info", f"🔀 Creating Pull Request"),
                        "timestamp": self.logs[-1]["timestamp"]
                    }
                    
                    pr_url = await self._create_pr(
                        prompt=prompt,
                        modified_files=modified_files,
                        test_results=test_results
                    )
            
            # Final result
            yield {
                "type": "result",
                "data": {
                    "status": "success",
                    "project_id": str(project.id),
                    "repo": self.repo,
                    "branch": self.target_branch,
                    "modified_files": modified_files,
                    "code_changes": code_changes["changes"],
                    "test_results": test_results,
                    "commit_hash": commit_hash,
                    "pr_url": pr_url,
                    "tokens_used": self.tokens_used,
                    "summary": code_changes.get("summary", "")
                },
                "timestamp": self.logs[-1]["timestamp"]
            }
            
        except Exception as e:
            self.log("error", f"Code generation failed: {str(e)}")
            yield {
                "type": "error",
                "data": {"error": str(e)},
                "timestamp": self.logs[-1]["timestamp"]
            }
        
        finally:
            # Cleanup temp directory
            if self.temp_dir and Path(self.temp_dir).exists():
                shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    async def _get_or_create_project(self) -> Project:
        """
        Récupère ou crée un Project RAG pour le repo.
        Option 1 recommandée: 1 Project par repo partagé entre agents.
        """
        # Check si project existe déjà pour ce repo
        existing = self.db.query(Project).filter(
            Project.user_id == self.user_id,
            Project.name == f"CodeGen: {self.repo}"
        ).first()
        
        if existing:
            self.log("info", f"Using existing project {existing.id}")
            return existing
        
        # Créer nouveau project
        project = Project(
            user_id=self.user_id,
            name=f"AgentCodeGenerator: {self.repo}",
            description=f"Auto-generated RAG context for {self.repo}"
        )
        self.db.add(project)
        self.db.flush()
        
        self.log("info", f"Created new project {project.id}")
        
        # Fetch repo content via GitHub MCP et embed
        await self._embed_repository(project.id)
        
        self.db.commit()
        return project
    
    async def _embed_repository(self, project_id: UUID):
        """
        Fetch le repo complet et embed tous les fichiers dans le RAG.
        """
        self.log("info", f"Fetching repository files from {self.repo}")
        
        # Get repo tree via GitHub MCP (méthode ajoutée par extension)
        try:
            tree_data = await self.call_mcp("github", "get_repo_tree", {
                "repo": self.repo,
                "recursive": True,
                "branch": self.base_branch
            })
            
            if not tree_data.get("success"):
                raise Exception(tree_data.get("error", "Failed to fetch tree"))
            
            files = tree_data.get("tree", [])
            code_files = [
                f for f in files 
                if f.get("type") == "blob" 
                and self._is_code_file(f.get("path", ""))
            ]
            
            self.log("info", f"Found {len(code_files)} code files to embed")
            
            # Fetch et embed chaque fichier (par batch pour performance)
            batch_size = 10
            for i in range(0, len(code_files), batch_size):
                batch = code_files[i:i+batch_size]
                
                for file_info in batch:
                    file_path = file_info["path"]
                    
                    # Fetch file content via GitHub MCP (méthode EXISTANTE)
                    content_data = await self.call_mcp("github", "get_file_content", {
                        "repo": self.repo,
                        "path": file_path,
                        "ref": self.base_branch
                    })
                    
                    content = content_data.get("content", "")
                    
                    if not content:
                        continue
                    
                    # Detect language
                    language = self._detect_language(file_path)
                    
                    # Create document in project
                    doc = Document(
                        project_id=project_id,
                        name=file_path,
                        content=content,
                        metadata={
                            "path": file_path,
                            "language": language,
                            "repo": self.repo,
                            "size": len(content)
                        }
                    )
                    self.db.add(doc)
                    self.db.flush()
                    
                    # Embed via vector store
                    query_embedding = self.embeddings.encode_single(content)
                    self.vector_store.add(
                        project_id=str(project_id),
                        document_id=str(doc.id),
                        text=content,
                        embedding=query_embedding,
                        metadata={
                            "path": file_path,
                            "language": language
                        }
                    )
            
            self.db.commit()
            self.log("info", f"Embedded {len(code_files)} files into RAG")
            
        except Exception as e:
            self.log("error", f"Failed to embed repository: {str(e)}")
            raise
    
    def _is_code_file(self, path: str) -> bool:
        """Filtre les fichiers de code pertinents."""
        code_extensions = {
            '.py', '.js', '.jsx', '.ts', '.tsx', '.java', '.go', '.rs',
            '.cpp', '.c', '.h', '.hpp', '.cs', '.php', '.rb', '.swift',
            '.kt', '.scala', '.sh', '.sql', '.yaml', '.yml', '.json',
            '.md', '.txt', '.vue', '.html', '.css', '.scss'
        }
        
        # Exclure certains dossiers
        exclude_dirs = {
            'node_modules', '__pycache__', '.git', 'venv', 'dist', 
            'build', 'target', '.next', '.cache'
        }
        
        for excluded in exclude_dirs:
            if f'/{excluded}/' in path or path.startswith(excluded):
                return False
        
        ext = Path(path).suffix.lower()
        return ext in code_extensions
    
    def _detect_language(self, file_path: str) -> str:
        """Détecte le langage depuis l'extension."""
        ext_map = {
            '.py': 'python',
            '.js': 'javascript',
            '.jsx': 'javascript',
            '.ts': 'typescript',
            '.tsx': 'typescript',
            '.java': 'java',
            '.go': 'go',
            '.rs': 'rust',
            '.cpp': 'cpp',
            '.c': 'c',
            '.rb': 'ruby',
            '.php': 'php',
            '.swift': 'swift',
            '.kt': 'kotlin',
            '.vue': 'vue'
        }
        ext = Path(file_path).suffix.lower()
        return ext_map.get(ext, 'unknown')
    
    async def _clone_repo(self) -> str:
        """Clone le repo dans un répertoire temporaire."""
        self.temp_dir = tempfile.mkdtemp(prefix="codegen_")
        
        try:
            # Clone via GitHub MCP (méthode ajoutée par extension)
            result = await self.call_mcp("github", "clone_repository", {
                "repo": self.repo,
                "path": self.temp_dir,
                "branch": self.base_branch
            })
            
            if not result.get("success"):
                raise Exception(result.get("error", "Clone failed"))
            
            self.log("info", f"Repository cloned to {self.temp_dir}")
            return self.temp_dir
            
        except Exception as e:
            self.log("error", f"Failed to clone repository: {str(e)}")
            raise
    
    async def _generate_code(
        self,
        project_id: UUID,
        prompt: str,
        repo_path: str,
        target_files: List[str],
        create_new_files: bool
    ) -> Dict[str, Any]:
        """
        Génère le code via LLM avec RAG context.
        """
        # RAG search pour contexte pertinent
        context_chunks = await self.get_rag_context(
            query=prompt,
            top_k=self.max_context_chunks
        )
        
        self.log("info", f"Retrieved {len(context_chunks)} relevant context chunks")
        
        # Lire les target_files existants si spécifiés
        existing_code = {}
        if target_files:
            for file_path in target_files:
                full_path = Path(repo_path) / file_path
                if full_path.exists():
                    with open(full_path, 'r', encoding='utf-8') as f:
                        existing_code[file_path] = f.read()
        
        # Build LLM prompt
        system_prompt = self._build_generation_prompt(
            context_chunks=context_chunks,
            existing_code=existing_code,
            create_new_files=create_new_files
        )
        
        user_prompt = f"""Task: {prompt}

Target files: {', '.join(target_files) if target_files else 'Auto-detect'}

Generate the necessary code changes following the repository's patterns and best practices."""
        
        # Call LLM
        try:
            response = await self.call_llm(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                provider_name=self.llm_provider,
                model=self.llm_model,
                temperature=self.llm_temperature,
                max_tokens=4000
            )
            
            # Parse JSON response
            parsed = self._parse_code_response(response)
            return parsed
            
        except Exception as e:
            self.log("error", f"LLM code generation failed: {str(e)}")
            raise
    
    def _build_generation_prompt(
        self,
        context_chunks: List[Dict[str, Any]],
        existing_code: Dict[str, str],
        create_new_files: bool
    ) -> str:
        """Build le prompt système pour la génération."""
        
        context_text = "\n\n".join([
            f"File: {chunk['metadata'].get('path', 'unknown')}\n```\n{chunk['content'][:500]}\n```"
            for chunk in context_chunks[:10]
        ])
        
        existing_text = ""
        if existing_code:
            existing_text = "\n\n".join([
                f"File: {path}\n```\n{content}\n```"
                for path, content in existing_code.items()
            ])
        
        prompt = f"""You are an expert code generator. Your task is to generate clean, production-ready code.

Repository Context (most relevant files):
{context_text}

Existing Code to Modify:
{existing_text or "No existing files specified"}

Rules:
1. Follow the repository's coding patterns and conventions
2. Generate complete, working code (not snippets)
3. Include proper imports, error handling, and documentation
4. Match the existing code style
5. {'Create new files if needed' if create_new_files else 'Only modify existing files'}
6. Return ONLY valid JSON, no markdown fences, no explanation

Response Format (JSON only):
{{
  "summary": "Brief description of changes",
  "changes": [
    {{
      "file": "path/to/file.py",
      "action": "create|modify|delete",
      "content": "FULL FILE CONTENT HERE",
      "explanation": "What changed and why"
    }}
  ]
}}

CRITICAL: Return complete file contents in "content", not diffs or snippets."""
        
        return prompt
    
    def _parse_code_response(self, response: str) -> Dict[str, Any]:
        """Parse la réponse JSON du LLM."""
        # Clean markdown fences
        clean = re.sub(r'```json\s*|\s*```', '', response).strip()
        
        try:
            parsed = json.loads(clean)
            
            if not isinstance(parsed, dict) or "changes" not in parsed:
                raise ValueError("Invalid response format")
            
            if not isinstance(parsed["changes"], list):
                raise ValueError("'changes' must be a list")
            
            return parsed
            
        except json.JSONDecodeError as e:
            self.log("error", f"Failed to parse JSON response: {str(e)}")
            raise ValueError(f"Invalid JSON from LLM: {str(e)}")
    
    async def _apply_changes(
        self,
        repo_path: str,
        changes: List[Dict[str, Any]]
    ) -> List[str]:
        """Applique les changements de code aux fichiers."""
        modified_files = []
        
        for change in changes:
            file_path = change["file"]
            action = change["action"]
            content = change.get("content", "")
            
            full_path = Path(repo_path) / file_path
            
            try:
                if action == "delete":
                    if full_path.exists():
                        full_path.unlink()
                        modified_files.append(file_path)
                        self.log("info", f"Deleted {file_path}")
                
                elif action == "create":
                    full_path.parent.mkdir(parents=True, exist_ok=True)
                    with open(full_path, 'w', encoding='utf-8') as f:
                        f.write(content)
                    modified_files.append(file_path)
                    self.log("info", f"Created {file_path}")
                
                elif action == "modify":
                    with open(full_path, 'w', encoding='utf-8') as f:
                        f.write(content)
                    modified_files.append(file_path)
                    self.log("info", f"Modified {file_path}")
                
            except Exception as e:
                self.log("error", f"Failed to {action} {file_path}: {str(e)}")
        
        return modified_files
    
    async def _run_tests(self, repo_path: str) -> Dict[str, Any]:
        """Lance les tests unitaires via MCP test_runner."""
        try:
            result = await self.call_mcp("test_runner", "run_tests", {
                "path": repo_path,
                "framework": self.test_framework
            })
            
            passed = result.get("passed", False)
            self.log("info" if passed else "warning", 
                    f"Tests {'passed' if passed else 'failed'}: {result.get('summary', '')}")
            
            return result
            
        except Exception as e:
            self.log("warning", f"Test execution failed: {str(e)}")
            return {
                "passed": False,
                "error": str(e),
                "summary": "Test execution failed"
            }
    
    async def _lint_and_format(self, repo_path: str, files: List[str]):
        """Lint et format les fichiers via MCP linter."""
        for file_path in files:
            try:
                full_path = str(Path(repo_path) / file_path)
                
                await self.call_mcp("linter", "format_file", {
                    "path": full_path,
                    "auto_fix": True
                })
                
                self.log("info", f"Formatted {file_path}")
                
            except Exception as e:
                self.log("warning", f"Failed to format {file_path}: {str(e)}")
    
    async def _commit_and_push(
        self,
        repo_path: str,
        files: List[str],
        commit_msg: str
    ) -> Dict[str, Any]:
        """Commit et push via GitHub MCP (extension)."""
        try:
            result = await self.call_mcp("github", "commit_and_push", {
                "path": repo_path,
                "files": files,
                "message": commit_msg,
                "branch": self.target_branch,
                "create_branch": True,
                "from_branch": self.base_branch
            })
            
            if not result.get("success"):
                raise Exception(result.get("error", "Commit/push failed"))
            
            self.log("info", f"Committed to {self.target_branch}: {result.get('commit_hash', '')[:7]}")
            return result
            
        except Exception as e:
            self.log("error", f"Failed to commit: {str(e)}")
            raise
    
    async def _create_pr(
        self,
        prompt: str,
        modified_files: List[str],
        test_results: Optional[Dict[str, Any]]
    ) -> Optional[str]:
        """Crée une Pull Request via GitHub MCP (méthode EXISTANTE)."""
        try:
            pr_body = self._generate_pr_description(prompt, modified_files, test_results)
            
            result = await self.call_mcp("github", "create_pull_request", {
                "repo": self.repo,
                "title": f"🤖 {prompt[:60]}",
                "body": pr_body,
                "head": self.target_branch,
                "base": self.base_branch
            })
            
            pr_url = result.get("html_url", "")
            self.log("info", f"Created PR: {pr_url}")
            return pr_url
            
        except Exception as e:
            self.log("error", f"Failed to create PR: {str(e)}")
            return None
    
    def _generate_pr_description(
        self,
        prompt: str,
        modified_files: List[str],
        test_results: Optional[Dict[str, Any]]
    ) -> str:
        """Génère la description de la PR."""
        body = f"## 🤖 AI Generated Code\n\n"
        body += f"**Prompt:** {prompt}\n\n"
        body += f"### 📋 Summary\n\n"
        body += f"- **Files modified:** {len(modified_files)}\n"
        body += f"- **Generated by:** CodeGeneratorAgent\n"
        
        if test_results:
            status = "✅ Passed" if test_results.get("passed") else "❌ Failed"
            body += f"- **Tests:** {status}\n"
        
        body += f"\n### 📝 Files Changed\n\n"
        for file in modified_files:
            body += f"- `{file}`\n"
        
        if test_results and test_results.get("passed"):
            body += f"\n### ✅ Test Results\n\n"
            body += f"```\n{test_results.get('summary', 'All tests passed')}\n```\n"
        
        body += f"\n---\n*Generated by AI CodeGenerator Agent*"
        return body