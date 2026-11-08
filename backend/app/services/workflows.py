"""
Workflows : exécution d'un DAG d'agents déterministes existants.

Réutilise tel quel AgentExecutor (même moteur que POST /api/agents/{id}/execute/stream) :
chaque node = une exécution d'agent (AgentExecution + Conversation dédiée), dans l'ordre topologique.

Références résolues dans toutes les valeurs string de node.input :
    {{trigger.<clé>}}                    -> input_data du run
    {{nodes.<id>.output[.chemin]}}       -> résultat (payload `result`) d'un node AMONT uniquement
Une valeur qui est exactement une référence garde son type natif (dict, liste, nombre...) ;
une référence au milieu d'un texte est convertie en texte.

Sémantique d'échec : un node en échec n'arrête pas les branches indépendantes ; ses descendants
sont ignorés. Le run est « failed » si au moins un node n'est pas « done ».
"""
import asyncio
import json
import logging
import re
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from typing import Any, AsyncIterator, Dict, List, Optional, Set, Tuple
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.agent import Agent, AgentExecution
from app.models.conversation import Conversation
from app.models.workflows import Workflow, WorkflowRun

logger = logging.getLogger(__name__)

NODE_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
TEMPLATE_RE = re.compile(r"\{\{\s*([^{}]*?)\s*\}\}")
MAX_STORED_OUTPUT_BYTES = 1_000_000
MAX_STREAM_CHARS = 200_000


class WorkflowValidationError(Exception):
    def __init__(self, errors: List[str]):
        self.errors = list(errors)
        super().__init__("; ".join(self.errors))


class WorkflowTemplateError(Exception):
    pass


# ───────────────────────────── helpers texte ─────────────────────────────────

def _result_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    try:  # même rendu que le scheduler quand il est disponible
        from app.services.scheduler.formatter import result_to_text
        return result_to_text(value)
    except Exception:
        return json.dumps(value, default=str, ensure_ascii=False, indent=2)


def _error_text(payload: Any) -> str:
    try:
        from app.services.scheduler.formatter import error_to_text
        return error_to_text(payload)
    except Exception:
        if isinstance(payload, dict):
            return str(payload.get("message") or payload.get("error") or json.dumps(payload, default=str))
        return str(payload)


def _json_safe(value: Any) -> Any:
    if value is None:
        return None
    try:
        dumped = json.dumps(value, default=str, ensure_ascii=False)
    except Exception:
        return {"unserializable": True}
    if len(dumped.encode("utf-8")) > MAX_STORED_OUTPUT_BYTES:
        return {"truncated": True, "reason": "output too large to store"}
    return json.loads(dumped)


# ───────────────────────────── graphe ────────────────────────────────────────

def build_graph(node_ids: List[str], edges: List[Dict[str, Any]]) -> Tuple[List[str], Dict[str, Set[str]], bool]:
    """Tri topologique stable (Kahn). Retourne (ordre, prédécesseurs, cyclique?)."""
    preds: Dict[str, Set[str]] = {i: set() for i in node_ids}
    succs: Dict[str, List[str]] = {i: [] for i in node_ids}
    for e in edges:
        s, t = e.get("source"), e.get("target")
        if s in preds and t in preds and s != t and s not in preds[t]:
            preds[t].add(s)
            succs[s].append(t)
    indeg = {i: len(preds[i]) for i in node_ids}
    queue = deque(i for i in node_ids if indeg[i] == 0)
    order: List[str] = []
    while queue:
        cur = queue.popleft()
        order.append(cur)
        for nxt in succs[cur]:
            indeg[nxt] -= 1
            if indeg[nxt] == 0:
                queue.append(nxt)
    return order, preds, len(order) != len(node_ids)


def _ancestors(node_id: str, preds: Dict[str, Set[str]]) -> Set[str]:
    seen: Set[str] = set()
    stack = list(preds.get(node_id, ()))
    while stack:
        cur = stack.pop()
        if cur in seen:
            continue
        seen.add(cur)
        stack.extend(preds.get(cur, ()))
    return seen


# ───────────────────────────── templates ─────────────────────────────────────

def _iter_strings(value: Any):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for v in value.values():
            yield from _iter_strings(v)
    elif isinstance(value, list):
        for v in value:
            yield from _iter_strings(v)


def _walk(value: Any, tokens: List[str], label: str) -> Any:
    cur = value
    for t in tokens:
        if isinstance(cur, dict) and t in cur:
            cur = cur[t]
        elif isinstance(cur, list) and t.isdigit() and int(t) < len(cur):
            cur = cur[int(t)]
        else:
            raise WorkflowTemplateError(f"Unresolved reference '{label}': '{t}' not found")
    return cur


def _resolve_expr(expr: str, trigger: Dict[str, Any], outputs: Dict[str, Any]) -> Any:
    tokens = expr.strip().split(".")
    if tokens[0] == "trigger" and len(tokens) >= 2:
        return _walk(trigger, tokens[1:], expr)
    if tokens[0] == "nodes" and len(tokens) >= 3 and tokens[2] == "output":
        if tokens[1] not in outputs:
            raise WorkflowTemplateError(f"Unresolved reference '{expr}': node '{tokens[1]}' produced no output")
        return _walk(outputs[tokens[1]], tokens[3:], expr)
    raise WorkflowTemplateError(f"Invalid reference '{{{{{expr}}}}}'")


def resolve_templates(value: Any, trigger: Dict[str, Any], outputs: Dict[str, Any]) -> Any:
    if isinstance(value, str):
        matches = list(TEMPLATE_RE.finditer(value))
        if not matches:
            return value
        if len(matches) == 1 and matches[0].span() == (0, len(value)):
            return _resolve_expr(matches[0].group(1), trigger, outputs)

        def _sub(m: "re.Match[str]") -> str:
            v = _resolve_expr(m.group(1), trigger, outputs)
            return "" if v is None else _result_text(v)

        return TEMPLATE_RE.sub(_sub, value)
    if isinstance(value, dict):
        return {k: resolve_templates(v, trigger, outputs) for k, v in value.items()}
    if isinstance(value, list):
        return [resolve_templates(v, trigger, outputs) for v in value]
    return value


# ───────────────────────────── validation stricte ────────────────────────────

@dataclass
class ExecutionPlan:
    order: List[str]
    nodes: Dict[str, Dict[str, Any]]
    preds: Dict[str, Set[str]]
    agents: Dict[str, Agent]  # clé = agent_id (str)


def validate_for_execution(db: Session, user_id: UUID, definition: Dict[str, Any]) -> ExecutionPlan:
    """Validation stricte avant exécution. Lève WorkflowValidationError (liste de messages)."""
    errors: List[str] = []
    raw_nodes: List[Dict[str, Any]] = list((definition or {}).get("nodes") or [])
    edges: List[Dict[str, Any]] = list((definition or {}).get("edges") or [])

    if not raw_nodes:
        raise WorkflowValidationError(["Workflow has no nodes"])

    ids = [str(n.get("id", "")) for n in raw_nodes]
    nodes = {str(n.get("id", "")): n for n in raw_nodes}
    if len(nodes) != len(raw_nodes):
        errors.append("Duplicate node ids")
    for nid in ids:
        if not NODE_ID_RE.match(nid):
            errors.append(f"Invalid node id '{nid}' (allowed: letters, digits, '_' and '-')")

    agent_ids: Set[UUID] = set()
    for nid, n in nodes.items():
        if n.get("type", "agent") != "agent":
            errors.append(f"Node '{nid}': unsupported type '{n.get('type')}'")
        raw_agent = n.get("agent_id")
        if not raw_agent:
            errors.append(f"Node '{nid}': no agent selected")
            continue
        try:
            agent_ids.add(UUID(str(raw_agent)))
        except ValueError:
            errors.append(f"Node '{nid}': invalid agent_id")

    for e in edges:
        if e.get("source") not in nodes or e.get("target") not in nodes:
            errors.append(f"Edge {e.get('source')} -> {e.get('target')} references an unknown node")

    if errors:
        raise WorkflowValidationError(errors)

    order, preds, cyclic = build_graph(list(nodes.keys()), edges)
    if cyclic:
        raise WorkflowValidationError(["Workflow contains a cycle"])

    agents_found = {
        str(a.id): a
        for a in db.query(Agent).filter(Agent.id.in_(agent_ids), Agent.user_id == user_id).all()
    }
    for nid, n in nodes.items():
        a = agents_found.get(str(UUID(str(n["agent_id"]))))
        if a is None:
            errors.append(f"Node '{nid}': agent not found")
        elif not a.is_active:
            errors.append(f"Node '{nid}': agent '{a.name}' is not active")

    # références : trigger.<clé> ou nodes.<id amont>.output...
    for nid in order:
        upstream = _ancestors(nid, preds)
        for s in _iter_strings(nodes[nid].get("input") or {}):
            for m in TEMPLATE_RE.finditer(s):
                tokens = m.group(1).strip().split(".")
                if tokens[0] == "trigger" and len(tokens) >= 2:
                    continue
                if tokens[0] == "nodes" and len(tokens) >= 3 and tokens[2] == "output":
                    if tokens[1] not in nodes:
                        errors.append(f"Node '{nid}': reference to unknown node '{tokens[1]}'")
                    elif tokens[1] not in upstream:
                        errors.append(f"Node '{nid}': '{tokens[1]}' is not upstream")
                    continue
                errors.append(f"Node '{nid}': invalid reference '{{{{{m.group(1).strip()}}}}}'")

    if errors:
        raise WorkflowValidationError(errors)

    # clés normalisées (UUID canonique)
    agents = {str(UUID(str(n["agent_id"]))): agents_found[str(UUID(str(n["agent_id"])))] for n in nodes.values()}
    return ExecutionPlan(order=order, nodes=nodes, preds=preds, agents=agents)


# ───────────────────────────── exécution ─────────────────────────────────────

def _event(kind: str, node_id: Optional[str], **extra: Any) -> Dict[str, Any]:
    payload: Dict[str, Any] = {"type": kind, **extra}
    if node_id:
        payload["node_id"] = node_id
    return payload


async def run_workflow(
    db: Session,
    user_id: UUID,
    workflow: Workflow,
    plan: ExecutionPlan,
    input_data: Dict[str, Any],
    trigger: str = "manual",
) -> AsyncIterator[Tuple[str, Dict[str, Any]]]:
    """Génère des (event_name, payload) : init | log | progress | node_status | result | error | done."""
    from app.agents.agent_executor import AgentExecutor  # import tardif : charge toutes les classes d'agents

    run = WorkflowRun(
        workflow_id=workflow.id,
        user_id=user_id,
        status="running",
        trigger=trigger,
        input_data=input_data,
        node_results={},
        started_at=datetime.utcnow(),
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    statuses: Dict[str, str] = {}
    results: Dict[str, Dict[str, Any]] = {}
    outputs: Dict[str, Any] = {}
    current_execution: Optional[AgentExecution] = None
    finished = False

    yield "init", {"run_id": str(run.id), "workflow_id": str(workflow.id)}

    try:
        executor = AgentExecutor(db)

        for node_id in plan.order:
            node = plan.nodes[node_id]
            agent = plan.agents[str(UUID(str(node["agent_id"])))]

            if any(statuses.get(p) != "done" for p in plan.preds[node_id]):
                statuses[node_id] = "skipped"
                results[node_id] = {"status": "skipped"}
                yield "log", _event("log", None, message=f"⏭ '{agent.name}' ({node_id}) skipped: an upstream node did not complete")
                continue

            yield "node_status", _event("node_status", node_id, status="running")

            def _fail(message: str) -> List[Tuple[str, Dict[str, Any]]]:
                statuses[node_id] = "failed"
                results[node_id] = {"status": "failed", "error": message}
                return [
                    ("error", _event("error", node_id, error=message, data={"message": message})),
                    ("node_status", _event("node_status", node_id, status="failed")),
                ]

            # 1) résolution des références
            try:
                resolved = resolve_templates(node.get("input") or {}, input_data, outputs)
                if not isinstance(resolved, dict):
                    raise WorkflowTemplateError("Node input must be an object")
            except WorkflowTemplateError as exc:
                for ev in _fail(str(exc)):
                    yield ev
                continue

            # 2) exécution de l'agent (même séquence que /agents/{id}/execute/stream)
            cfg = agent.config or {}
            conversation = Conversation(
                user_id=user_id,
                title=f"[Workflow] {workflow.name} · {agent.name}"[:255],
                provider_name=cfg.get("llm_provider", "ollama"),
                model=cfg.get("llm_model", ""),
                temperature=cfg.get("llm_temperature", 0.7),
            )
            db.add(conversation)
            db.commit()
            db.refresh(conversation)

            payload = dict(resolved)
            payload["conversation_id"] = str(conversation.id)

            current_execution = AgentExecution(
                agent_id=agent.id,
                status="pending",
                trigger="workflow",
                input_data=payload,
                started_at=datetime.utcnow(),
            )
            db.add(current_execution)
            db.commit()
            db.refresh(current_execution)

            final: Any = None
            err_payload: Any = None
            raised: Optional[str] = None
            stream_parts: List[str] = []
            stream_size = 0

            try:
                async for update in executor.execute_agent(
                    agent_id=agent.id,
                    execution_id=current_execution.id,
                    input_data=payload,
                ):
                    kind = update.get("type", "log")
                    if kind == "result":
                        final = update.get("data")
                        yield "result", {**update, "node_id": node_id}
                    elif kind == "error":
                        err_payload = update.get("data")
                    elif kind in ("log", "progress"):
                        yield kind, {**update, "node_id": node_id}
                    elif kind == "stream" and stream_size < MAX_STREAM_CHARS:
                        data = update.get("data")
                        piece = data if isinstance(data, str) else (
                            next((data[k] for k in ("content", "text", "chunk", "token", "delta")
                                  if isinstance(data, dict) and isinstance(data.get(k), str)), "")
                        )
                        stream_parts.append(piece)
                        stream_size += len(piece)
                    await asyncio.sleep(0)
            except Exception as exc:
                logger.exception("Workflow %s: node %s raised", workflow.id, node_id)
                raised = str(exc) or exc.__class__.__name__

            exec_id = str(current_execution.id)
            failure: Optional[str] = None
            if raised is not None:
                failure = raised
            elif final is None and err_payload is not None:
                failure = _error_text(err_payload)

            if failure is not None:
                # AgentExecutor laisse parfois « success » quand l'agent yield une erreur : on corrige l'historique
                db.rollback()
                ex = db.query(AgentExecution).filter(AgentExecution.id == current_execution.id).first()
                if ex is not None:
                    ex.status = "failed"
                    ex.output_data = {"error": failure}
                    ex.completed_at = datetime.utcnow()
                    db.commit()
                current_execution = None
                for ev in _fail(failure):
                    yield ev
                results[node_id]["execution_id"] = exec_id
                continue

            if final is None and stream_parts:
                text = "".join(stream_parts).strip()
                if text:
                    final = {"content": text}
                    yield "result", {"type": "result", "data": final, "node_id": node_id}

            current_execution = None
            statuses[node_id] = "done"
            outputs[node_id] = final
            results[node_id] = {"status": "done", "execution_id": exec_id, "output": _json_safe(final)}
            yield "node_status", _event("node_status", node_id, status="done")

        failed = [n for n in plan.order if statuses.get(n) != "done"]
        run.status = "failed" if failed else "success"
        if failed:
            run.error = "Nodes not completed: " + ", ".join(failed)
        run.node_results = results
        run.completed_at = datetime.utcnow()
        db.commit()
        finished = True

        yield "done", {
            "run_id": str(run.id),
            "workflow_id": str(workflow.id),
            "status": run.status,
            "nodes": statuses,
        }

    except Exception as exc:  # erreur interne du moteur (hors agent)
        logger.exception("Workflow %s: engine error", workflow.id)
        db.rollback()
        run.status = "failed"
        run.error = str(exc) or exc.__class__.__name__
        run.node_results = results
        run.completed_at = datetime.utcnow()
        db.commit()
        finished = True
        yield "error", {"type": "error", "error": run.error, "data": {"message": run.error}}
        yield "done", {"run_id": str(run.id), "workflow_id": str(workflow.id), "status": "failed", "nodes": statuses}

    finally:
        if not finished:  # client déconnecté / annulation
            try:
                db.rollback()
                if current_execution is not None:
                    ex = db.query(AgentExecution).filter(AgentExecution.id == current_execution.id).first()
                    if ex is not None and ex.status in ("pending", "running"):
                        ex.status = "failed"
                        ex.output_data = {"error": "Workflow run cancelled"}
                        ex.completed_at = datetime.utcnow()
                db.query(WorkflowRun).filter(WorkflowRun.id == run.id).update(
                    {"status": "cancelled", "node_results": results, "completed_at": datetime.utcnow()},
                    synchronize_session=False,
                )
                db.commit()
            except Exception:
                logger.exception("Workflow %s: could not close cancelled run %s", workflow.id, run.id)
