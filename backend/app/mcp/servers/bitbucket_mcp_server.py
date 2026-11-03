"""
BitbucketMCPServer — MCP Server pour Bitbucket Server / Data Center (REST API 1.0).

Auth :
  - Header "Authorization: Bearer <HTTP_ACCESS_TOKEN>"
  - Token généré dans Bitbucket : Profil > Manage account > HTTP access tokens
    (ou Project/Repository settings > HTTP access tokens).
  - Doc : https://confluence.atlassian.com/bitbucketserver/http-access-tokens-939515499.html

Matrice de permissions (token) -> méthodes MCP utilisables :
  Repository read   : list_projects, list_repositories, get_repository, list_branches,
                      list_directory, get_path_type, get_file_content, list_commits,
                      list_pull_requests, get_pull_request, get_pull_request_diff
  Repository write  : + create_branch, write_file, create_pull_request, add_pull_request_comment
                      (le merge de PR n'est PAS possible avec un token write : volontairement non exposé)
  Repository admin  : non requis par ce MCP.

Endpoints utilisés :
  /rest/api/1.0/...            (API cœur)
  /rest/branch-utils/1.0/...   (création de branche)

Config attendue dans mcp_config["bitbucket"] :
{
    "base_url": "https://bitbucket.mondomaine.fr",   # sans /rest, contexte inclus si présent (ex: /bitbucket)
    "token": "<HTTP access token>",
    "verify_ssl": true,                              # optionnel, défaut true
    "ca_bundle": "/etc/ssl/certs/internal-ca.pem",   # optionnel, prioritaire sur verify_ssl
    "timeout": 30                                    # optionnel
}
"""
import logging
from typing import Any, Dict, List, Optional
from urllib.parse import quote, urlparse, parse_qs, unquote

import httpx

logger = logging.getLogger(__name__)

DEFAULT_PAGE_SIZE = 100
MAX_PAGES = 50  # garde-fou anti-boucle de pagination


class BitbucketMCPServer:
    def __init__(
        self,
        base_url: str,
        token: str,
        verify_ssl: bool = True,
        ca_bundle: Optional[str] = None,
        timeout: float = 30.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_url = f"{self.base_url}/rest/api/1.0"
        self.branch_utils_url = f"{self.base_url}/rest/branch-utils/1.0"
        self.token = token
        self.verify: Any = ca_bundle if ca_bundle else verify_ssl
        self.timeout = timeout
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
        }
        logger.info(f"Bitbucket MCP Server initialized: {self.base_url}")

    # ─────────────────────────────────────────────────────────────────────
    # Cœur HTTP
    # ─────────────────────────────────────────────────────────────────────

    async def _request(
        self,
        method: str,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
        files: Optional[Dict[str, Any]] = None,
        text: bool = False,
    ) -> Any:
        """Exécute une requête et remonte le message d'erreur Bitbucket (errors[].message)."""
        headers = dict(self.headers)
        if text:
            headers["Accept"] = "text/plain, */*"

        async with httpx.AsyncClient(verify=self.verify, timeout=self.timeout) as client:
            r = await client.request(
                method, url, headers=headers, params=params, json=json, files=files
            )

        if r.status_code >= 400:
            try:
                errs = r.json().get("errors", [])
                msg = "; ".join(e.get("message", str(e)) for e in errs) or r.text[:300]
            except ValueError:
                msg = r.text[:300]
            logger.error(f"Bitbucket {method} {url} -> HTTP {r.status_code}: {msg}")
            raise Exception(f"Bitbucket HTTP {r.status_code}: {msg}")

        if text:
            return r.text
        if r.status_code == 204 or not r.content:
            return {}
        return r.json()

    async def _paginate(
        self, url: str, params: Optional[Dict[str, Any]] = None, limit: int = 1000
    ) -> List[Dict[str, Any]]:
        """Parcourt une ressource paginée Bitbucket (isLastPage / nextPageStart)."""
        results: List[Dict[str, Any]] = []
        start = 0
        for _ in range(MAX_PAGES):
            p = dict(params or {})
            p.update({"start": start, "limit": min(DEFAULT_PAGE_SIZE, limit - len(results))})
            data = await self._request("GET", url, params=p)
            results.extend(data.get("values", []))
            if data.get("isLastPage", True) or len(results) >= limit:
                break
            start = data.get("nextPageStart", start + DEFAULT_PAGE_SIZE)
        return results[:limit]

    def _repo_url(self, project: str, repo: str) -> str:
        return f"{self.api_url}/projects/{quote(project, safe='~')}/repos/{quote(repo, safe='')}"

    @staticmethod
    def _path(path: str) -> str:
        return quote((path or "").strip("/"), safe="/")

    # ─────────────────────────────────────────────────────────────────────
    # Helpers URL
    # ─────────────────────────────────────────────────────────────────────

    async def parse_url(self, url: str) -> Dict[str, Any]:
        """
        Extrait project/repo/path/ref/pr_id d'une URL Bitbucket Server. Formats supportés :
          .../projects/KEY/repos/SLUG[/browse/<path>][?at=<ref>]
          .../projects/KEY/repos/SLUG/pull-requests/<id>[/...]
          .../users/NAME/repos/SLUG/...          (repo personnel -> project "~NAME")
          .../scm/KEY/SLUG.git                   (URL de clone HTTP)
        """
        parsed = urlparse(url)
        segs = [unquote(s) for s in parsed.path.split("/") if s]
        out: Dict[str, Any] = {
            "project": None, "repo": None, "path": "", "ref": None, "pr_id": None,
        }

        for i, s in enumerate(segs):
            if s in ("projects", "users") and i + 3 < len(segs) + 0 and segs[i + 2] == "repos":
                out["project"] = segs[i + 1] if s == "projects" else f"~{segs[i + 1]}"
                out["repo"] = segs[i + 3]
                rest = segs[i + 4:]
                if rest[:1] == ["browse"]:
                    out["path"] = "/".join(rest[1:])
                elif rest[:1] == ["pull-requests"] and len(rest) > 1 and rest[1].isdigit():
                    out["pr_id"] = int(rest[1])
                break
            if s == "scm" and i + 2 < len(segs):
                out["project"] = segs[i + 1].upper() if not segs[i + 1].startswith("~") else segs[i + 1]
                repo = segs[i + 2]
                out["repo"] = repo[:-4] if repo.endswith(".git") else repo
                break

        if not out["project"] or not out["repo"]:
            raise ValueError(f"Unsupported Bitbucket URL: {url}")

        at = parse_qs(parsed.query).get("at")
        if at:
            out["ref"] = at[0]
        return out

    # ─────────────────────────────────────────────────────────────────────
    # Lecture (token : Repository read)
    # ─────────────────────────────────────────────────────────────────────

    async def list_projects(self, limit: int = 100) -> List[Dict[str, Any]]:
        values = await self._paginate(f"{self.api_url}/projects", limit=limit)
        return [{"key": p["key"], "name": p.get("name"), "description": p.get("description", "")}
                for p in values]

    async def list_repositories(self, project: str, limit: int = 200) -> List[Dict[str, Any]]:
        values = await self._paginate(
            f"{self.api_url}/projects/{quote(project, safe='~')}/repos", limit=limit
        )
        return [{"slug": r["slug"], "name": r.get("name"), "state": r.get("state"),
                 "archived": r.get("archived", False)} for r in values]

    async def get_repository(self, project: str, repo: str) -> Dict[str, Any]:
        data = await self._request("GET", self._repo_url(project, repo))
        default = None
        try:
            default = (await self._request("GET", f"{self._repo_url(project, repo)}/branches/default")).get("displayId")
        except Exception:
            pass  # repo vide : pas de branche par défaut
        clone = {l["name"]: l["href"] for l in data.get("links", {}).get("clone", [])}
        return {
            "slug": data["slug"], "name": data.get("name"), "project": data["project"]["key"],
            "default_branch": default, "clone": clone, "public": data.get("public", False),
        }

    async def list_branches(
        self, project: str, repo: str, filter_text: str = "", limit: int = 100
    ) -> List[Dict[str, Any]]:
        params = {"filterText": filter_text} if filter_text else {}
        values = await self._paginate(f"{self._repo_url(project, repo)}/branches", params, limit)
        return [{"id": b["id"], "displayId": b["displayId"],
                 "latestCommit": b.get("latestCommit"), "isDefault": b.get("isDefault", False)}
                for b in values]

    async def get_path_type(
        self, project: str, repo: str, path: str = "", ref: Optional[str] = None
    ) -> str:
        """Retourne 'directory' ou 'file' (lève si le chemin n'existe pas)."""
        params = {"limit": 1}
        if ref:
            params["at"] = ref
        data = await self._request(
            "GET", f"{self._repo_url(project, repo)}/browse/{self._path(path)}", params=params
        )
        return "directory" if "children" in data else "file"

    async def list_directory(
        self, project: str, repo: str, path: str = "", ref: Optional[str] = None, limit: int = 500
    ) -> List[Dict[str, Any]]:
        """Liste le contenu d'un dossier (pas récursif)."""
        entries: List[Dict[str, Any]] = []
        start = 0
        for _ in range(MAX_PAGES):
            params: Dict[str, Any] = {"start": start, "limit": min(DEFAULT_PAGE_SIZE, limit - len(entries))}
            if ref:
                params["at"] = ref
            data = await self._request(
                "GET", f"{self._repo_url(project, repo)}/browse/{self._path(path)}", params=params
            )
            children = data.get("children")
            if children is None:
                raise ValueError(f"'{path}' is a file, not a directory")
            for c in children.get("values", []):
                entries.append({"name": c["path"]["name"], "type": c["type"], "size": c.get("size")})
            if children.get("isLastPage", True) or len(entries) >= limit:
                break
            start = children.get("nextPageStart", start + DEFAULT_PAGE_SIZE)
        return entries

    async def get_file_content(
        self, project: str, repo: str, path: str, ref: Optional[str] = None
    ) -> str:
        """Contenu brut d'un fichier (endpoint /raw)."""
        params = {"at": ref} if ref else None
        return await self._request(
            "GET", f"{self._repo_url(project, repo)}/raw/{self._path(path)}",
            params=params, text=True,
        )

    async def list_commits(
        self, project: str, repo: str, ref: Optional[str] = None,
        path: Optional[str] = None, limit: int = 25,
    ) -> List[Dict[str, Any]]:
        params: Dict[str, Any] = {}
        if ref:
            params["until"] = ref
        if path:
            params["path"] = path.strip("/")
        values = await self._paginate(f"{self._repo_url(project, repo)}/commits", params, limit)
        return [{"id": c["id"], "displayId": c["displayId"],
                 "message": c.get("message", ""), "author": c.get("author", {}).get("name"),
                 "authorTimestamp": c.get("authorTimestamp")} for c in values]

    async def list_pull_requests(
        self, project: str, repo: str, state: str = "OPEN", limit: int = 50
    ) -> List[Dict[str, Any]]:
        values = await self._paginate(
            f"{self._repo_url(project, repo)}/pull-requests", {"state": state}, limit
        )
        return [self._slim_pr(p) for p in values]

    async def get_pull_request(self, project: str, repo: str, pr_id: int) -> Dict[str, Any]:
        data = await self._request("GET", f"{self._repo_url(project, repo)}/pull-requests/{pr_id}")
        pr = self._slim_pr(data)
        pr["description"] = data.get("description", "")
        return pr

    async def get_pull_request_diff(self, project: str, repo: str, pr_id: int) -> str:
        """Diff unifié brut de la PR (suffixe .diff)."""
        return await self._request(
            "GET", f"{self._repo_url(project, repo)}/pull-requests/{pr_id}.diff", text=True
        )

    @staticmethod
    def _slim_pr(p: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "id": p["id"], "title": p.get("title"), "state": p.get("state"),
            "author": p.get("author", {}).get("user", {}).get("name"),
            "fromRef": p.get("fromRef", {}).get("displayId"),
            "toRef": p.get("toRef", {}).get("displayId"),
            "updatedDate": p.get("updatedDate"),
        }

    # ─────────────────────────────────────────────────────────────────────
    # Écriture (token : Repository write)
    # ─────────────────────────────────────────────────────────────────────

    async def create_branch(
        self, project: str, repo: str, name: str, start_point: str
    ) -> Dict[str, Any]:
        """Crée une branche depuis start_point (branche, tag ou commit id)."""
        data = await self._request(
            "POST",
            f"{self.branch_utils_url}/projects/{quote(project, safe='~')}/repos/{quote(repo, safe='')}/branches",
            json={"name": name, "startPoint": start_point},
        )
        logger.info(f"Created branch {name} from {start_point} in {project}/{repo}")
        return {"id": data.get("id"), "displayId": data.get("displayId"),
                "latestCommit": data.get("latestCommit")}

    async def write_file(
        self,
        project: str,
        repo: str,
        path: str,
        content: str,
        branch: str,
        message: str,
        source_branch: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Crée ou modifie un fichier via un commit sur `branch`.
        - Fichier existant : sourceCommitId (dernier commit du fichier sur la branche)
          est requis par Bitbucket pour la détection de conflit -> récupéré automatiquement.
        - source_branch : si `branch` n'existe pas, Bitbucket la crée depuis source_branch.
        """
        path = path.strip("/")
        source_commit: Optional[str] = None
        try:
            commits = await self.list_commits(project, repo, ref=branch, path=path, limit=1)
            if commits:
                source_commit = commits[0]["id"]
        except Exception as exc:
            logger.info(f"No history for {path} on {branch} (new file or new branch): {exc}")

        form: Dict[str, Any] = {
            "content": (None, content),
            "message": (None, message),
            "branch": (None, branch),
        }
        if source_commit:
            form["sourceCommitId"] = (None, source_commit)
        if source_branch:
            form["sourceBranch"] = (None, source_branch)

        data = await self._request(
            "PUT", f"{self._repo_url(project, repo)}/browse/{self._path(path)}", files=form
        )
        logger.info(f"Wrote {project}/{repo}:{path} on {branch} ({data.get('id')})")
        return {"commit": data.get("id"), "displayId": data.get("displayId"),
                "branch": branch, "path": path}

    async def create_pull_request(
        self, project: str, repo: str, title: str, from_branch: str, to_branch: str,
        description: str = "",
    ) -> Dict[str, Any]:
        def ref(branch: str) -> Dict[str, Any]:
            bid = branch if branch.startswith("refs/") else f"refs/heads/{branch}"
            return {"id": bid, "repository": {"slug": repo, "project": {"key": project}}}

        data = await self._request(
            "POST", f"{self._repo_url(project, repo)}/pull-requests",
            json={"title": title, "description": description,
                  "fromRef": ref(from_branch), "toRef": ref(to_branch)},
        )
        pr = self._slim_pr(data)
        pr["url"] = (data.get("links", {}).get("self") or [{}])[0].get("href")
        return pr

    async def add_pull_request_comment(
        self, project: str, repo: str, pr_id: int, text: str
    ) -> Dict[str, Any]:
        data = await self._request(
            "POST", f"{self._repo_url(project, repo)}/pull-requests/{pr_id}/comments",
            json={"text": text},
        )
        return {"id": data.get("id"), "pr_id": pr_id}