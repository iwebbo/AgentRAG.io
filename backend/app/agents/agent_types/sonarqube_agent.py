"""
SonarQubeAgent — agent d'audit sécurité & de remédiation assistée par LLM.

S'appuie sur le SonarQubeMCPServer (auth par token API, identique au token CI/CD).

Config attendue (agent.config) :
{
    "mcp_servers": ["sonarqube"],
    "mode": "projects" | "overview" | "issues" | "hotspots" | "remediate",
    "analyze": true,                 # passer les résultats au LLM (défaut true)
    "page_size": 50,                 # résultats par page
    "max_remediations": 5,           # nb max d'issues corrigées par exécution
    "snippet_context": 15,           # lignes de code autour de l'issue
    "use_rag": false,                # injecter le contexte RAG du projet lié
    "project_id": "<uuid>",          # projet RAG (requis si use_rag=true)
    "llm_provider": "lmstudio",
    "llm_model": "qwen3.5-4b-...",
    "llm_temperature": 0.2
}

Input attendu (input_data) :
    mode=projects   → {}  |  { "query": "backend" }
    mode=overview   → { "project_key": "my-project", "branch": "main" }
    mode=issues     → { "project_key": "my-project", "types": ["VULNERABILITY"],
                        "severities": ["BLOCKER","CRITICAL"], "page_size": 50 }
    mode=hotspots   → { "project_key": "my-project", "status": "TO_REVIEW" }
    mode=remediate  → { "project_key": "my-project" }            # top N vulnérabilités
                    | { "issue_keys": ["AY7x...", "AY8z..."] }   # issues ciblées
"""
from typing import Any, AsyncGenerator, Dict, List, Optional
from uuid import UUID
from datetime import datetime
import logging

from sqlalchemy.orm import Session

from app.agents.base_agent import BaseAgent

logger = logging.getLogger(__name__)

VALID_MODES = ("projects", "overview", "issues", "hotspots", "remediate")
SEVERITY_ORDER = {"BLOCKER": 0, "CRITICAL": 1, "MAJOR": 2, "MINOR": 3, "INFO": 4}


class SonarQubeAgent(BaseAgent):
    """Agent SonarQube : inventaire, audit des vulnérabilités et remédiation LLM."""

    MCP_SERVER = "sonarqube"

    def __init__(
        self,
        agent_id: UUID,
        user_id: UUID,
        config: Dict[str, Any],
        mcp_config: Dict[str, Any],
        db: Session,
    ):
        super().__init__(agent_id, user_id, config, mcp_config, db)
        self.mode = config.get("mode", "projects")
        self.analyze = config.get("analyze", True)
        self.page_size = config.get("page_size", 50)
        self.max_remediations = config.get("max_remediations", 5)
        self.snippet_context = config.get("snippet_context", 15)
        self.use_rag = config.get("use_rag", False)

    # ------------------------------------------------------------------ #
    # Main entry point
    # ------------------------------------------------------------------ #

    async def execute(self, input_data: Dict[str, Any]) -> AsyncGenerator[Dict[str, Any], None]:
        mode = input_data.get("mode", self.mode)

        self.log("info", f"SonarQubeAgent starting — mode={mode}")
        yield self._progress("init", f"Mode d'exécution : {mode}")

        try:
            # Validation du token dès le démarrage — évite des erreurs opaques plus loin
            auth = await self.call_mcp(self.MCP_SERVER, "validate_auth", {})
            if not auth.get("valid"):
                yield self._error(
                    f"SonarQube token invalide sur {auth.get('base_url')} "
                    f"(auth_mode={auth.get('auth_mode')}). Vérifie mcp_config.sonarqube.token"
                )
                return
            yield self._progress("auth", f"Token validé ({auth.get('auth_mode')})")

            if mode == "projects":
                async for update in self._workflow_projects(input_data):
                    yield update

            elif mode == "overview":
                async for update in self._workflow_overview(input_data):
                    yield update

            elif mode == "issues":
                async for update in self._workflow_issues(input_data):
                    yield update

            elif mode == "hotspots":
                async for update in self._workflow_hotspots(input_data):
                    yield update

            elif mode == "remediate":
                async for update in self._workflow_remediate(input_data):
                    yield update

            else:
                yield self._error(f"Unknown mode: {mode}. Expected: {'|'.join(VALID_MODES)}")

        except Exception as exc:
            self.log("error", f"SonarQubeAgent failed: {exc}")
            yield self._error(str(exc))

    # ------------------------------------------------------------------ #
    # Workflows
    # ------------------------------------------------------------------ #

    async def _workflow_projects(self, input_data: Dict[str, Any]):
        """Inventaire des projets disponibles sur l'instance SonarQube."""
        query = input_data.get("query")
        page = input_data.get("page", 1)
        page_size = input_data.get("page_size", self.page_size)

        self.log("info", f"📋 Listing projects (q={query!r})")
        yield self._progress("projects", "Récupération des projets SonarQube...")

        raw = await self.call_mcp(self.MCP_SERVER, "list_projects", {
            "query": query,
            "page": page,
            "page_size": page_size,
        })
        projects = raw.get("projects", [])
        self.log("info", f"✅ {raw.get('total', 0)} projects found")
        yield self._progress("projects_done", f"{raw.get('total', 0)} projets trouvés")

        # Enrichissement quality gate si demandé (1 appel par projet — désactivé par défaut)
        if input_data.get("with_quality_gate") and projects:
            yield self._progress("quality_gate", "Récupération des quality gates...")
            for project in projects:
                try:
                    gate = await self.call_mcp(self.MCP_SERVER, "get_quality_gate", {
                        "project_key": project["key"],
                    })
                    project["quality_gate"] = gate.get("status")
                except Exception as exc:  # projet jamais analysé, permissions…
                    self.log("warning", f"Quality gate unavailable for {project['key']}: {exc}")
                    project["quality_gate"] = None

        yield self._result({
            "mode": "projects",
            "query": query,
            "total": raw.get("total", 0),
            "page": raw.get("page", page),
            "page_size": raw.get("page_size", page_size),
            "source": raw.get("source"),
            "projects": projects,
        })

    async def _workflow_overview(self, input_data: Dict[str, Any]):
        """Vue 360° d'un projet : quality gate + mesures + facettes d'issues + hotspots."""
        project_key = input_data.get("project_key")
        if not project_key:
            yield self._error("Missing 'project_key' for mode=overview")
            return

        branch = input_data.get("branch")
        in_new_code = input_data.get("in_new_code_period")

        self.log("info", f"🔎 Overview project={project_key} branch={branch}")
        yield self._progress("quality_gate", "Lecture de la quality gate...")
        quality_gate = await self._safe_call("get_quality_gate", {
            "project_key": project_key, "branch": branch,
        }, default={})

        yield self._progress("measures", "Lecture des métriques...")
        measures = await self._safe_call("get_measures", {
            "component_key": project_key, "branch": branch,
        }, default={})

        yield self._progress("issues", "Agrégation des issues...")
        summary = await self._safe_call("get_issues_summary", {
            "project_key": project_key, "branch": branch, "in_new_code_period": in_new_code,
        }, default={})

        yield self._progress("hotspots", "Lecture des security hotspots...")
        hotspots = await self._safe_call("list_security_hotspots", {
            "project_key": project_key, "status": "TO_REVIEW", "branch": branch, "page_size": 10,
        }, default={})

        branches = await self._safe_call("list_branches", {"project_key": project_key}, default={})

        analysis = None
        if self.analyze:
            yield self._progress("llm", "Analyse LLM de la posture sécurité...")
            analysis = await self._llm_overview(project_key, quality_gate, measures, summary, hotspots)

        yield self._result({
            "mode": "overview",
            "project_key": project_key,
            "branch": branch,
            "quality_gate": quality_gate,
            "measures": measures.get("measures", {}),
            "issues_summary": summary,
            "hotspots": {
                "total": hotspots.get("total", 0),
                "top": hotspots.get("hotspots", [])[:10],
            },
            "branches": branches.get("branches", []),
            "analysis": analysis,
        })

    async def _workflow_issues(self, input_data: Dict[str, Any]):
        """Liste filtrée des issues / vulnérabilités d'un projet."""
        project_key = input_data.get("project_key")
        if not project_key:
            yield self._error("Missing 'project_key' for mode=issues")
            return

        types = self._as_list(input_data.get("types"))
        severities = self._as_list(input_data.get("severities"))
        statuses = self._as_list(input_data.get("statuses"))
        rules = self._as_list(input_data.get("rules"))
        tags = self._as_list(input_data.get("tags"))
        branch = input_data.get("branch")
        page = input_data.get("page", 1)
        page_size = input_data.get("page_size", self.page_size)

        self.log("info", f"🐛 Searching issues project={project_key} types={types} sev={severities}")
        yield self._progress("search", f"Recherche des issues sur « {project_key} »")

        raw = await self.call_mcp(self.MCP_SERVER, "search_issues", {
            "project_key": project_key,
            "types": types,
            "severities": severities,
            "statuses": statuses,
            "rules": rules,
            "tags": tags,
            "branch": branch,
            "created_after": input_data.get("created_after"),
            "in_new_code_period": input_data.get("in_new_code_period"),
            "resolved": input_data.get("resolved", False),
            "page": page,
            "page_size": page_size,
            "facets": ["severities", "types"],
        })

        issues = raw.get("issues", [])
        total = raw.get("total", 0)
        facets = {f.get("property"): {v["val"]: v["count"] for v in f.get("values", [])}
                  for f in raw.get("facets", [])}

        self.log("info", f"✅ {total} issues found, {len(issues)} on page {page}")
        yield self._progress("search_done", f"{total} issues trouvées")

        summary = None
        if self.analyze and issues:
            yield self._progress("llm", "Analyse LLM des issues...")
            summary = await self._llm_issues(project_key, issues, facets)

        yield self._result({
            "mode": "issues",
            "project_key": project_key,
            "total": total,
            "page": raw.get("page", page),
            "page_size": raw.get("page_size", page_size),
            "by_severity": facets.get("severities", {}),
            "by_type": facets.get("types", {}),
            "issues": issues,
            "summary": summary,
            "filters": {
                "types": types, "severities": severities, "statuses": statuses,
                "rules": rules, "tags": tags, "branch": branch,
            },
        })

    async def _workflow_hotspots(self, input_data: Dict[str, Any]):
        """Security hotspots d'un projet, avec détail des N premiers."""
        project_key = input_data.get("project_key")
        if not project_key:
            yield self._error("Missing 'project_key' for mode=hotspots")
            return

        status = input_data.get("status", "TO_REVIEW")
        page_size = input_data.get("page_size", self.page_size)
        detail_limit = input_data.get("detail_limit", 5)

        self.log("info", f"🔥 Listing hotspots project={project_key} status={status}")
        yield self._progress("hotspots", f"Récupération des hotspots ({status})...")

        raw = await self.call_mcp(self.MCP_SERVER, "list_security_hotspots", {
            "project_key": project_key,
            "status": status,
            "branch": input_data.get("branch"),
            "in_new_code_period": input_data.get("in_new_code_period"),
            "page": input_data.get("page", 1),
            "page_size": page_size,
        })
        hotspots = raw.get("hotspots", [])
        self.log("info", f"✅ {raw.get('total', 0)} hotspots found")

        details: List[Dict[str, Any]] = []
        for hotspot in hotspots[:detail_limit]:
            yield self._progress("hotspot_detail", f"Analyse du hotspot {hotspot.get('key')}")
            detail = await self._safe_call("get_security_hotspot", {
                "hotspot_key": hotspot["key"],
            }, default={})
            if detail:
                details.append(detail)

        summary = None
        if self.analyze and details:
            yield self._progress("llm", "Analyse LLM des hotspots...")
            summary = await self._llm_hotspots(project_key, details)

        yield self._result({
            "mode": "hotspots",
            "project_key": project_key,
            "status": status,
            "total": raw.get("total", 0),
            "hotspots": hotspots,
            "details": details,
            "summary": summary,
        })

    async def _workflow_remediate(self, input_data: Dict[str, Any]):
        """
        Cœur de la feature : pour chaque issue, agrège
            règle SonarQube (root cause + how to fix)
          + extrait de code réel autour de la ligne
          + contexte RAG du repo (optionnel)
        puis demande au LLM un correctif prêt à appliquer.
        """
        project_key = input_data.get("project_key")
        issue_keys = self._as_list(input_data.get("issue_keys"))

        if not project_key and not issue_keys:
            yield self._error("Provide 'project_key' or 'issue_keys' for mode=remediate")
            return

        limit = int(input_data.get("max_remediations", self.max_remediations))
        context_lines = int(input_data.get("snippet_context", self.snippet_context))
        branch = input_data.get("branch")

        # 1. Sélection des issues à corriger
        if issue_keys:
            yield self._progress("select", f"{len(issue_keys)} issue(s) ciblée(s)")
            issues = []
            for key in issue_keys[:limit]:
                issue = await self._safe_call("get_issue", {"issue_key": key}, default=None)
                if issue:
                    issues.append(issue)
        else:
            types = self._as_list(input_data.get("types")) or ["VULNERABILITY"]
            severities = self._as_list(input_data.get("severities"))
            yield self._progress("select", f"Sélection des {limit} issues prioritaires ({','.join(types)})")
            raw = await self.call_mcp(self.MCP_SERVER, "search_issues", {
                "project_key": project_key,
                "types": types,
                "severities": severities,
                "branch": branch,
                "in_new_code_period": input_data.get("in_new_code_period"),
                "resolved": False,
                "sort": "SEVERITY",
                "asc": False,
                "page_size": max(limit, 20),
            })
            issues = sorted(
                raw.get("issues", []),
                key=lambda i: SEVERITY_ORDER.get(i.get("severity", "INFO"), 9),
            )[:limit]

        if not issues:
            yield self._error("Aucune issue à corriger pour ces critères")
            return

        self.log("info", f"🛠 Remediating {len(issues)} issue(s)")

        # 2. Enrichissement + génération du correctif
        remediations: List[Dict[str, Any]] = []
        rule_cache: Dict[str, Dict[str, Any]] = {}

        for index, issue in enumerate(issues, start=1):
            issue_key = issue.get("key")
            rule_key = issue.get("rule")
            component = issue.get("component")
            line = issue.get("line")

            yield self._progress(
                "remediate",
                f"[{index}/{len(issues)}] {issue.get('severity')} {rule_key} — {component}:{line}",
            )

            # Règle (mise en cache : plusieurs issues partagent souvent la même règle)
            if rule_key and rule_key not in rule_cache:
                rule_cache[rule_key] = await self._safe_call(
                    "get_rule", {"rule_key": rule_key}, default={}
                )
            rule = rule_cache.get(rule_key, {})

            # Extrait de code
            snippet = await self._safe_call("get_source_snippet", {
                "component_key": component,
                "line": line,
                "context": context_lines,
                "branch": branch,
            }, default={})

            # Contexte RAG du repo indexé (optionnel)
            rag_context = ""
            if self.use_rag and self.project_id:
                chunks = await self.get_rag_context(
                    query=f"{rule.get('name', '')} {issue.get('message', '')}", top_k=3
                )
                rag_context = "\n---\n".join(c["content"][:800] for c in chunks)

            fix = await self._llm_remediate(issue, rule, snippet, rag_context)

            remediations.append({
                "issue_key": issue_key,
                "rule": rule_key,
                "rule_name": rule.get("name"),
                "severity": issue.get("severity"),
                "type": issue.get("type"),
                "component": component,
                "line": line,
                "message": issue.get("message"),
                "effort": issue.get("effort"),
                "snippet": snippet.get("text"),
                "snippet_range": [snippet.get("from"), snippet.get("to")] if snippet else None,
                "rule_how_to_fix": (rule.get("how_to_fix") or "")[:1500],
                "remediation": fix,
                "rag_used": bool(rag_context),
            })

        yield self._progress("remediate_done", f"{len(remediations)} correctif(s) généré(s)")

        yield self._result({
            "mode": "remediate",
            "project_key": project_key,
            "branch": branch,
            "count": len(remediations),
            "remediations": remediations,
        })

    # ------------------------------------------------------------------ #
    # LLM helpers
    # ------------------------------------------------------------------ #

    async def _call_llm(self, messages: List[Dict[str, str]], max_tokens: int = 1200) -> str:
        return await self.call_llm(
            messages,
            provider_name=self.config.get("llm_provider"),
            model=self.config.get("llm_model"),
            temperature=self.config.get("llm_temperature", 0.2),
            max_tokens=max_tokens,
        )

    async def _llm_overview(self, project_key, quality_gate, measures, summary, hotspots) -> str:
        failed = quality_gate.get("failed_conditions", []) if quality_gate else []
        failed_txt = "\n".join(
            f"  • {c['metric']}: {c['actual']} (seuil {c['comparator']} {c['threshold']})"
            for c in failed
        ) or "  • aucune"
        messages = [
            {"role": "system", "content": (
                "Tu es un expert AppSec / DevSecOps. Tu analyses des rapports SonarQube "
                "et tu donnes un plan d'action priorisé, concret et actionnable."
            )},
            {"role": "user", "content": (
                f"Projet SonarQube : {project_key}\n"
                f"Quality gate : {quality_gate.get('status', 'N/A')}\n"
                f"Conditions en échec :\n{failed_txt}\n\n"
                f"Métriques : {measures.get('measures', {})}\n"
                f"Issues par sévérité : {summary.get('by_severity', {})}\n"
                f"Issues par type : {summary.get('by_type', {})}\n"
                f"Top règles déclenchées : {list(summary.get('by_rule', {}).items())[:10]}\n"
                f"Fichiers les plus touchés : {list(summary.get('by_file', {}).items())[:10]}\n"
                f"Security hotspots à revoir : {hotspots.get('total', 0)}\n\n"
                "Produis :\n"
                "1. Un verdict en 2 lignes sur la posture sécurité du projet.\n"
                "2. Les 3 à 5 chantiers prioritaires, classés par risque × effort.\n"
                "3. Ce qui bloque la CI/CD et comment le débloquer rapidement."
            )},
        ]
        return await self._call_llm(messages, max_tokens=900)

    async def _llm_issues(self, project_key, issues, facets) -> str:
        lines = "\n".join(
            f"- [{i.get('severity')}][{i.get('type')}] {i.get('rule')} — "
            f"{i.get('component', '').split(':')[-1]}:{i.get('line')} — {(i.get('message') or '')[:120]}"
            for i in issues[:25]
        )
        messages = [
            {"role": "system", "content": (
                "Tu es un expert sécurité applicative. Tu regroupes des issues SonarQube "
                "par cause racine et tu proposes un ordre de correction efficace."
            )},
            {"role": "user", "content": (
                f"Projet : {project_key}\n"
                f"Répartition par sévérité : {facets.get('severities', {})}\n"
                f"Répartition par type : {facets.get('types', {})}\n\n"
                f"Issues :\n{lines}\n\n"
                "Regroupe ces issues par cause racine (pattern commun, règle, fichier), "
                "identifie les corrections à fort effet de levier (une correction = N issues), "
                "et donne un ordre de traitement en 5 points maximum."
            )},
        ]
        return await self._call_llm(messages, max_tokens=800)

    async def _llm_hotspots(self, project_key, details) -> str:
        blocks = "\n\n".join(
            f"[{d.get('key')}] {d.get('rule', {}).get('name')} "
            f"(catégorie: {d.get('rule', {}).get('security_category')}, "
            f"probabilité: {d.get('rule', {}).get('vulnerability_probability')})\n"
            f"Fichier: {d.get('component')}:{d.get('line')}\n"
            f"Risque: {(d.get('rule', {}).get('risk_description') or '')[:400]}\n"
            f"Correctif recommandé: {(d.get('rule', {}).get('fix_recommendations') or '')[:400]}"
            for d in details
        )
        messages = [
            {"role": "system", "content": (
                "Tu es un expert AppSec. Tu tries des Security Hotspots SonarQube : "
                "distinguer les vrais risques des faux positifs, et dire quoi faire."
            )},
            {"role": "user", "content": (
                f"Projet : {project_key}\n\nHotspots à revoir :\n{blocks}\n\n"
                "Pour chaque hotspot : verdict (à corriger / safe / à investiguer), "
                "justification en une ligne, et action concrète."
            )},
        ]
        return await self._call_llm(messages, max_tokens=1000)

    async def _llm_remediate(self, issue, rule, snippet, rag_context) -> str:
        code = (snippet.get("text") or "Code source indisponible")[:3000]
        rag_block = f"\n\nContexte du dépôt (RAG) :\n{rag_context[:2000]}" if rag_context else ""
        messages = [
            {"role": "system", "content": (
                "Tu es un ingénieur sécurité senior. Tu corriges des vulnérabilités détectées "
                "par SonarQube. Tu produis du code compilable, minimal et sûr. "
                "Tu ne réécris jamais tout le fichier : tu ne touches qu'au strict nécessaire. "
                "Réponds toujours dans ce format :\n"
                "## Cause racine\n<2 lignes>\n"
                "## Correctif\n```<langage>\n<code corrigé>\n```\n"
                "## Diff à appliquer\n```diff\n<patch unifié>\n```\n"
                "## Vérification\n<comment valider que la vulnérabilité est levée>"
            )},
            {"role": "user", "content": (
                f"Règle SonarQube : {rule.get('key')} — {rule.get('name')}\n"
                f"Type : {issue.get('type')} | Sévérité : {issue.get('severity')} | "
                f"Effort estimé : {issue.get('effort', 'N/A')}\n"
                f"Langage : {rule.get('lang', 'inconnu')}\n"
                f"Message : {issue.get('message')}\n"
                f"Fichier : {issue.get('component')} (ligne {issue.get('line')})\n\n"
                f"Description de la règle :\n{(rule.get('description') or 'N/A')[:1500]}\n\n"
                f"Recommandation SonarQube :\n{(rule.get('how_to_fix') or 'N/A')[:1500]}\n\n"
                f"Code source (numéroté) :\n```\n{code}\n```"
                f"{rag_block}\n\n"
                "Corrige cette vulnérabilité en respectant strictement le format demandé."
            )},
        ]
        return await self._call_llm(messages, max_tokens=1600)

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #

    async def _safe_call(self, method: str, params: Dict[str, Any], default: Any = None) -> Any:
        """Appel MCP tolérant aux erreurs — un sous-appel optionnel ne casse pas le workflow."""
        try:
            return await self.call_mcp(self.MCP_SERVER, method, params)
        except Exception as exc:
            self.log("warning", f"MCP sonarqube.{method} failed: {exc}")
            return default

    @staticmethod
    def _as_list(value: Any) -> Optional[List[str]]:
        """Accepte une liste, une string CSV, ou None (tolérance sur le payload d'exécution)."""
        if value is None or value == "":
            return None
        if isinstance(value, str):
            return [v.strip() for v in value.split(",") if v.strip()]
        if isinstance(value, (list, tuple)):
            return [str(v) for v in value]
        return [str(value)]

    # ------------------------------------------------------------------ #
    # Yield helpers
    # ------------------------------------------------------------------ #

    def _result(self, data: Dict[str, Any]) -> Dict[str, Any]:
        data.setdefault("metadata", {})["timestamp"] = datetime.utcnow().isoformat()
        return {
            "type": "result",
            "data": data,
            "timestamp": datetime.utcnow().isoformat(),
        }

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