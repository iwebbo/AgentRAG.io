"""
SkillAgent v3 — schema MCP introspectif, zéro hardcoding
=========================================================

Principe : le LLM reçoit le vrai contrat de l'API MCP (méthodes + params exacts)
généré dynamiquement par MCPClient.get_schema_as_text().
Aucune normalisation, aucun alias, aucun mapping par skill_id.

Flux pour skills MCP (ssh_admin, win_admin, et tout futur skill MCP) :
  1. Charger skill template depuis sys_skills / templates / builtin
  2. Récupérer le schema réel du MCP server (introspection Python)
  3. LLM → JSON strict avec méthode + params EXACTS du schema
  4. call_mcp() → stdout réel

Flux pour skills LLM purs (invoice_analyzer, etc.) :
  Inchangé — RAG + mémoire + LLM texte libre.

Config agent :
{
  "skill_id":    "ssh_admin",
  "mcp_servers": ["ssh"],        ← doit être présent pour activer le flow MCP
  "llm_provider": "lmstudio",
  "llm_model":   "openai/gpt-oss-20b"
}
"""
import json
import logging
from typing import Any, AsyncGenerator, Dict, List, Optional
from uuid import UUID
from datetime import datetime
from sqlalchemy.orm import Session

from app.agents.base_agent import BaseAgent
from app.services.vector_store import VectorStore

logger = logging.getLogger(__name__)

SYS_SKILLS_COLLECTION = "sys_skills"

# Prompt système générique — injecte le schema MCP réel en variable
_INTENT_SYSTEM = """\
You are an intent-to-MCP-call translator.
You receive a skill description and a LIVE schema of the MCP server.
You MUST respond ONLY with a valid JSON object — no prose, no markdown, no explanation.

The JSON schema is:
{
  "mcp_method": "<exact method name from the schema>",
  "params": { <exact param names from the schema, matching their types> },
  "reasoning": "<one sentence>"
}

RULES:
- Use ONLY method names listed in the schema. Never invent names.
- Use ONLY param names listed in the schema. Never invent aliases.
- Required params must always be present.
- If the intent cannot be mapped: {"mcp_method": null, "params": {}, "reasoning": "<why>"}
""".strip()


class SkillAgent(BaseAgent):

    def __init__(
        self,
        agent_id: UUID,
        user_id: UUID,
        config: Dict[str, Any],
        mcp_config: Dict[str, Any],
        db: Session,
    ):
        super().__init__(agent_id, user_id, config, mcp_config, db)
        self.skill_id: Optional[str] = config.get("skill_id")
        self.query_field: str = config.get("query_field", "query")

    # ═════════════════════════════════════════════════════════════════════════
    # ENTRY POINT
    # ═════════════════════════════════════════════════════════════════════════

    async def execute(
        self, input_data: Dict[str, Any]
    ) -> AsyncGenerator[Dict[str, Any], None]:

        if not self.skill_id:
            raise ValueError("SkillAgent requires 'skill_id' in agent config.")

        query: str = input_data.get(self.query_field, "")
        host: str  = input_data.get("host", "")
        extra_context: str = input_data.get("context", "")
        conversation_id = input_data.get("conversation_id")
        extra_params = {
            k: v for k, v in input_data.items()
            if k not in ("query", "context", "conversation_id", "trigger", "host")
        }

        self.log("info", f"SkillAgent starting skill='{self.skill_id}'")
        yield self._mk_log()

        # ── 1. Charger le template skill ─────────────────────────────────────
        yield self._mk_progress("loading_skill", {"skill_id": self.skill_id})
        skill_definition = await self._load_skill_definition()
        self.log("info", f"Skill loaded: {self.skill_id} ({len(skill_definition)} chars)")
        yield self._mk_log()

        # ── 2. RAG context ───────────────────────────────────────────────────
        rag_chunks: List[Dict] = []
        if query and self.project_id:
            yield self._mk_progress("fetching_rag", {"query": query[:60]})
            rag_chunks = await self.get_rag_context(query=query, top_k=5)
            self.log("info", f"RAG: {len(rag_chunks)} chunks retrieved")
            yield self._mk_log()

        # ── 3. Mémoire épisodique ────────────────────────────────────────────
        memory_chunks = await self._recall_memory(query)
        if memory_chunks:
            self.log("info", f"Memory: {len(memory_chunks)} past executions recalled")
            yield self._mk_log()

        # ── 4. Routing : MCP ou LLM texte libre ─────────────────────────────
        mcp_server = self._resolve_mcp_server()
        if mcp_server:
            async for update in self._run_mcp_skill(
                query=query,
                host=host,
                mcp_server=mcp_server,
                skill_definition=skill_definition,
                memory_chunks=memory_chunks,
                rag_chunks=rag_chunks,
            ):
                yield update
        else:
            async for update in self._run_llm_skill(
                query=query,
                extra_context=extra_context,
                skill_definition=skill_definition,
                rag_chunks=rag_chunks,
                memory_chunks=memory_chunks,
                conversation_id=conversation_id,
                extra_params=extra_params,
            ):
                yield update

    # ═════════════════════════════════════════════════════════════════════════
    # MCP SKILL FLOW
    # ═════════════════════════════════════════════════════════════════════════

    def _resolve_mcp_server(self) -> Optional[str]:
        """
        Retourne le nom du MCP server si ce skill doit passer par MCP.
        Règle : premier serveur listé dans config["mcp_servers"] qui est
                effectivement enregistré dans mcp_client.
        Aucun hardcoding skill_id → server_name.
        """
        if not self.mcp_client:
            return None
        for server_name in self.mcp_servers:
            if server_name in self.mcp_client.servers:
                return server_name
        return None

    async def _run_mcp_skill(
        self,
        query: str,
        host: str,
        mcp_server: str,
        skill_definition: str,
        memory_chunks: List[Dict],
        rag_chunks: List[Dict],
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """LLM → intent JSON (avec schema MCP réel) → call_mcp → stdout réel."""

        # ── 4a. Récupérer le schema MCP réel (introspection) ─────────────────
        try:
            mcp_schema_text = self.mcp_client.get_schema_as_text(mcp_server)
        except Exception as e:
            self.log("warning", f"Schema introspection failed: {e} — falling back to method list")
            mcp_schema_text = f"MCP server '{mcp_server}' — schema unavailable."

        self.log("info", f"MCP schema loaded for '{mcp_server}' ({len(mcp_schema_text)} chars)")

        # ── 4b. Construire le prompt avec schema injecté ──────────────────────
        yield self._mk_progress("llm_intent", {"status": "pending"})

        memory_str = ""
        if memory_chunks:
            lines = ["Past executions (context only):"]
            for m in memory_chunks:
                lines.append(f"  - {m.get('content', '')[:100]}")
            memory_str = "\n".join(lines)

        user_msg = (
            f"## Skill description\n{skill_definition}\n\n"
            f"## Live MCP API schema (use EXACTLY these names)\n{mcp_schema_text}\n\n"
            + (f"## Past executions\n{memory_str}\n\n" if memory_str else "")
            + f"## Request\n  query: \"{query}\"\n  host:  \"{host}\"\n\n"
            f"Respond ONLY with the JSON object."
        )

        try:
            raw = await self.call_llm(
                messages=[
                    {"role": "system", "content": _INTENT_SYSTEM},
                    {"role": "user",   "content": user_msg},
                ],
                temperature=0.0,
                max_tokens=512,
            )
        except Exception as e:
            self.log("error", f"LLM intent extraction failed: {e}")
            yield self._mk_result_error(f"LLM error: {e}")
            return

        # ── 4c. Parser le JSON retourné ───────────────────────────────────────
        import re
        cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip(), flags=re.MULTILINE)
        try:
            intent: Dict[str, Any] = json.loads(cleaned)
        except json.JSONDecodeError:
            self.log("error", f"LLM returned invalid JSON: {raw[:200]}")
            yield self._mk_result_error(f"LLM JSON parse error. Raw: {raw[:200]}")
            return

        mcp_method: Optional[str] = intent.get("mcp_method")
        mcp_params: Dict[str, Any] = intent.get("params", {})
        reasoning: str = intent.get("reasoning", "")

        self.log("info", f"Intent: method={mcp_method} reasoning={reasoning}")
        yield self._mk_progress("intent_parsed", {"method": mcp_method, "params": mcp_params})

        if not mcp_method:
            yield self._mk_result_error(f"Cannot determine MCP action: {reasoning}")
            return

        # ── 4d. Validation contre le schema réel (guard) ─────────────────────
        try:
            schema = self.mcp_client.get_schema(mcp_server)
            valid, error = self._validate_against_schema(mcp_method, mcp_params, schema)
            if not valid:
                self.log("error", f"Schema validation failed: {error}")
                yield self._mk_result_error(
                    f"LLM generated invalid call — {error}. "
                    f"Available methods: {list(schema.keys())}"
                )
                return
        except Exception as e:
            self.log("warning", f"Schema validation skipped: {e}")

        # ── 4e. Injecter host si absent et pertinent ──────────────────────────
        schema = self.mcp_client.get_schema(mcp_server)
        method_params = schema.get(mcp_method, {}).get("params", {})
        if host and "host" in method_params and "host" not in mcp_params:
            mcp_params["host"] = host

        # ── 4f. Appel MCP réel ────────────────────────────────────────────────
        self.log("info", f"Calling MCP {mcp_server}.{mcp_method} params={mcp_params}")
        yield self._mk_progress("mcp_call", {
            "server": mcp_server, "method": mcp_method, "params": mcp_params
        })

        try:
            mcp_result: Dict[str, Any] = await self.call_mcp(mcp_server, mcp_method, mcp_params)
        except Exception as e:
            self.log("error", f"MCP {mcp_server}.{mcp_method} failed: {e}")
            yield self._mk_result_error(f"MCP error: {e}")
            return

        stdout: str   = mcp_result.get("stdout", "")
        stderr: str   = mcp_result.get("stderr", "")
        exit_code     = mcp_result.get("exit_code", -1)
        success: bool = mcp_result.get("success", False)

        self.log(
            "info" if success else "warning",
            f"MCP result: exit_code={exit_code}, stdout={len(stdout)} chars"
        )

        await self._write_memory(
            query=f"host={host} query={query}",
            response=f"method={mcp_method} exit_code={exit_code}\n{stdout[:400]}",
        )
        
        #Fix return command
        if self.llm_conversation_id:
            from app.models import Message as MessageModel
            result_msg = MessageModel(
                conversation_id=self.llm_conversation_id,
                role="assistant",
                content=_format_output(success, stdout, stderr, exit_code),
            )
            self.db.add(result_msg)
            self.db.commit()

        yield {
            "type": "result",
            "data": {
                "skill_id":           self.skill_id,
                "mcp_server":         mcp_server,
                "mcp_method":         mcp_method,
                "mcp_params":         mcp_params,
                "success":            success,
                "exit_code":          exit_code,
                "stdout":             stdout,
                "stderr":             stderr,
                "output":             _format_output(success, stdout, stderr, exit_code),
                "reasoning":          reasoning,
                "rag_chunks_used":    len(rag_chunks),
                "memory_chunks_used": len(memory_chunks),
                "tokens_used":        self.tokens_used,
            },
            "timestamp": datetime.utcnow().isoformat(),
        }
    

    # ═════════════════════════════════════════════════════════════════════════
    # SCHEMA VALIDATION (générique)
    # ═════════════════════════════════════════════════════════════════════════

    def _validate_against_schema(
        self,
        method: str,
        params: Dict[str, Any],
        schema: Dict[str, Any],
    ) -> tuple:
        """
        Valide method + params contre le schema introspectif.
        Retourne (True, None) si OK, (False, error_message) sinon.
        Générique — fonctionne pour tout MCP server.
        """
        if method not in schema:
            available = list(schema.keys())
            return False, f"'{method}' not in schema. Available: {available}"

        method_schema = schema[method]["params"]

        # Vérifier les params requis
        for pname, pmeta in method_schema.items():
            if pmeta.get("required") and pname not in params:
                return False, f"Required param '{pname}' missing for method '{method}'"

        # Vérifier qu'il n'y a pas de params inconnus
        for pname in params:
            if pname not in method_schema:
                return False, f"Unknown param '{pname}' for method '{method}'. Known: {list(method_schema.keys())}"

        return True, None

    # ═════════════════════════════════════════════════════════════════════════
    # LLM TEXT SKILL FLOW (invoice_analyzer, etc.) — inchangé
    # ═════════════════════════════════════════════════════════════════════════

    async def _run_llm_skill(
        self,
        query: str,
        extra_context: str,
        skill_definition: str,
        rag_chunks: List[Dict],
        memory_chunks: List[Dict],
        conversation_id,
        extra_params: Dict,
    ) -> AsyncGenerator[Dict[str, Any], None]:

        yield self._mk_progress("calling_llm", {})

        rag_text = (
            "\n\n---\n".join(f"[doc {i+1}]\n{c['content']}" for i, c in enumerate(rag_chunks))
            if rag_chunks else "No document context available."
        )
        memory_text = (
            "\n\n---\n".join(f"[past {i+1}]\n{c['content']}" for i, c in enumerate(memory_chunks))
            if memory_chunks else "No past executions."
        )

        parts = [f"Input: {query}"]
        if extra_context:
            parts.append(f"Additional context: {extra_context}")
        parts.append(f"\n## Document context (RAG)\n{rag_text}")
        parts.append(f"\n## Memory\n{memory_text}")

        llm_result = await self.call_llm(
            messages=[
                {"role": "system", "content": skill_definition},
                {"role": "user",   "content": "\n\n".join(parts)},
            ],
            provider_name=self.config.get("llm_provider"),
            model=self.config.get("llm_model"),
            temperature=0.3,
            max_tokens=2000,
        )

        await self._write_memory(query=query, response=llm_result[:800])

        yield {
            "type": "result",
            "data": {
                "skill_id":           self.skill_id,
                "output":             llm_result,
                "rag_chunks_used":    len(rag_chunks),
                "memory_chunks_used": len(memory_chunks),
                "tokens_used":        self.tokens_used,
            },
            "timestamp": datetime.utcnow().isoformat(),
        }

    # ═════════════════════════════════════════════════════════════════════════
    # SKILL DEFINITION LOADER
    # ═════════════════════════════════════════════════════════════════════════

    async def _load_skill_definition(self) -> str:
        """
        Priorité : sys_skills ChromaDB → SQL templates → builtin.
        Le builtin n'a plus besoin de décrire les méthodes MCP
        (c'est le schema introspectif qui s'en charge).
        """
        # 1. ChromaDB sys_skills
        try:
            vs = VectorStore()
            results = vs.query(
                project_id=SYS_SKILLS_COLLECTION,
                query_embedding=self.embeddings.encode_single(self.skill_id),
                n_results=1,
            )
            if results and results.get("documents") and results["documents"][0]:
                for doc, meta in zip(
                    results["documents"][0],
                    results.get("metadatas", [[]])[0],
                ):
                    if meta.get("skill_id") == self.skill_id or self.skill_id in doc[:100]:
                        logger.info(f"Skill '{self.skill_id}' loaded from sys_skills ChromaDB")
                        return doc
        except Exception as e:
            logger.debug(f"sys_skills ChromaDB lookup failed: {e}")

        # 2. SQL templates table
        try:
            from app.models.template import Template
            record = self.db.query(Template).filter(Template.name == self.skill_id).first()
            if record and record.content:
                logger.info(f"Skill '{self.skill_id}' loaded from templates table")
                return record.content
        except Exception as e:
            logger.debug(f"Template SQL lookup failed: {e}")

        # 3. Builtin minimal (contexte métier uniquement — pas de schema MCP)
        if self.skill_id in _BUILTIN_SKILLS:
            logger.info(f"Skill '{self.skill_id}' loaded from builtin")
            return _BUILTIN_SKILLS[self.skill_id]

        raise ValueError(
            f"Skill '{self.skill_id}' not found. "
            f"Register it via POST /api/skills or add it to templates."
        )

    # ═════════════════════════════════════════════════════════════════════════
    # MEMORY
    # ═════════════════════════════════════════════════════════════════════════

    async def _recall_memory(self, query: str, top_k: int = 3) -> List[Dict]:
        if not query:
            return []
        try:
            vs = VectorStore()
            results = vs.query(
                project_id=f"sys_memory_{self.skill_id}",
                query_embedding=self.embeddings.encode_single(query),
                n_results=top_k,
            )
            if not results or not results.get("documents"):
                return []
            return [
                {"content": doc, "metadata": meta}
                for doc, meta in zip(
                    results["documents"][0],
                    results.get("metadatas", [[]])[0],
                )
            ]
        except Exception as e:
            logger.debug(f"Memory recall failed (non-blocking): {e}")
            return []

    async def _write_memory(self, query: str, response: str) -> None:
        try:
            vs = VectorStore()
            content = f"Request: {query}\n\nResponse: {response}"
            embedding = self.embeddings.encode_single(content)
            vs.add_documents(
                project_id=f"sys_memory_{self.skill_id}",
                documents=[content],
                embeddings=[embedding.tolist()],
                metadatas=[{
                    "skill_id":   self.skill_id,
                    "user_id":    str(self.user_id),
                    "created_at": datetime.utcnow().isoformat(),
                }],
                ids=[f"mem_{self.skill_id}_{datetime.utcnow().timestamp()}"],
            )
        except Exception as e:
            logger.debug(f"Memory write failed (non-blocking): {e}")

    # ═════════════════════════════════════════════════════════════════════════
    # HELPERS
    # ═════════════════════════════════════════════════════════════════════════

    def _mk_log(self) -> Dict[str, Any]:
        return {"type": "log", "data": self.logs[-1], "timestamp": self.logs[-1]["timestamp"]}

    def _mk_progress(self, step: str, data: Dict) -> Dict[str, Any]:
        return {"type": "progress", "data": {"step": step, **data}, "timestamp": datetime.utcnow().isoformat()}

    def _mk_result_error(self, message: str) -> Dict[str, Any]:
        self.log("error", message)
        return {
            "type": "result",
            "data": {"skill_id": self.skill_id, "success": False, "error": message,
                     "stdout": "", "stderr": "", "tokens_used": self.tokens_used},
            "timestamp": datetime.utcnow().isoformat(),
        }


# Fix output MCP command return
def _format_output(success: bool, stdout: str, stderr: str, exit_code: int) -> str:
    """Formate le résultat MCP pour affichage front — champ output_data.output."""
    if success:
        icon = "✅ Succès"
        body = stdout.strip()
    elif exit_code != 0 and stdout:
        icon = "⚠️ Warning"
        body = stdout.strip()
    else:
        icon = "❌ Erreur"
        body = stderr.strip() or f"exit_code={exit_code}"
    return f"{icon}\n\n{body}"


# ═════════════════════════════════════════════════════════════════════════════
# BUILTIN SKILL TEMPLATES
# Contexte métier uniquement — PAS de description des méthodes MCP.
# Le schema est injecté dynamiquement via MCPClient.get_schema_as_text().
# ═════════════════════════════════════════════════════════════════════════════

_BUILTIN_SKILLS: Dict[str, str] = {
    "ssh_admin": """\
You are an expert Linux/Unix sysadmin assistant.
Given a user request and a live MCP API schema, determine the correct MCP method
and params to fulfill the request on the specified remote host.
Map natural language admin queries (disk, memory, CPU, services, logs, files)
to the appropriate MCP method using the exact names from the schema.""",

    "win_admin": """\
You are an expert Windows sysadmin assistant (PowerShell).
Given a user request and a live MCP API schema, determine the correct MCP method
and params to fulfill the request on the specified remote Windows host.
Map natural language admin queries (disk, memory, processes, services, registry)
to the appropriate MCP method using the exact names from the schema.""",
}