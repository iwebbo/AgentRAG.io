from typing import Dict, Any, AsyncGenerator, List, Optional
from uuid import UUID
from sqlalchemy.orm import Session
import logging
import re
from datetime import datetime

from app.agents.base_agent import BaseAgent

logger = logging.getLogger(__name__)

# Fichiers "clés" lus automatiquement pour contextualiser l'analyse d'un dossier / repo
KEY_FILES = (
    "README.md", "readme.md", "Dockerfile", "Chart.yaml", "values.yaml",
    "Jenkinsfile", "bitbucket-pipelines.yml", "pom.xml", "package.json",
    "pyproject.toml", "requirements.txt", "go.mod",
)
MAX_FILE_CHARS = 12000


class BitbucketAgent(BaseAgent):
    """
    Agent d'intégration Bitbucket Server (HTTP access token).

    Modes :
        read          → { "url": "https://bb/projects/K/repos/R/browse/path?at=main", "question": "..."(opt) }
                        ou { "project", "repo", "path"(opt), "ref"(opt) }
                        Fichier -> analyse LLM du fichier ; dossier/repo -> analyse LLM de l'arborescence
                        + fichiers clés (README, Dockerfile, Chart.yaml, ...).
        pull_request  → { "url": ".../pull-requests/42" } ou { "project", "repo", "pr_id" },
                        { "post_comment": false }  (review LLM du diff ; commentaire posté seulement si true)
        write         → { "url": ".../browse/path/file?at=main" ou project/repo/path/ref,
                          "instruction": "...", "branch": "feature/x"(opt), "commit_message"(opt),
                          "open_pr": false }
                        Le fichier est réécrit par le LLM puis commité sur une branche dédiée
                        (jamais sur la branche par défaut sauf config allow_push_default=true).

    Config attendue (agent.config) :
    {
        "mcp_servers": ["bitbucket"],
        "mode": "read" | "pull_request" | "write",
        "llm_provider": "...", "llm_model": "...", "llm_temperature": 0.2,
        "allow_push_default": false
    }
    """

    MCP_SERVER = "bitbucket"

    def __init__(
        self,
        agent_id: UUID,
        user_id: UUID,
        config: Dict[str, Any],
        mcp_config: Dict[str, Any],
        db: Session,
    ):
        super().__init__(agent_id, user_id, config, mcp_config, db)
        self.mode = config.get("mode", "read")
        self.allow_push_default = config.get("allow_push_default", False)
        self.llm_provider = config.get("llm_provider")
        self.llm_model = config.get("llm_model")
        self.llm_temperature = config.get("llm_temperature", 0.2)

    # ------------------------------------------------------------------ #
    # Entry point
    # ------------------------------------------------------------------ #

    async def execute(self, input_data: Dict[str, Any]) -> AsyncGenerator[Dict[str, Any], None]:
        mode = input_data.get("mode", self.mode)
        self.log("info", f"BitbucketAgent starting — mode={mode}")
        yield self._progress("init", f"Mode d'exécution : {mode}")

        try:
            if mode == "read":
                async for u in self._workflow_read(input_data):
                    yield u
            elif mode == "pull_request":
                async for u in self._workflow_pull_request(input_data):
                    yield u
            elif mode == "write":
                async for u in self._workflow_write(input_data):
                    yield u
            else:
                yield self._error(f"Unknown mode: {mode}. Expected: read|pull_request|write")
        except Exception as exc:
            self.log("error", f"BitbucketAgent failed: {exc}")
            yield self._error(str(exc))

    # ------------------------------------------------------------------ #
    # Target resolution
    # ------------------------------------------------------------------ #

    async def _resolve_target(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """URL Bitbucket OU champs explicites -> {project, repo, path, ref, pr_id}."""
        if input_data.get("url"):
            t = await self.call_mcp(self.MCP_SERVER, "parse_url", {"url": input_data["url"]})
        else:
            t = {
                "project": input_data.get("project"),
                "repo": input_data.get("repo"),
                "path": input_data.get("path", ""),
                "ref": input_data.get("ref"),
                "pr_id": input_data.get("pr_id"),
            }
        # Les champs explicites surchargent ce qui est déduit de l'URL
        for k in ("project", "repo", "path", "ref", "pr_id"):
            if input_data.get(k) not in (None, ""):
                t[k] = input_data[k]

        if not t.get("project") or not t.get("repo"):
            raise ValueError("Provide 'url' or 'project' + 'repo'")
        return t

    # ------------------------------------------------------------------ #
    # Workflows
    # ------------------------------------------------------------------ #

    async def _workflow_read(self, input_data: Dict[str, Any]):
        t = await self._resolve_target(input_data)
        question = input_data.get("question")
        project, repo, path, ref = t["project"], t["repo"], t.get("path", ""), t.get("ref")

        yield self._progress("fetch", f"Lecture : {project}/{repo}/{path} @ {ref or 'default'}")
        kind = await self.call_mcp(self.MCP_SERVER, "get_path_type", {
            "project": project, "repo": repo, "path": path, "ref": ref,
        })

        if kind == "file":
            content = await self.call_mcp(self.MCP_SERVER, "get_file_content", {
                "project": project, "repo": repo, "path": path, "ref": ref,
            })
            material = f"Fichier : {path}\n\n{content[:MAX_FILE_CHARS]}"
            meta = {"type": "file", "path": path, "chars": len(content)}
        else:
            entries = await self.call_mcp(self.MCP_SERVER, "list_directory", {
                "project": project, "repo": repo, "path": path, "ref": ref,
            })
            tree = "\n".join(
                f"{'[D]' if e['type'] == 'DIRECTORY' else '[F]'} {e['name']}" for e in entries
            )
            material = f"Dossier : /{path}\n\nContenu :\n{tree}\n"
            names = {e["name"] for e in entries if e["type"] == "FILE"}
            for key in KEY_FILES:
                if key in names:
                    fpath = f"{path.strip('/')}/{key}".lstrip("/")
                    body = await self.call_mcp(self.MCP_SERVER, "get_file_content", {
                        "project": project, "repo": repo, "path": fpath, "ref": ref,
                    })
                    material += f"\n--- {fpath} ---\n{body[:MAX_FILE_CHARS // 2]}\n"
            meta = {"type": "directory", "path": path, "entries": len(entries)}

        yield self._progress("llm", "Analyse LLM...")
        analysis = await self._llm_analyze(material, question)

        yield self._result("read", {
            "target": {"project": project, "repo": repo, "ref": ref, **meta},
            "question": question,
            "analysis": analysis,
        })

    async def _workflow_pull_request(self, input_data: Dict[str, Any]):
        t = await self._resolve_target(input_data)
        if not t.get("pr_id"):
            yield self._error("Provide a pull request URL or 'pr_id' for mode=pull_request")
            return
        project, repo, pr_id = t["project"], t["repo"], int(t["pr_id"])

        yield self._progress("fetch", f"Lecture PR #{pr_id}")
        pr = await self.call_mcp(self.MCP_SERVER, "get_pull_request", {
            "project": project, "repo": repo, "pr_id": pr_id,
        })
        diff = await self.call_mcp(self.MCP_SERVER, "get_pull_request_diff", {
            "project": project, "repo": repo, "pr_id": pr_id,
        })

        yield self._progress("llm", "Review LLM du diff...")
        material = (
            f"PR #{pr['id']} : {pr['title']}\n{pr['fromRef']} -> {pr['toRef']}\n"
            f"Description : {pr.get('description', '')}\n\nDiff :\n{diff[:MAX_FILE_CHARS * 2]}"
        )
        review = await self._llm_analyze(
            material,
            "Fais une code review : risques, bugs, problèmes de sécurité, impacts CI/CD "
            "(Docker/Helm), et recommandations priorisées.",
        )

        posted = False
        if input_data.get("post_comment", False):
            yield self._progress("publish", "Publication du commentaire sur la PR")
            await self.call_mcp(self.MCP_SERVER, "add_pull_request_comment", {
                "project": project, "repo": repo, "pr_id": pr_id,
                "text": f"**Review automatique (LLM)**\n\n{review}",
            })
            posted = True

        yield self._result("pull_request", {
            "pull_request": pr, "review": review, "comment_posted": posted,
        })

    async def _workflow_write(self, input_data: Dict[str, Any]):
        t = await self._resolve_target(input_data)
        instruction = input_data.get("instruction")
        path = (t.get("path") or "").strip("/")
        if not instruction or not path:
            yield self._error("Provide 'instruction' and a file path (url .../browse/<file> or 'path') for mode=write")
            return
        project, repo = t["project"], t["repo"]

        repo_info = await self.call_mcp(self.MCP_SERVER, "get_repository", {
            "project": project, "repo": repo,
        })
        base_ref = t.get("ref") or repo_info["default_branch"]
        base_branch = re.sub(r"^refs/heads/", "", base_ref or "")
        branch = input_data.get("branch") or (
            f"mcp/{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}-{re.sub(r'[^a-zA-Z0-9]+', '-', path)[:40].strip('-')}"
        )

        if branch == repo_info["default_branch"] and not self.allow_push_default:
            yield self._error(
                f"Push direct sur la branche par défaut '{branch}' interdit "
                "(config allow_push_default=false). Fournis 'branch'."
            )
            return

        yield self._progress("fetch", f"Lecture de {path} @ {base_branch}")
        current = await self.call_mcp(self.MCP_SERVER, "get_file_content", {
            "project": project, "repo": repo, "path": path, "ref": base_branch,
        })

        yield self._progress("llm", "Réécriture du fichier par le LLM...")
        new_content = self._strip_fences(await self._llm_revise(path, current, instruction))
        if new_content.strip() == current.strip():
            yield self._error("Le LLM n'a produit aucune modification : aucun commit créé")
            return

        yield self._progress("publish", f"Commit sur la branche {branch}")
        branches = await self.call_mcp(self.MCP_SERVER, "list_branches", {
            "project": project, "repo": repo, "filter_text": branch,
        })
        exists = any(b["displayId"] == branch for b in branches)
        if not exists:
            await self.call_mcp(self.MCP_SERVER, "create_branch", {
                "project": project, "repo": repo, "name": branch, "start_point": base_branch,
            })

        commit = await self.call_mcp(self.MCP_SERVER, "write_file", {
            "project": project, "repo": repo, "path": path, "content": new_content,
            "branch": branch,
            "message": input_data.get("commit_message") or f"chore({path}): {instruction[:72]}",
        })

        pr = None
        if input_data.get("open_pr", False):
            yield self._progress("publish", "Création de la pull request")
            pr = await self.call_mcp(self.MCP_SERVER, "create_pull_request", {
                "project": project, "repo": repo,
                "title": input_data.get("pr_title") or f"{path}: {instruction[:72]}",
                "from_branch": branch, "to_branch": base_branch,
                "description": f"Modification automatique.\n\nInstruction : {instruction}",
            })

        yield self._result("write", {
            "target": {"project": project, "repo": repo, "path": path},
            "branch": branch, "base_branch": base_branch,
            "commit": commit, "pull_request": pr,
            "content_preview": new_content[:300],
        })

    # ------------------------------------------------------------------ #
    # LLM helpers
    # ------------------------------------------------------------------ #

    async def _llm_analyze(self, material: str, question: Optional[str]) -> str:
        instruction = (
            f"Réponds précisément à cette question : « {question} »"
            if question else
            "Fais une synthèse claire (objectif, structure, points clés) et signale "
            "les risques ou incohérences éventuels."
        )
        messages = [
            {"role": "system", "content": (
                "Tu es un ingénieur DevOps/logiciel senior. Tu analyses du contenu issu "
                "d'un dépôt Bitbucket (code, Dockerfile, Helm chart, CI/CD). Sois factuel et concis."
            )},
            {"role": "user", "content": f"{material}\n\n{instruction}"},
        ]
        return await self.call_llm(
            messages, provider_name=self.llm_provider, model=self.llm_model,
            temperature=self.llm_temperature, max_tokens=1200,
        )

    async def _llm_revise(self, path: str, content: str, instruction: str) -> str:
        messages = [
            {"role": "system", "content": (
                "Tu es un ingénieur senior. Tu modifies un fichier de dépôt en respectant "
                "strictement l'instruction, sans toucher au reste. Réponds UNIQUEMENT avec le "
                "contenu complet du fichier modifié : pas de commentaire, pas de bloc markdown."
            )},
            {"role": "user", "content": (
                f"Fichier : {path}\n\nContenu actuel :\n{content}\n\n"
                f"Instruction : {instruction}"
            )},
        ]
        return await self.call_llm(
            messages, provider_name=self.llm_provider, model=self.llm_model,
            temperature=self.llm_temperature, max_tokens=4000,
        )

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #

    @staticmethod
    def _strip_fences(text: str) -> str:
        """Retire un éventuel bloc ``` englobant renvoyé par le LLM."""
        m = re.match(r"^\s*```[a-zA-Z0-9_+-]*\n(.*?)\n```\s*$", text, re.DOTALL)
        return (m.group(1) + "\n") if m else text

    def _result(self, mode: str, data: Dict[str, Any]) -> Dict[str, Any]:
        data = {"mode": mode, **data, "metadata": {"timestamp": datetime.utcnow().isoformat()}}
        return {"type": "result", "data": data, "timestamp": datetime.utcnow().isoformat()}

    def _progress(self, step: str, message: str) -> Dict[str, Any]:
        return {
            "type": "progress",
            "data": {"step": step, "message": message},
            "timestamp": datetime.utcnow().isoformat(),
        }

    def _error(self, message: str) -> Dict[str, Any]:
        self.log("error", message)
        return {
            "type": "error",
            "data": {"error": message},
            "timestamp": datetime.utcnow().isoformat(),
        }