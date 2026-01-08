import httpx
from typing import Dict, Any, List, Optional
import logging

logger = logging.getLogger(__name__)


class GitHubMCPServer:
    """
    MCP Server pour GitHub.
    
    Fournit des mÃ©thodes pour interagir avec GitHub API :
    - RÃ©cupÃ©rer des PRs
    - Lire des fichiers
    - CrÃ©er des commentaires
    - Lister des commits
    """
    
    def __init__(self, token: str, repo: Optional[str] = None):
        """
        Args:
            token: GitHub Personal Access Token
            repo: Repo par dÃ©faut au format "owner/repo" (optionnel)
        """
        self.token = token
        self.default_repo = repo
        self.base_url = "https://api.github.com"
        
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github.v3+json",
            "X-GitHub-Api-Version": "2022-11-28"
        }
        
        logger.info(f"GitHub MCP Server initialized for repo: {repo}")
    
    async def get_pr(self, repo: Optional[str] = None, pr_number: int = None) -> Dict[str, Any]:
        """
        RÃ©cupÃ¨re les dÃ©tails d'une Pull Request.
        
        Args:
            repo: Repo au format "owner/repo" (utilise default si None)
            pr_number: NumÃ©ro de la PR
            
        Returns:
            DÃ©tails de la PR avec fichiers modifiÃ©s
        """
        repo = repo or self.default_repo
        if not repo:
            raise ValueError("No repo specified and no default repo set")
        
        url = f"{self.base_url}/repos/{repo}/pulls/{pr_number}"
        
        async with httpx.AsyncClient() as client:
            # Get PR details
            response = await client.get(url, headers=self.headers)
            response.raise_for_status()
            pr_data = response.json()
            
            # Get PR files
            files_url = f"{url}/files"
            files_response = await client.get(files_url, headers=self.headers)
            files_response.raise_for_status()
            files_data = files_response.json()
            
            # Combine data
            pr_data['files'] = files_data
            
            logger.info(f"Retrieved PR #{pr_number} from {repo}: {len(files_data)} files changed")
            
            return pr_data
    
    async def list_prs(
        self,
        repo: Optional[str] = None,
        state: str = "open",
        per_page: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Liste les Pull Requests d'un repo.
        
        Args:
            repo: Repo au format "owner/repo"
            state: Ã‰tat des PRs (open, closed, all)
            per_page: Nombre de PRs Ã  retourner
            
        Returns:
            Liste des PRs
        """
        repo = repo or self.default_repo
        if not repo:
            raise ValueError("No repo specified and no default repo set")
        
        url = f"{self.base_url}/repos/{repo}/pulls"
        params = {"state": state, "per_page": per_page}
        
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=self.headers, params=params)
            response.raise_for_status()
            prs = response.json()
            
            logger.info(f"Retrieved {len(prs)} PRs from {repo}")
            return prs
    
    async def get_file_content(
        self,
        repo: Optional[str] = None,
        path: str = None,
        ref: str = "main"
    ) -> Dict[str, str]:
        """
        RÃ©cupÃ¨re le contenu d'un fichier avec son SHA.
        
        Args:
            repo: Repo au format "owner/repo"
            path: Chemin du fichier
            ref: Branch/commit (dÃ©faut: main)
            
        Returns:
            Dict avec content et sha: {"content": "...", "sha": "abc123"}
        """
        repo = repo or self.default_repo
        if not repo:
            raise ValueError("No repo specified and no default repo set")
        
        url = f"{self.base_url}/repos/{repo}/contents/{path}"
        params = {"ref": ref}
        
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=self.headers, params=params)
            response.raise_for_status()
            data = response.json()
            
            # Decode base64 content
            import base64
            content = base64.b64decode(data['content']).decode('utf-8')
            sha = data['sha']
            
            logger.info(f"Retrieved file {path} from {repo} ({len(content)} chars, sha: {sha[:7]})")
            return {"content": content, "sha": sha}
    
    async def create_pr_comment(
        self,
        repo: Optional[str] = None,
        pr_number: int = None,
        body: str = None
    ) -> Dict[str, Any]:
        """
        CrÃ©e un commentaire gÃ©nÃ©ral sur une PR.
        
        Args:
            repo: Repo au format "owner/repo"
            pr_number: NumÃ©ro de la PR
            body: Contenu du commentaire
            
        Returns:
            DonnÃ©es du commentaire crÃ©Ã©
        """
        repo = repo or self.default_repo
        if not repo:
            raise ValueError("No repo specified and no default repo set")
        
        url = f"{self.base_url}/repos/{repo}/issues/{pr_number}/comments"
        payload = {"body": body}
        
        async with httpx.AsyncClient() as client:
            response = await client.post(url, headers=self.headers, json=payload)
            response.raise_for_status()
            comment = response.json()
            
            logger.info(f"Created comment on PR #{pr_number} in {repo}")
            return comment
    
    async def create_review_comment(
        self,
        repo: Optional[str] = None,
        pr_number: int = None,
        commit_id: str = None,
        path: str = None,
        line: int = None,
        body: str = None
    ) -> Dict[str, Any]:
        """
        CrÃ©e un commentaire inline sur une ligne spÃ©cifique.
        
        Args:
            repo: Repo au format "owner/repo"
            pr_number: NumÃ©ro de la PR
            commit_id: SHA du commit Ã  commenter
            path: Chemin du fichier
            line: NumÃ©ro de ligne
            body: Contenu du commentaire
            
        Returns:
            DonnÃ©es du commentaire crÃ©Ã©
        """
        repo = repo or self.default_repo
        if not repo:
            raise ValueError("No repo specified and no default repo set")
        
        url = f"{self.base_url}/repos/{repo}/pulls/{pr_number}/comments"
        payload = {
            "body": body,
            "commit_id": commit_id,
            "path": path,
            "line": line
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(url, headers=self.headers, json=payload)
            response.raise_for_status()
            comment = response.json()
            
            logger.info(f"Created review comment on {path}:{line} in PR #{pr_number}")
            return comment
    
    async def list_commits(
        self,
        repo: Optional[str] = None,
        sha: str = "main",
        per_page: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Liste les commits d'un repo.
        
        Args:
            repo: Repo au format "owner/repo"
            sha: Branch/commit (dÃ©faut: main)
            per_page: Nombre de commits
            
        Returns:
            Liste des commits
        """
        repo = repo or self.default_repo
        if not repo:
            raise ValueError("No repo specified and no default repo set")
        
        url = f"{self.base_url}/repos/{repo}/commits"
        params = {"sha": sha, "per_page": per_page}
        
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=self.headers, params=params)
            response.raise_for_status()
            commits = response.json()
            
            logger.info(f"Retrieved {len(commits)} commits from {repo}")
            return commits
    
    async def get_repo_info(self, repo: Optional[str] = None) -> Dict[str, Any]:
        """
        RÃ©cupÃ¨re les infos d'un repo.
        
        Args:
            repo: Repo au format "owner/repo"
            
        Returns:
            Infos du repo
        """
        repo = repo or self.default_repo
        if not repo:
            raise ValueError("No repo specified and no default repo set")
        
        url = f"{self.base_url}/repos/{repo}"
        
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=self.headers)
            response.raise_for_status()
            repo_data = response.json()
            
            logger.info(f"Retrieved info for repo {repo}")
            return repo_data
    
    async def get_branch_ref(
        self,
        repo: Optional[str] = None,
        branch: str = "main"
    ) -> Dict[str, Any]:
        """
        RÃ©cupÃ¨re la rÃ©fÃ©rence (SHA) d'une branche.
        
        Args:
            repo: Repo au format "owner/repo"
            branch: Nom de la branche
            
        Returns:
            RÃ©fÃ©rence de la branche avec SHA
        """
        repo = repo or self.default_repo
        if not repo:
            raise ValueError("No repo specified and no default repo set")
        
        url = f"{self.base_url}/repos/{repo}/git/ref/heads/{branch}"
        
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=self.headers)
            response.raise_for_status()
            ref_data = response.json()
            
            logger.info(f"Retrieved branch ref for {branch}: {ref_data['object']['sha']}")
            return ref_data
    
    async def create_branch(
        self,
        repo: Optional[str] = None,
        new_branch: str = None,
        from_branch: str = "main"
    ) -> Dict[str, Any]:
        """
        CrÃ©e une nouvelle branche Ã  partir d'une branche existante.
        
        Args:
            repo: Repo au format "owner/repo"
            new_branch: Nom de la nouvelle branche
            from_branch: Branche source
            
        Returns:
            RÃ©fÃ©rence de la nouvelle branche
        """
        repo = repo or self.default_repo
        if not repo or not new_branch:
            raise ValueError("Repo and new_branch are required")
        
        # Get SHA of source branch
        source_ref = await self.get_branch_ref(repo, from_branch)
        source_sha = source_ref['object']['sha']
        
        # Create new branch
        url = f"{self.base_url}/repos/{repo}/git/refs"
        payload = {
            "ref": f"refs/heads/{new_branch}",
            "sha": source_sha
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(url, headers=self.headers, json=payload)
            response.raise_for_status()
            new_ref = response.json()
            
            logger.info(f"Created branch {new_branch} from {from_branch}")
            return new_ref
    
    async def update_file(
        self,
        repo: Optional[str] = None,
        path: str = None,
        content: str = None,
        message: str = None,
        branch: str = "main",
        sha: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        CrÃ©e ou met Ã  jour un fichier dans le repo.
        
        Args:
            repo: Repo au format "owner/repo"
            path: Chemin du fichier
            content: Contenu du fichier (sera encodÃ© en base64)
            message: Message de commit
            branch: Branche cible
            sha: SHA du fichier existant (pour update)
            
        Returns:
            RÃ©sultat du commit
        """
        repo = repo or self.default_repo
        if not repo or not path or not content or not message:
            raise ValueError("Repo, path, content and message are required")
        
        # Encode content to base64
        import base64
        content_b64 = base64.b64encode(content.encode('utf-8')).decode('utf-8')
        
        url = f"{self.base_url}/repos/{repo}/contents/{path}"
        payload = {
            "message": message,
            "content": content_b64,
            "branch": branch
        }
        
        if sha:
            payload["sha"] = sha
        
        async with httpx.AsyncClient() as client:
            response = await client.put(url, headers=self.headers, json=payload)
            response.raise_for_status()
            result = response.json()
            
            logger.info(f"Updated file {path} on branch {branch}")
            return result
    
    async def create_pull_request(
        self,
        repo: Optional[str] = None,
        title: str = None,
        body: str = None,
        head: str = None,
        base: str = "main"
    ) -> Dict[str, Any]:
        """
        CrÃ©e une nouvelle Pull Request.
        
        Args:
            repo: Repo au format "owner/repo"
            title: Titre de la PR
            body: Description de la PR
            head: Branche source
            base: Branche cible
            
        Returns:
            DonnÃ©es de la PR crÃ©Ã©e
        """
        repo = repo or self.default_repo
        if not repo or not title or not head:
            raise ValueError("Repo, title and head are required")
        
        url = f"{self.base_url}/repos/{repo}/pulls"
        payload = {
            "title": title,
            "body": body or "",
            "head": head,
            "base": base
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(url, headers=self.headers, json=payload)
            response.raise_for_status()
            pr_data = response.json()
            
            logger.info(f"Created PR #{pr_data['number']}: {title}")
            return pr_data
    # ========================================
    # NOUVELLES MÉTHODES POUR CODE GENERATOR
    # ========================================
    
    async def clone_repository(
        self,
        repo: Optional[str] = None,
        path: str = None,
        branch: str = "main"
    ) -> Dict[str, Any]:
        """
        Clone un repository localement via Git CLI.
        
        Args:
            repo: Repo au format "owner/repo" (utilise default si None)
            path: Chemin local où cloner
            branch: Branche à cloner (défaut: main)
        
        Returns:
            {"success": bool, "path": str, "branch": str}
        """
        import subprocess
        
        repo = repo or self.default_repo
        if not repo or not path:
            raise ValueError("Repo and path are required")
        
        # Clone avec authentification via token
        url = f"https://{self.token}@github.com/{repo}.git"
        
        try:
            result = subprocess.run(
                ["git", "clone", "-b", branch, "--single-branch", url, path],
                capture_output=True,
                text=True,
                timeout=300
            )
            
            if result.returncode != 0:
                logger.error(f"Git clone failed: {result.stderr}")
                return {
                    "success": False,
                    "error": result.stderr
                }
            
            # Configure git user pour commits futurs
            subprocess.run(
                ["git", "config", "user.email", "ai-agent@codegen.local"],
                cwd=path,
                capture_output=True
            )
            subprocess.run(
                ["git", "config", "user.name", "AI Code Generator"],
                cwd=path,
                capture_output=True
            )
            
            logger.info(f"Cloned {repo} to {path} (branch: {branch})")
            
            return {
                "success": True,
                "path": path,
                "branch": branch
            }
            
        except subprocess.TimeoutExpired:
            logger.error("Git clone timeout (5min)")
            return {
                "success": False,
                "error": "Clone timeout (5min)"
            }
        except Exception as e:
            logger.error(f"Clone error: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def get_repo_tree(
        self,
        repo: Optional[str] = None,
        recursive: bool = True,
        branch: str = "main"
    ) -> Dict[str, Any]:
        """
        Récupère l'arbre complet du repository via GitHub API.
        
        Args:
            repo: Repo au format "owner/repo" (utilise default si None)
            recursive: Récursif (défaut: True)
            branch: Branche (défaut: main)
        
        Returns:
            {
                "success": bool,
                "tree": [{"path": "...", "type": "blob|tree", "sha": "..."}, ...]
            }
        """
        repo = repo or self.default_repo
        if not repo:
            raise ValueError("No repo specified and no default repo set")
        
        try:
            # Utilise get_branch_ref() existant
            ref_data = await self.get_branch_ref(repo, branch)
            commit_sha = ref_data["object"]["sha"]
        except Exception as e:
            logger.error(f"Failed to get branch ref: {str(e)}")
            return {
                "success": False,
                "error": f"Branch {branch} not found"
            }
        
        # Get tree via API
        tree_url = f"{self.base_url}/repos/{repo}/git/trees/{commit_sha}"
        if recursive:
            tree_url += "?recursive=1"
        
        async with httpx.AsyncClient() as client:
            response = await client.get(tree_url, headers=self.headers)
            
            if response.status_code != 200:
                logger.error(f"Failed to fetch tree: {response.text}")
                return {
                    "success": False,
                    "error": "Failed to fetch tree"
                }
            
            tree_data = response.json()
            logger.info(f"Retrieved {len(tree_data.get('tree', []))} items from {repo}")
            
            return {
                "success": True,
                "tree": tree_data.get("tree", [])
            }
    
    async def commit_and_push(
        self,
        path: str,
        files: List[str],
        message: str,
        branch: str,
        create_branch: bool = False,
        from_branch: str = "main"
    ) -> Dict[str, Any]:
        """
        Commit et push des fichiers via Git CLI local.
        
        Args:
            path: Chemin local du repo cloné
            files: Liste des fichiers à commiter
            message: Message de commit
            branch: Branche cible
            create_branch: Créer la branche si n'existe pas
            from_branch: Branche source (si create_branch=True)
        
        Returns:
            {"success": bool, "commit_hash": str, "branch": str}
        """
        import subprocess
        
        try:
            # Switch/create branch
            if create_branch:
                subprocess.run(
                    ["git", "checkout", from_branch],
                    cwd=path,
                    capture_output=True,
                    check=True
                )
                result = subprocess.run(
                    ["git", "checkout", "-b", branch],
                    cwd=path,
                    capture_output=True
                )
                if result.returncode != 0:
                    logger.warning(f"Branch {branch} exists, checking out...")
                    subprocess.run(
                        ["git", "checkout", branch],
                        cwd=path,
                        capture_output=True,
                        check=True
                    )
            else:
                result = subprocess.run(
                    ["git", "checkout", branch],
                    cwd=path,
                    capture_output=True
                )
                if result.returncode != 0:
                    logger.info(f"Branch {branch} not found, creating...")
                    subprocess.run(
                        ["git", "checkout", "-b", branch],
                        cwd=path,
                        capture_output=True,
                        check=True
                    )
            
            # Add files
            for file in files:
                subprocess.run(
                    ["git", "add", file],
                    cwd=path,
                    capture_output=True,
                    check=True
                )
            
            # Commit
            result = subprocess.run(
                ["git", "commit", "-m", message],
                cwd=path,
                capture_output=True,
                text=True
            )
            
            if result.returncode != 0:
                logger.error(f"Git commit failed: {result.stderr}")
                return {
                    "success": False,
                    "error": f"Commit failed: {result.stderr}"
                }
            
            # Get commit hash
            hash_result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=path,
                capture_output=True,
                text=True,
                check=True
            )
            commit_hash = hash_result.stdout.strip()
            
            # Push
            push_result = subprocess.run(
                ["git", "push", "origin", branch],
                cwd=path,
                capture_output=True,
                text=True,
                timeout=120
            )
            
            if push_result.returncode != 0:
                if "rejected" in push_result.stderr:
                    logger.warning("Push rejected, trying force push...")
                    push_result = subprocess.run(
                        ["git", "push", "-f", "origin", branch],
                        cwd=path,
                        capture_output=True,
                        text=True,
                        timeout=120
                    )
                
                if push_result.returncode != 0:
                    logger.error(f"Git push failed: {push_result.stderr}")
                    return {
                        "success": False,
                        "error": f"Push failed: {push_result.stderr}",
                        "commit_hash": commit_hash
                    }
            
            logger.info(f"Committed and pushed to {branch}: {commit_hash[:7]}")
            
            return {
                "success": True,
                "commit_hash": commit_hash,
                "branch": branch
            }
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Git command failed: {e}")
            return {
                "success": False,
                "error": f"Git command failed: {str(e)}"
            }
        except Exception as e:
            logger.error(f"Commit and push error: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }