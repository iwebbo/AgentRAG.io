"""
GiteaMCPServer — MCP Server pour Gitea self-hosted.

API Gitea est compatible Swagger/OpenAPI et très proche de GitHub API v3.
Différences clés vs GitHub :
  - base_url = http(s)://<host>/api/v1  (pas api.github.com)
  - Auth header : token <TOKEN>  (pas Bearer)
  - Pull Requests → /repos/{owner}/{repo}/pulls  (identique)
  - Contents API → /repos/{owner}/{repo}/contents/{path}  (identique)
  - Git refs → /repos/{owner}/{repo}/git/refs  (identique)
  - Clone URL → http(s)://<host>/<owner>/<repo>.git

Méthodes exposées (identiques au GitHubMCPServer pour rester compatible
avec CodeGeneratorAgent et BranchCodeReviewAgent) :
  - get_pr / list_prs
  - get_file_content / update_file
  - get_branch_ref / create_branch
  - create_pr_comment / create_review_comment
  - create_pull_request
  - list_commits / get_repo_info
  - clone_repository / commit_and_push
  - get_repo_tree
"""
import base64
import subprocess
import httpx
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


class GiteaMCPServer:
    """
    MCP Server pour Gitea self-hosted.

    Config attendue dans mcp_config["gitea"] :
    {
        "url":   "http://192.168.1.10:3000",   # URL de l'instance Gitea (sans trailing slash)
        "token": "your_gitea_token",            # Token API Gitea
        "repo":  "owner/repo"                  # Repo par défaut (optionnel)
    }
    """

    def __init__(self, url: str, token: str, repo: Optional[str] = None):
        """
        Args:
            url:   Base URL de l'instance Gitea, ex: http://192.168.1.10:3000
            token: Token API Gitea (Settings → Applications → Generate Token)
            repo:  Repo par défaut au format "owner/repo" (optionnel)
        """
        self.gitea_url = url.rstrip("/")
        self.token = token
        self.default_repo = repo
        self.base_url = f"{self.gitea_url}/api/v1"

        # Gitea utilise "token <TOKEN>" contrairement à GitHub "Bearer <TOKEN>"
        self.headers = {
            "Authorization": f"token {token}",
            "Content-Type":  "application/json",
            "Accept":        "application/json",
        }

        logger.info(f"Gitea MCP Server initialized: {self.gitea_url} (repo: {repo})")

    # ─────────────────────────────────────────────────────────────────────────
    # Pull Requests
    # ─────────────────────────────────────────────────────────────────────────

    async def get_pr(
        self,
        repo: Optional[str] = None,
        pr_number: int = None,
    ) -> Dict[str, Any]:
        """Récupère les détails d'une Pull Request avec ses fichiers modifiés."""
        repo = repo or self.default_repo
        if not repo:
            raise ValueError("No repo specified and no default repo set")

        async with httpx.AsyncClient(verify=False) as client:
            # PR details
            url = f"{self.base_url}/repos/{repo}/pulls/{pr_number}"
            r = await client.get(url, headers=self.headers)
            r.raise_for_status()
            pr_data = r.json()

            # Files changed (Gitea: /repos/{owner}/{repo}/pulls/{index}/files)
            files_url = f"{self.base_url}/repos/{repo}/pulls/{pr_number}/files"
            rf = await client.get(files_url, headers=self.headers)
            if rf.status_code == 200:
                pr_data["files"] = rf.json()
            else:
                pr_data["files"] = []

        logger.info(f"Retrieved PR #{pr_number} from {repo}: {len(pr_data['files'])} files")
        return pr_data

    async def list_prs(
        self,
        repo: Optional[str] = None,
        state: str = "open",
        per_page: int = 10,
    ) -> List[Dict[str, Any]]:
        """Liste les Pull Requests d'un repo."""
        repo = repo or self.default_repo
        if not repo:
            raise ValueError("No repo specified and no default repo set")

        url = f"{self.base_url}/repos/{repo}/pulls"
        params = {"state": state, "limit": per_page}

        async with httpx.AsyncClient(verify=False) as client:
            r = await client.get(url, headers=self.headers, params=params)
            r.raise_for_status()
            prs = r.json()

        logger.info(f"Retrieved {len(prs)} PRs from {repo}")
        return prs

    # ─────────────────────────────────────────────────────────────────────────
    # Contents (fichiers)
    # ─────────────────────────────────────────────────────────────────────────

    async def get_file_content(
        self,
        repo: Optional[str] = None,
        path: str = None,
        ref: str = "main",
    ) -> Dict[str, str]:
        """Récupère le contenu d'un fichier avec son SHA."""
        repo = repo or self.default_repo
        if not repo or not path:
            raise ValueError("Repo and path are required")

        url = f"{self.base_url}/repos/{repo}/contents/{path}"
        params = {"ref": ref}

        async with httpx.AsyncClient(verify=False) as client:
            r = await client.get(url, headers=self.headers, params=params)
            r.raise_for_status()
            data = r.json()

        content = base64.b64decode(data["content"]).decode("utf-8")
        sha = data["sha"]
        logger.info(f"Retrieved file {path} from {repo} ({len(content)} chars, sha: {sha[:7]})")
        return {"content": content, "sha": sha}

    async def update_file(
        self,
        repo: Optional[str] = None,
        path: str = None,
        content: str = None,
        message: str = None,
        branch: str = "main",
        sha: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Crée ou met à jour un fichier dans le repo."""
        repo = repo or self.default_repo
        if not repo or not path or not content or not message:
            raise ValueError("Repo, path, content and message are required")

        content_b64 = base64.b64encode(content.encode("utf-8")).decode("utf-8")
        url = f"{self.base_url}/repos/{repo}/contents/{path}"
        payload: Dict[str, Any] = {
            "message": message,
            "content": content_b64,
            "branch":  branch,
        }
        if sha:
            payload["sha"] = sha

        async with httpx.AsyncClient(verify=False) as client:
            r = await client.put(url, headers=self.headers, json=payload)
            r.raise_for_status()
            result = r.json()

        logger.info(f"Updated file {path} on branch {branch}")
        return result

    # ─────────────────────────────────────────────────────────────────────────
    # Branches & refs
    # ─────────────────────────────────────────────────────────────────────────

    async def get_branch_ref(
        self,
        repo: Optional[str] = None,
        branch: str = "main",
    ) -> Dict[str, Any]:
        """Récupère la référence (SHA) d'une branche."""
        repo = repo or self.default_repo
        if not repo:
            raise ValueError("No repo specified and no default repo set")

        url = f"{self.base_url}/repos/{repo}/branches/{branch}"

        async with httpx.AsyncClient(verify=False) as client:
            r = await client.get(url, headers=self.headers)
            r.raise_for_status()
            data = r.json()

        # Normalise au format GitHub pour compatibilité CodeGeneratorAgent
        sha = data["commit"]["id"]
        logger.info(f"Retrieved branch ref for {branch}: {sha[:7]}")
        return {"ref": f"refs/heads/{branch}", "object": {"sha": sha}}

    async def create_branch(
        self,
        repo: Optional[str] = None,
        new_branch: str = None,
        from_branch: str = "main",
    ) -> Dict[str, Any]:
        """Crée une nouvelle branche à partir d'une branche existante."""
        repo = repo or self.default_repo
        if not repo or not new_branch:
            raise ValueError("Repo and new_branch are required")

        ref_data = await self.get_branch_ref(repo, from_branch)
        source_sha = ref_data["object"]["sha"]

        url = f"{self.base_url}/repos/{repo}/branches"
        payload = {"new_branch_name": new_branch, "old_branch_name": from_branch}

        async with httpx.AsyncClient(verify=False) as client:
            r = await client.post(url, headers=self.headers, json=payload)
            r.raise_for_status()
            result = r.json()

        logger.info(f"Created branch {new_branch} from {from_branch} (sha: {source_sha[:7]})")
        return result

    # ─────────────────────────────────────────────────────────────────────────
    # Commentaires PR
    # ─────────────────────────────────────────────────────────────────────────

    async def create_pr_comment(
        self,
        repo: Optional[str] = None,
        pr_number: int = None,
        body: str = None,
    ) -> Dict[str, Any]:
        """Crée un commentaire général sur une PR."""
        repo = repo or self.default_repo
        if not repo or not pr_number or not body:
            raise ValueError("Repo, pr_number and body are required")

        # Gitea : commentaires PR via /issues/{index}/comments
        url = f"{self.base_url}/repos/{repo}/issues/{pr_number}/comments"
        payload = {"body": body}

        async with httpx.AsyncClient(verify=False) as client:
            r = await client.post(url, headers=self.headers, json=payload)
            r.raise_for_status()
            comment = r.json()

        logger.info(f"Created comment on PR #{pr_number} in {repo}")
        return comment

    async def create_review_comment(
        self,
        repo: Optional[str] = None,
        pr_number: int = None,
        commit_id: str = None,
        path: str = None,
        line: int = None,
        body: str = None,
    ) -> Dict[str, Any]:
        """Crée un commentaire inline sur une ligne spécifique d'une PR."""
        repo = repo or self.default_repo
        if not repo or not pr_number:
            raise ValueError("Repo and pr_number are required")

        url = f"{self.base_url}/repos/{repo}/pulls/{pr_number}/reviews"
        payload = {
            "body": body or "",
            "comments": [{"path": path, "line": line, "body": body}],
            "commit_id": commit_id,
        }

        async with httpx.AsyncClient(verify=False) as client:
            r = await client.post(url, headers=self.headers, json=payload)
            r.raise_for_status()
            result = r.json()

        logger.info(f"Created review comment on {path}:{line} in PR #{pr_number}")
        return result

    # ─────────────────────────────────────────────────────────────────────────
    # Pull Request create
    # ─────────────────────────────────────────────────────────────────────────

    async def create_pull_request(
        self,
        repo: Optional[str] = None,
        title: str = None,
        body: str = None,
        head: str = None,
        base: str = "main",
    ) -> Dict[str, Any]:
        """Crée une Pull Request."""
        repo = repo or self.default_repo
        if not repo or not title or not head:
            raise ValueError("Repo, title and head are required")

        url = f"{self.base_url}/repos/{repo}/pulls"
        payload = {
            "title": title,
            "body":  body or "",
            "head":  head,
            "base":  base,
        }

        async with httpx.AsyncClient(verify=False) as client:
            r = await client.post(url, headers=self.headers, json=payload)
            r.raise_for_status()
            pr_data = r.json()

        logger.info(f"Created PR #{pr_data['number']}: {title}")
        return {**pr_data, "html_url": f"{self.gitea_url}/{repo}/pulls/{pr_data['number']}"}

    # ─────────────────────────────────────────────────────────────────────────
    # Commits & repo info
    # ─────────────────────────────────────────────────────────────────────────

    async def list_commits(
        self,
        repo: Optional[str] = None,
        sha: str = "main",
        per_page: int = 10,
    ) -> List[Dict[str, Any]]:
        """Liste les commits d'un repo."""
        repo = repo or self.default_repo
        if not repo:
            raise ValueError("No repo specified and no default repo set")

        url = f"{self.base_url}/repos/{repo}/commits"
        params = {"sha": sha, "limit": per_page}

        async with httpx.AsyncClient(verify=False) as client:
            r = await client.get(url, headers=self.headers, params=params)
            r.raise_for_status()
            commits = r.json()

        logger.info(f"Retrieved {len(commits)} commits from {repo}")
        return commits

    async def get_repo_info(self, repo: Optional[str] = None) -> Dict[str, Any]:
        """Récupère les infos d'un repo."""
        repo = repo or self.default_repo
        if not repo:
            raise ValueError("No repo specified and no default repo set")

        url = f"{self.base_url}/repos/{repo}"

        async with httpx.AsyncClient(verify=False) as client:
            r = await client.get(url, headers=self.headers)
            r.raise_for_status()
            repo_data = r.json()

        logger.info(f"Retrieved info for repo {repo}")
        return repo_data

    # ─────────────────────────────────────────────────────────────────────────
    # Clone & Git local (identique GitHub — diff uniquement sur l'URL de clone)
    # ─────────────────────────────────────────────────────────────────────────

    async def clone_repository(
        self,
        repo: Optional[str] = None,
        path: str = None,
        branch: str = "main",
    ) -> Dict[str, Any]:
        """Clone un repository Gitea localement via Git CLI."""
        repo = repo or self.default_repo
        if not repo or not path:
            raise ValueError("Repo and path are required")

        # URL Gitea avec auth token : http://token@host/owner/repo.git
        clone_url = f"{self.gitea_url}/{repo}.git"
        # Injecter le token dans l'URL (basic auth ou token@ selon config Gitea)
        from urllib.parse import urlparse, urlunparse
        parsed = urlparse(clone_url)
        authed_url = urlunparse(parsed._replace(netloc=f"{self.token}@{parsed.netloc}"))

        try:
            result = subprocess.run(
                ["git", "clone", "-b", branch, "--single-branch", authed_url, path],
                capture_output=True,
                text=True,
                timeout=300,
            )

            if result.returncode != 0:
                # Essai sans --single-branch si la branche n'existe pas encore
                result = subprocess.run(
                    ["git", "clone", authed_url, path],
                    capture_output=True,
                    text=True,
                    timeout=300,
                )
                if result.returncode != 0:
                    logger.error(f"Git clone failed: {result.stderr}")
                    return {"success": False, "error": result.stderr}

            # Configure git user pour commits IA
            for cmd in [
                ["git", "config", "user.email", "ai-agent@codegen.local"],
                ["git", "config", "user.name",  "AI Code Generator (Gitea)"],
            ]:
                subprocess.run(cmd, cwd=path, capture_output=True)

            logger.info(f"Cloned {repo} to {path} (branch: {branch})")
            return {"success": True, "path": path, "branch": branch}

        except subprocess.TimeoutExpired:
            return {"success": False, "error": "Clone timeout (5min)"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def commit_and_push(
        self,
        path: str,
        files: List[str],
        message: str,
        branch: str,
        create_branch: bool = False,
        from_branch: str = "main",
    ) -> Dict[str, Any]:
        """Commit et push des fichiers via Git CLI local (identique GitHub)."""
        try:
            # Switch/create branch
            if create_branch:
                subprocess.run(["git", "checkout", from_branch], cwd=path, capture_output=True)
                result = subprocess.run(
                    ["git", "checkout", "-b", branch], cwd=path, capture_output=True
                )
                if result.returncode != 0:
                    logger.warning(f"Branch {branch} exists, checking out...")
                    subprocess.run(
                        ["git", "checkout", branch], cwd=path, capture_output=True, check=True
                    )
            else:
                result = subprocess.run(
                    ["git", "checkout", branch], cwd=path, capture_output=True
                )
                if result.returncode != 0:
                    subprocess.run(
                        ["git", "checkout", "-b", branch], cwd=path,
                        capture_output=True, check=True,
                    )

            # Add files
            for f in files:
                subprocess.run(["git", "add", f], cwd=path, capture_output=True, check=True)

            # Commit
            result = subprocess.run(
                ["git", "commit", "-m", message],
                cwd=path, capture_output=True, text=True,
            )
            if result.returncode != 0:
                return {"success": False, "error": f"Commit failed: {result.stderr}"}

            # Commit hash
            commit_hash = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=path, capture_output=True, text=True, check=True,
            ).stdout.strip()

            # Push
            push_result = subprocess.run(
                ["git", "push", "origin", branch],
                cwd=path, capture_output=True, text=True, timeout=120,
            )
            if push_result.returncode != 0:
                if "rejected" in push_result.stderr:
                    push_result = subprocess.run(
                        ["git", "push", "-f", "origin", branch],
                        cwd=path, capture_output=True, text=True, timeout=120,
                    )
                if push_result.returncode != 0:
                    return {
                        "success": False,
                        "error": f"Push failed: {push_result.stderr}",
                        "commit_hash": commit_hash,
                    }

            logger.info(f"Committed and pushed to {branch}: {commit_hash[:7]}")
            return {"success": True, "commit_hash": commit_hash, "branch": branch}

        except subprocess.CalledProcessError as e:
            return {"success": False, "error": f"Git command failed: {str(e)}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def get_repo_tree(
        self,
        repo: Optional[str] = None,
        recursive: bool = True,
        branch: str = "main",
    ) -> Dict[str, Any]:
        """Récupère l'arbre complet du repository via Gitea API."""
        repo = repo or self.default_repo
        if not repo:
            raise ValueError("No repo specified and no default repo set")

        try:
            ref_data = await self.get_branch_ref(repo, branch)
            commit_sha = ref_data["object"]["sha"]
        except Exception as e:
            logger.error(f"Failed to get branch ref: {e}")
            return {"success": False, "error": f"Branch {branch} not found"}

        # Gitea git/trees endpoint
        tree_url = f"{self.base_url}/repos/{repo}/git/trees/{commit_sha}"
        params = {"recursive": "1"} if recursive else {}

        async with httpx.AsyncClient(verify=False) as client:
            r = await client.get(tree_url, headers=self.headers, params=params)
            if r.status_code != 200:
                logger.error(f"Failed to fetch tree: {r.text}")
                return {"success": False, "error": "Failed to fetch tree"}
            tree_data = r.json()

        tree = tree_data.get("tree", [])
        logger.info(f"Retrieved {len(tree)} items from {repo}")
        return {"success": True, "tree": tree}