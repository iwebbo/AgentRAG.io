"""
SonarQubeMCPServer — MCP Server pour SonarQube / SonarCloud.

Authentification par **token utilisateur** (identique au token utilisé dans les
pipelines CI/CD : Account → Security → Generate Token).

Deux schémas d'auth supportés (SonarQube a changé de convention selon les versions) :
  - bearer : Authorization: Bearer <TOKEN>          → SonarQube 10.0+ / SonarCloud
  - basic  : Authorization: Basic base64("<TOKEN>:") → toutes versions (8.x / 9.x)

Le serveur démarre sur `auth_mode` (défaut "bearer") et **bascule automatiquement**
sur l'autre schéma si la première requête renvoie 401. Aucune config supplémentaire
nécessaire côté agent.

Config attendue dans mcp_config["sonarqube"] :
{
    "base_url":     "https://sonarqube.aecoding.local",   # sans /api
    "token":        "squ_xxxxxxxxxxxxxxxxxxxx",
    "organization": "my-org",        # optionnel — SonarCloud uniquement
    "verify_ssl":   false,           # optionnel — défaut false (PKI interne)
    "timeout":      30,              # optionnel
    "auth_mode":    "bearer",        # optionnel — "bearer" | "basic"
    "page_size":    100              # optionnel — défaut 100 (max SonarQube: 500)
}

Méthodes exposées :
    Santé / auth
      - get_system_status         : GET /api/system/status        (public)
      - get_server_version        : GET /api/server/version        (public)
      - validate_auth             : GET /api/authentication/validate
    Projets
      - list_projects             : /api/projects/search → fallback /api/components/search_projects
      - get_project               : recherche exacte d'un projet par clé
      - list_branches             : /api/project_branches/list
    Issues / vulnérabilités
      - search_issues             : /api/issues/search (pagination + facettes)
      - fetch_all_issues          : pagination automatique jusqu'à max_items
      - get_issue                 : une issue par clé
      - get_issues_summary        : facettes agrégées (severities / types / rules / files)
    Security hotspots
      - list_security_hotspots    : /api/hotspots/search
      - get_security_hotspot      : /api/hotspots/show
    Contexte de remédiation
      - get_rule                  : /api/rules/show (root cause + how to fix, HTML nettoyé)
      - get_source_snippet        : /api/sources/raw → fallback /api/sources/show
    Qualité
      - get_quality_gate          : /api/qualitygates/project_status
      - get_measures              : /api/measures/component
"""
import base64
import html
import logging
import re
from typing import Any, Dict, List, Optional, Union

import httpx

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 30.0
MAX_PAGE_SIZE = 500

# Metrics par défaut pour get_measures — clés stables sur SonarQube 8.x → 2025.x
DEFAULT_METRICS = [
    "alert_status",
    "bugs",
    "vulnerabilities",
    "code_smells",
    "security_hotspots",
    "coverage",
    "duplicated_lines_density",
    "ncloc",
    "reliability_rating",
    "security_rating",
    "sqale_rating",
    "sqale_index",
]

_TAG_RE = re.compile(r"<[^>]+>")


class SonarQubeError(RuntimeError):
    """Erreur renvoyée par l'API SonarQube (payload {"errors":[{"msg": ...}]})."""

    def __init__(self, status_code: int, message: str, path: str = ""):
        self.status_code = status_code
        self.path = path
        super().__init__(f"SonarQube API {status_code} on {path}: {message}")


class SonarQubeMCPServer:
    """MCP Server SonarQube — lecture seule (audit sécurité + remédiation assistée)."""

    def __init__(
        self,
        base_url: str,
        token: str,
        organization: Optional[str] = None,
        verify_ssl: bool = False,
        timeout: float = DEFAULT_TIMEOUT,
        auth_mode: str = "bearer",
        page_size: int = 100,
    ):
        if not base_url:
            raise ValueError("sonarqube: 'base_url' is required")
        if not token:
            raise ValueError("sonarqube: 'token' is required")

        self.base_url = base_url.rstrip("/")
        self.token = token
        self.organization = organization
        self.verify_ssl = bool(verify_ssl)
        self.timeout = float(timeout)
        self.page_size = min(int(page_size), MAX_PAGE_SIZE)

        self.auth_mode = auth_mode if auth_mode in ("bearer", "basic") else "bearer"
        self._auth_swapped = False          # évite les boucles de fallback
        self._use_components_param = False  # issues: componentKeys → components (SonarQube 10.2+)

        logger.info(
            "SonarQube MCP Server initialized: %s (auth=%s, verify_ssl=%s, org=%s)",
            self.base_url, self.auth_mode, self.verify_ssl, self.organization,
        )

    # ───────────────────────────────────────────────────────────────────────── #
    # HTTP plumbing
    # ───────────────────────────────────────────────────────────────────────── #

    def _headers(self) -> Dict[str, str]:
        if self.auth_mode == "basic":
            encoded = base64.b64encode(f"{self.token}:".encode()).decode()
            authorization = f"Basic {encoded}"
        else:
            authorization = f"Bearer {self.token}"
        return {"Authorization": authorization, "Accept": "application/json"}

    @staticmethod
    def _clean_params(params: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Retire les None/valeurs vides et sérialise les listes en CSV (format SonarQube)."""
        cleaned: Dict[str, Any] = {}
        for key, value in (params or {}).items():
            if value is None or value == "" or value == []:
                continue
            if isinstance(value, (list, tuple, set)):
                cleaned[key] = ",".join(str(v) for v in value)
            elif isinstance(value, bool):
                cleaned[key] = "true" if value else "false"
            else:
                cleaned[key] = value
        return cleaned

    @staticmethod
    def _extract_error(response: httpx.Response) -> str:
        try:
            payload = response.json()
            errors = payload.get("errors") or []
            if errors:
                return "; ".join(e.get("msg", str(e)) for e in errors)
            return str(payload)[:300]
        except Exception:
            return (response.text or "")[:300]

    async def _request(
        self,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        as_text: bool = False,
    ) -> Union[Dict[str, Any], str]:
        """GET authentifié avec fallback d'auth (bearer ↔ basic) sur 401."""
        url = f"{self.base_url}{path}"
        query = self._clean_params(params)
        if self.organization and "organization" not in query:
            query["organization"] = self.organization

        async with httpx.AsyncClient(verify=self.verify_ssl, timeout=self.timeout) as client:
            response = await client.get(url, headers=self._headers(), params=query)

            # Fallback d'authentification une seule fois pour la vie du serveur
            if response.status_code == 401 and not self._auth_swapped:
                self.auth_mode = "basic" if self.auth_mode == "bearer" else "bearer"
                self._auth_swapped = True
                logger.warning(
                    "SonarQube 401 on %s — retrying with auth_mode=%s", path, self.auth_mode
                )
                response = await client.get(url, headers=self._headers(), params=query)

            if response.status_code >= 400:
                raise SonarQubeError(response.status_code, self._extract_error(response), path)

            if as_text:
                return response.text
            if not response.content:
                return {}
            return response.json()

    # ───────────────────────────────────────────────────────────────────────── #
    # Santé / authentification
    # ───────────────────────────────────────────────────────────────────────── #

    async def get_system_status(self) -> Dict[str, Any]:
        """Statut de l'instance : {"id", "version", "status": "UP"|"STARTING"|"DOWN"}."""
        data = await self._request("/api/system/status")
        logger.info("SonarQube status=%s version=%s", data.get("status"), data.get("version"))
        return data

    async def get_server_version(self) -> Dict[str, Any]:
        """Version du serveur (endpoint texte brut)."""
        version = await self._request("/api/server/version", as_text=True)
        return {"version": str(version).strip()}

    async def validate_auth(self) -> Dict[str, Any]:
        """
        Valide le token. SonarQube renvoie {"valid": true|false} *avec un HTTP 200*
        même quand le token est invalide → on remonte le booléen tel quel.
        """
        data = await self._request("/api/authentication/validate")
        valid = bool(data.get("valid", False))
        logger.info("SonarQube auth validation → valid=%s (mode=%s)", valid, self.auth_mode)
        return {"valid": valid, "auth_mode": self.auth_mode, "base_url": self.base_url}

    # ───────────────────────────────────────────────────────────────────────── #
    # Projets
    # ───────────────────────────────────────────────────────────────────────── #

    async def list_projects(
        self,
        query: Optional[str] = None,
        page: int = 1,
        page_size: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Liste les projets visibles.

        /api/projects/search exige la permission 'Administer System'. En cas de 403,
        bascule automatiquement sur /api/components/search_projects (portail Projects,
        accessible à tout utilisateur authentifié).

        Returns:
            {"projects": [{key, name, qualifier, last_analysis_date, visibility}],
             "total": int, "page": int, "page_size": int, "source": "projects|components"}
        """
        ps = min(page_size or self.page_size, MAX_PAGE_SIZE)
        source = "projects"
        try:
            data = await self._request(
                "/api/projects/search", {"q": query, "p": page, "ps": ps}
            )
            components = data.get("components", [])
        except SonarQubeError as exc:
            if exc.status_code not in (401, 403):
                raise
            logger.warning(
                "projects/search refused (%s) — falling back to components/search_projects",
                exc.status_code,
            )
            source = "components"
            data = await self._request(
                "/api/components/search_projects", {"filter": f'query="{query}"' if query else None,
                                                    "p": page, "ps": ps}
            )
            components = data.get("components", [])

        paging = data.get("paging", {})
        projects = [
            {
                "key": c.get("key"),
                "name": c.get("name"),
                "qualifier": c.get("qualifier", "TRK"),
                "visibility": c.get("visibility"),
                "last_analysis_date": c.get("lastAnalysisDate"),
                "revision": c.get("revision"),
            }
            for c in components
        ]
        total = paging.get("total", len(projects))
        logger.info("list_projects q=%r → %d projects (source=%s)", query, total, source)
        return {
            "projects": projects,
            "total": total,
            "page": paging.get("pageIndex", page),
            "page_size": paging.get("pageSize", ps),
            "source": source,
        }

    async def get_project(self, project_key: str) -> Dict[str, Any]:
        """Récupère un projet par sa clé exacte (via /api/components/show)."""
        data = await self._request("/api/components/show", {"component": project_key})
        component = data.get("component", {})
        logger.info("get_project key=%r → %s", project_key, component.get("name", "?"))
        return {
            "key": component.get("key"),
            "name": component.get("name"),
            "qualifier": component.get("qualifier"),
            "analysis_date": component.get("analysisDate"),
            "version": component.get("version"),
            "tags": component.get("tags", []),
            "ancestors": [a.get("key") for a in data.get("ancestors", [])],
        }

    async def list_branches(self, project_key: str) -> Dict[str, Any]:
        """Liste les branches analysées d'un projet (Developer Edition+)."""
        try:
            data = await self._request("/api/project_branches/list", {"project": project_key})
        except SonarQubeError as exc:
            # Community Edition : endpoint indisponible → dégradation propre
            if exc.status_code in (403, 404):
                logger.warning("project_branches/list unavailable (%s) — CE edition?", exc.status_code)
                return {"branches": [], "total": 0, "available": False}
            raise
        branches = [
            {
                "name": b.get("name"),
                "is_main": b.get("isMain", False),
                "type": b.get("type"),
                "quality_gate": (b.get("status") or {}).get("qualityGateStatus"),
                "analysis_date": b.get("analysisDate"),
            }
            for b in data.get("branches", [])
        ]
        logger.info("list_branches project=%r → %d branches", project_key, len(branches))
        return {"branches": branches, "total": len(branches), "available": True}

    # ───────────────────────────────────────────────────────────────────────── #
    # Issues / vulnérabilités
    # ───────────────────────────────────────────────────────────────────────── #

    async def search_issues(
        self,
        project_key: Optional[str] = None,
        issue_keys: Optional[List[str]] = None,
        types: Optional[List[str]] = None,
        severities: Optional[List[str]] = None,
        statuses: Optional[List[str]] = None,
        resolved: Optional[bool] = False,
        rules: Optional[List[str]] = None,
        tags: Optional[List[str]] = None,
        assignees: Optional[List[str]] = None,
        branch: Optional[str] = None,
        pull_request: Optional[str] = None,
        created_after: Optional[str] = None,
        in_new_code_period: Optional[bool] = None,
        facets: Optional[List[str]] = None,
        sort: Optional[str] = "SEVERITY",
        asc: bool = False,
        page: int = 1,
        page_size: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Recherche d'issues (/api/issues/search).

        Args:
            project_key       : clé du projet (composant racine).
            issue_keys        : liste de clés d'issues précises (ignore les autres filtres).
            types             : BUG | VULNERABILITY | CODE_SMELL   (déprécié en 10.4+, toujours fonctionnel)
            severities        : INFO | MINOR | MAJOR | CRITICAL | BLOCKER
            statuses          : OPEN | CONFIRMED | REOPENED | RESOLVED | CLOSED
            resolved          : False = uniquement les issues ouvertes (défaut)
            rules             : filtre par clés de règles (ex: "java:S2076")
            branch            : branche à analyser (Developer Edition+)
            created_after     : ISO date ("2026-01-01" ou "2026-01-01T00:00:00+0000")
            in_new_code_period: limiter au "New Code" (quality gate CI/CD)
            facets            : agrégations demandées (severities, types, rules, files, tags...)
            sort              : SEVERITY | CREATION_DATE | UPDATE_DATE | FILE_LINE

        Returns:
            {"issues": [...], "components": [...], "rules": [...], "facets": [...],
             "total": int, "page": int, "page_size": int}
        """
        ps = min(page_size or self.page_size, MAX_PAGE_SIZE)
        component_param = "components" if self._use_components_param else "componentKeys"

        params: Dict[str, Any] = {
            "issues": issue_keys,
            "types": types,
            "severities": severities,
            "statuses": statuses,
            "rules": rules,
            "tags": tags,
            "assignees": assignees,
            "branch": branch,
            "pullRequest": pull_request,
            "createdAfter": created_after,
            "facets": facets,
            "s": sort,
            "asc": asc,
            "p": page,
            "ps": ps,
            "additionalFields": "_all",
        }
        if resolved is not None and not issue_keys:
            params["resolved"] = resolved
        if in_new_code_period is not None:
            params["inNewCodePeriod"] = in_new_code_period
        if project_key and not issue_keys:
            params[component_param] = project_key

        try:
            data = await self._request("/api/issues/search", params)
        except SonarQubeError as exc:
            # SonarQube 10.2+ a retiré componentKeys → bascule définitive sur `components`
            if exc.status_code == 400 and project_key and not self._use_components_param:
                logger.warning("issues/search rejected 'componentKeys' — switching to 'components'")
                self._use_components_param = True
                params.pop("componentKeys", None)
                params["components"] = project_key
                data = await self._request("/api/issues/search", params)
            else:
                raise

        paging = data.get("paging", {})
        issues = [self._normalize_issue(i) for i in data.get("issues", [])]
        total = paging.get("total", data.get("total", len(issues)))

        logger.info(
            "search_issues project=%r types=%s → %d issues (page %d/%s)",
            project_key, types, total, page, paging.get("pageSize", ps),
        )
        return {
            "issues": issues,
            "components": data.get("components", []),
            "rules": data.get("rules", []),
            "facets": data.get("facets", []),
            "total": total,
            "page": paging.get("pageIndex", page),
            "page_size": paging.get("pageSize", ps),
        }

    async def fetch_all_issues(
        self,
        project_key: str,
        max_items: int = 500,
        **filters: Any,
    ) -> Dict[str, Any]:
        """
        Pagine automatiquement /api/issues/search jusqu'à `max_items`.

        SonarQube plafonne la pagination à 10 000 résultats — au-delà, affiner les filtres.
        """
        collected: List[Dict[str, Any]] = []
        page = 1
        total = 0
        page_size = min(filters.pop("page_size", self.page_size) or self.page_size, MAX_PAGE_SIZE)

        while len(collected) < max_items:
            batch = await self.search_issues(
                project_key=project_key, page=page, page_size=page_size, **filters
            )
            total = batch["total"]
            collected.extend(batch["issues"])
            if not batch["issues"] or len(collected) >= total or page * page_size >= 10000:
                break
            page += 1

        logger.info(
            "fetch_all_issues project=%r → %d/%d collected in %d page(s)",
            project_key, len(collected), total, page,
        )
        return {"issues": collected[:max_items], "total": total, "collected": len(collected[:max_items])}

    async def get_issue(self, issue_key: str) -> Dict[str, Any]:
        """Récupère une issue unique par sa clé (avec composants et règle associés)."""
        data = await self.search_issues(issue_keys=[issue_key], page_size=1, resolved=None)
        issues = data.get("issues", [])
        if not issues:
            raise SonarQubeError(404, f"Issue '{issue_key}' not found", "/api/issues/search")
        issue = issues[0]
        issue["_components"] = data.get("components", [])
        issue["_rule"] = next(
            (r for r in data.get("rules", []) if r.get("key") == issue.get("rule")), None
        )
        logger.info("get_issue key=%r → %s", issue_key, issue.get("message", "?")[:80])
        return issue

    async def get_issues_summary(
        self,
        project_key: str,
        branch: Optional[str] = None,
        in_new_code_period: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """
        Vue agrégée d'un projet via les facettes SonarQube (1 seul appel API).

        Returns:
            {"project": key, "total": int,
             "by_severity": {...}, "by_type": {...}, "by_rule": {...},
             "by_file": {...}, "by_tag": {...}}
        """
        data = await self.search_issues(
            project_key=project_key,
            branch=branch,
            in_new_code_period=in_new_code_period,
            facets=["severities", "types", "rules", "files", "tags", "statuses"],
            page_size=1,
        )
        facets = {f.get("property"): {v["val"]: v["count"] for v in f.get("values", [])}
                  for f in data.get("facets", [])}

        summary = {
            "project": project_key,
            "branch": branch,
            "total": data.get("total", 0),
            "by_severity": facets.get("severities", {}),
            "by_type": facets.get("types", {}),
            "by_status": facets.get("statuses", {}),
            "by_rule": dict(sorted(facets.get("rules", {}).items(),
                                   key=lambda kv: kv[1], reverse=True)[:20]),
            "by_file": dict(sorted(facets.get("files", {}).items(),
                                   key=lambda kv: kv[1], reverse=True)[:20]),
            "by_tag": facets.get("tags", {}),
        }
        logger.info(
            "get_issues_summary project=%r → %d issues, severities=%s",
            project_key, summary["total"], summary["by_severity"],
        )
        return summary

    # ───────────────────────────────────────────────────────────────────────── #
    # Security hotspots
    # ───────────────────────────────────────────────────────────────────────── #

    async def list_security_hotspots(
        self,
        project_key: str,
        status: Optional[str] = "TO_REVIEW",
        resolution: Optional[str] = None,
        branch: Optional[str] = None,
        in_new_code_period: Optional[bool] = None,
        page: int = 1,
        page_size: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Liste les Security Hotspots (/api/hotspots/search).

        Args:
            status    : TO_REVIEW | REVIEWED
            resolution: FIXED | SAFE | ACKNOWLEDGED (uniquement si status=REVIEWED)
        """
        ps = min(page_size or self.page_size, MAX_PAGE_SIZE)
        data = await self._request("/api/hotspots/search", {
            "projectKey": project_key,
            "status": status,
            "resolution": resolution,
            "branch": branch,
            "inNewCodePeriod": in_new_code_period,
            "p": page,
            "ps": ps,
        })
        paging = data.get("paging", {})
        hotspots = [
            {
                "key": h.get("key"),
                "component": h.get("component"),
                "project": h.get("project"),
                "rule": (h.get("rule") or {}).get("key") if isinstance(h.get("rule"), dict) else h.get("ruleKey"),
                "security_category": h.get("securityCategory"),
                "vulnerability_probability": h.get("vulnerabilityProbability"),
                "status": h.get("status"),
                "resolution": h.get("resolution"),
                "line": h.get("line"),
                "message": h.get("message"),
                "author": h.get("author"),
                "creation_date": h.get("creationDate"),
            }
            for h in data.get("hotspots", [])
        ]
        total = paging.get("total", len(hotspots))
        logger.info("list_security_hotspots project=%r status=%s → %d", project_key, status, total)
        return {
            "hotspots": hotspots,
            "components": data.get("components", []),
            "total": total,
            "page": paging.get("pageIndex", page),
            "page_size": paging.get("pageSize", ps),
        }

    async def get_security_hotspot(self, hotspot_key: str) -> Dict[str, Any]:
        """Détail d'un hotspot (/api/hotspots/show) : règle, risque, correctif recommandé."""
        data = await self._request("/api/hotspots/show", {"hotspot": hotspot_key})
        rule = data.get("rule", {}) or {}
        return {
            "key": data.get("key"),
            "component": (data.get("component") or {}).get("key"),
            "project": (data.get("project") or {}).get("key"),
            "status": data.get("status"),
            "resolution": data.get("resolution"),
            "line": data.get("line"),
            "message": data.get("message"),
            "rule": {
                "key": rule.get("key"),
                "name": rule.get("name"),
                "security_category": rule.get("securityCategory"),
                "vulnerability_probability": rule.get("vulnerabilityProbability"),
                "risk_description": self._strip_html(rule.get("riskDescription")),
                "vulnerability_description": self._strip_html(rule.get("vulnerabilityDescription")),
                "fix_recommendations": self._strip_html(rule.get("fixRecommendations")),
            },
            "creation_date": data.get("creationDate"),
            "update_date": data.get("updateDate"),
        }

    # ───────────────────────────────────────────────────────────────────────── #
    # Contexte de remédiation (règle + code source)
    # ───────────────────────────────────────────────────────────────────────── #

    async def get_rule(self, rule_key: str) -> Dict[str, Any]:
        """
        Détail d'une règle (/api/rules/show), HTML nettoyé pour être injecté dans un prompt LLM.

        Gère les deux formats de description :
          - legacy  : rule.htmlDesc
          - 9.6+    : rule.descriptionSections[] (root_cause / how_to_fix / resources)
        """
        data = await self._request("/api/rules/show", {"key": rule_key, "actives": "false"})
        rule = data.get("rule", {}) or {}

        sections: Dict[str, str] = {}
        for section in rule.get("descriptionSections", []) or []:
            key = section.get("key", "unknown")
            sections[key] = self._strip_html(section.get("content", ""))

        description = sections.get("root_cause") or self._strip_html(rule.get("htmlDesc", ""))
        how_to_fix = sections.get("how_to_fix") or ""

        logger.info("get_rule key=%r → %s", rule_key, rule.get("name", "?"))
        return {
            "key": rule.get("key"),
            "name": rule.get("name"),
            "lang": rule.get("langName") or rule.get("lang"),
            "type": rule.get("type"),
            "severity": rule.get("severity"),
            "tags": (rule.get("sysTags") or []) + (rule.get("tags") or []),
            "remediation_effort": rule.get("remFnBaseEffort"),
            "description": description[:4000],
            "how_to_fix": how_to_fix[:4000],
            "sections": list(sections.keys()),
        }

    async def get_source_snippet(
        self,
        component_key: str,
        line: Optional[int] = None,
        context: int = 15,
        from_line: Optional[int] = None,
        to_line: Optional[int] = None,
        branch: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Extrait le code source autour d'une issue — indispensable pour la remédiation LLM.

        Stratégie : /api/sources/raw (texte brut, découpé côté serveur MCP).
        Fallback  : /api/sources/show (HTML SonarQube, nettoyé) si raw est refusé.

        Args:
            component_key: clé du fichier (ex: "my-project:src/main/java/App.java")
            line         : ligne de l'issue — la fenêtre est centrée dessus
            context      : nombre de lignes avant/après (défaut 15)
            from_line/to_line: fenêtre explicite (prioritaire sur line/context)
        """
        if from_line is None or to_line is None:
            if line:
                from_line = max(1, line - context)
                to_line = line + context
            else:
                from_line, to_line = 1, 2 * context + 1

        try:
            raw = await self._request(
                "/api/sources/raw", {"key": component_key, "branch": branch}, as_text=True
            )
            all_lines = str(raw).splitlines()
            window = [
                {"line": n, "code": all_lines[n - 1]}
                for n in range(from_line, min(to_line, len(all_lines)) + 1)
            ]
            source = "raw"
        except SonarQubeError as exc:
            if exc.status_code not in (401, 403, 404):
                raise
            logger.warning("sources/raw refused (%s) — falling back to sources/show", exc.status_code)
            data = await self._request(
                "/api/sources/show",
                {"key": component_key, "from": from_line, "to": to_line, "branch": branch},
            )
            window = [
                {"line": item[0], "code": self._strip_html(item[1])}
                for item in data.get("sources", [])
            ]
            source = "show"

        text = "\n".join(f"{item['line']:>5} | {item['code']}" for item in window)
        logger.info(
            "get_source_snippet component=%r lines=%s-%s → %d lines (%s)",
            component_key, from_line, to_line, len(window), source,
        )
        return {
            "component": component_key,
            "from": from_line,
            "to": to_line,
            "issue_line": line,
            "lines": window,
            "text": text,
            "source": source,
        }

    # ───────────────────────────────────────────────────────────────────────── #
    # Qualité
    # ───────────────────────────────────────────────────────────────────────── #

    async def get_quality_gate(
        self,
        project_key: str,
        branch: Optional[str] = None,
        pull_request: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Statut de la Quality Gate (/api/qualitygates/project_status) — c'est le verdict
        qui fait passer ou échouer le stage CI/CD.
        """
        data = await self._request("/api/qualitygates/project_status", {
            "projectKey": project_key,
            "branch": branch,
            "pullRequest": pull_request,
        })
        status = data.get("projectStatus", {}) or {}
        conditions = [
            {
                "metric": c.get("metricKey"),
                "status": c.get("status"),
                "comparator": c.get("comparator"),
                "threshold": c.get("errorThreshold"),
                "actual": c.get("actualValue"),
            }
            for c in status.get("conditions", [])
        ]
        failed = [c for c in conditions if c["status"] == "ERROR"]
        logger.info(
            "get_quality_gate project=%r → %s (%d failing conditions)",
            project_key, status.get("status"), len(failed),
        )
        return {
            "project": project_key,
            "branch": branch,
            "status": status.get("status"),
            "conditions": conditions,
            "failed_conditions": failed,
        }

    async def get_measures(
        self,
        component_key: str,
        metric_keys: Optional[List[str]] = None,
        branch: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Mesures d'un composant (/api/measures/component) : bugs, vulnérabilités, coverage…"""
        metrics = metric_keys or DEFAULT_METRICS
        data = await self._request("/api/measures/component", {
            "component": component_key,
            "metricKeys": metrics,
            "branch": branch,
        })
        component = data.get("component", {}) or {}
        measures = {
            m.get("metric"): m.get("value", (m.get("periods") or [{}])[0].get("value"))
            for m in component.get("measures", [])
        }
        logger.info("get_measures component=%r → %d metrics", component_key, len(measures))
        return {
            "component": component.get("key", component_key),
            "name": component.get("name"),
            "qualifier": component.get("qualifier"),
            "measures": measures,
        }

    # ───────────────────────────────────────────────────────────────────────── #
    # Helpers
    # ───────────────────────────────────────────────────────────────────────── #

    @staticmethod
    def _strip_html(value: Optional[str]) -> str:
        """Nettoie le HTML SonarQube (descriptions de règles) pour un prompt LLM."""
        if not value:
            return ""
        text = re.sub(r"<br\s*/?>", "\n", value)
        text = re.sub(r"</(p|li|h\d|pre)>", "\n", text)
        text = _TAG_RE.sub("", text)
        text = html.unescape(text)
        return re.sub(r"\n{3,}", "\n\n", text).strip()

    @staticmethod
    def _normalize_issue(issue: Dict[str, Any]) -> Dict[str, Any]:
        """Normalise une issue SonarQube en payload compact et stable."""
        text_range = issue.get("textRange") or {}
        impacts = issue.get("impacts") or []
        return {
            "key": issue.get("key"),
            "rule": issue.get("rule"),
            "severity": issue.get("severity"),
            "type": issue.get("type"),
            "status": issue.get("status"),
            "resolution": issue.get("resolution"),
            "message": issue.get("message"),
            "component": issue.get("component"),
            "project": issue.get("project"),
            "line": issue.get("line") or text_range.get("startLine"),
            "text_range": {
                "start_line": text_range.get("startLine"),
                "end_line": text_range.get("endLine"),
                "start_offset": text_range.get("startOffset"),
                "end_offset": text_range.get("endOffset"),
            } if text_range else None,
            "effort": issue.get("effort") or issue.get("debt"),
            "tags": issue.get("tags", []),
            "author": issue.get("author"),
            "assignee": issue.get("assignee"),
            "creation_date": issue.get("creationDate"),
            "update_date": issue.get("updateDate"),
            "clean_code_attribute": issue.get("cleanCodeAttribute"),
            "impacts": [
                {"quality": i.get("softwareQuality"), "severity": i.get("severity")}
                for i in impacts
            ],
            "flows_count": len(issue.get("flows", [])),
        }