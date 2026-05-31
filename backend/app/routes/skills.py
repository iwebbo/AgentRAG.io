"""
Routes Skills — /api/skills
"""
import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, Agent
from app.dependencies import get_current_user
from app.services.skill_registry import SkillRegistry

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/skills", tags=["Skills"])

_registry: Optional[SkillRegistry] = None


def get_registry() -> SkillRegistry:
    global _registry
    if _registry is None:
        _registry = SkillRegistry()
    return _registry


# ── Schemas ────────────────────────────────────────────────────────────────────

class SkillListItem(BaseModel):
    skill_id: str
    type: str
    description: str
    tags: List[str]
    mcp_servers: List[str]
    version: str
    indexed_at: Optional[str] = None


class SkillSearchResult(BaseModel):
    skill_id: str
    type: str
    description: str
    tags: List[str]
    distance: Optional[float] = None


class SkillRegisterResponse(BaseModel):
    skill_id: str
    type: str
    description: str
    tags: List[str]
    mcp_servers: List[str]
    agent_created: bool = False
    agent_id: Optional[str] = None
    message: str


class AgentCreateForSkill(BaseModel):
    name: str
    description: Optional[str] = None
    project_id: Optional[str] = None


# ── Routes ─────────────────────────────────────────────────────────────────────

@router.post("/register", response_model=SkillRegisterResponse, status_code=status.HTTP_201_CREATED)
async def register_skill(
    file: UploadFile = File(None, description="Fichier .md du skill"),
    md_content: str = Form(None, description="Contenu .md (alternative au fichier)"),
    auto_create_agent: bool = Form(False, description="Créer automatiquement un Agent DB"),
    project_id: Optional[str] = Form(None, description="Project RAG à lier si auto_create_agent"),
    # ── LLM config — injectés dans agent.config si fournis ────────────────
    llm_provider: Optional[str] = Form(None, description="Provider LLM (ex: lmstudio, ollama)"),
    llm_model: Optional[str] = Form(None, description="Modèle LLM (ex: openai/gpt-oss-20b)"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    registry: SkillRegistry = Depends(get_registry),
):
    """
    Enregistre un skill .md dans sys_skills (ChromaDB).

    Si auto_create_agent=true (ou type=agent dans le frontmatter),
    crée un Agent DB de type "skill" avec config complète incluant
    llm_provider et llm_model si fournis.
    """
    # ── Résolution du contenu ─────────────────────────────────────────────
    if file:
        if not file.filename.endswith(".md"):
            raise HTTPException(400, "File must be a .md file")
        content = (await file.read()).decode("utf-8")
    elif md_content:
        content = md_content
    else:
        raise HTTPException(400, "Provide either 'file' or 'md_content'")

    try:
        meta = await registry.register_from_md(
            md_content=content,
            created_by=str(current_user.id),
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        logger.error(f"Skill registration error: {e}")
        raise HTTPException(500, f"Registration failed: {str(e)}")

    agent_id = None
    agent_created = False

    # ── Créer un Agent DB si demandé ──────────────────────────────────────
    if auto_create_agent or meta["type"] == "agent":
        existing = db.query(Agent).filter(
            Agent.user_id == current_user.id,
            Agent.name == meta["skill_id"],
        ).first()

        if not existing:
            # Construire config — merge frontmatter + llm params
            config = {"skill_id": meta["skill_id"]}

            if project_id:
                config["project_id"] = project_id
            if meta.get("mcp_servers"):
                config["mcp_servers"] = meta["mcp_servers"]
            if llm_provider:
                config["llm_provider"] = llm_provider
            if llm_model:
                config["llm_model"] = llm_model

            agent = Agent(
                user_id=current_user.id,
                name=meta["skill_id"],
                description=meta.get("description", ""),
                agent_type="skill",
                config=config,
                mcp_config={},
                is_active=True,
            )
            db.add(agent)
            db.commit()
            db.refresh(agent)
            agent_id = str(agent.id)
            agent_created = True
            logger.info(
                f"Agent created for skill '{meta['skill_id']}': {agent.id} "
                f"(provider={llm_provider}, model={llm_model})"
            )
        else:
            # Agent existe déjà — mettre à jour llm_provider/llm_model si fournis
            if llm_provider or llm_model:
                updated_config = dict(existing.config or {})
                if llm_provider:
                    updated_config["llm_provider"] = llm_provider
                if llm_model:
                    updated_config["llm_model"] = llm_model
                existing.config = updated_config
                db.commit()
                logger.info(
                    f"Agent '{existing.id}' config updated: "
                    f"provider={llm_provider}, model={llm_model}"
                )
            agent_id = str(existing.id)

    return SkillRegisterResponse(
        skill_id=meta["skill_id"],
        type=meta["type"],
        description=meta.get("description", ""),
        tags=meta.get("tags", []),
        mcp_servers=meta.get("mcp_servers", []),
        agent_created=agent_created,
        agent_id=agent_id,
        message=(
            f"Skill '{meta['skill_id']}' registered successfully"
            + (f" and agent created ({agent_id})" if agent_created else "")
        ),
    )


@router.get("/", response_model=List[SkillListItem])
async def list_skills(
    skill_type: Optional[str] = None,
    tag: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    registry: SkillRegistry = Depends(get_registry),
):
    skills = await registry.list_skills(skill_type=skill_type, tag=tag)
    return [SkillListItem(**s) for s in skills]


@router.get("/search", response_model=List[SkillSearchResult])
async def search_skills(
    q: str,
    top_k: int = 5,
    current_user: User = Depends(get_current_user),
    registry: SkillRegistry = Depends(get_registry),
):
    if not q or len(q.strip()) < 3:
        raise HTTPException(400, "Query must be at least 3 characters")
    skills = await registry.search_skills(query=q, top_k=top_k)
    return [SkillSearchResult(**s) for s in skills]


@router.get("/{skill_id}")
async def get_skill(
    skill_id: str,
    current_user: User = Depends(get_current_user),
    registry: SkillRegistry = Depends(get_registry),
):
    skill = await registry.get_skill(skill_id)
    if not skill:
        raise HTTPException(404, f"Skill '{skill_id}' not found")
    return skill


@router.delete("/{skill_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_skill(
    skill_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    registry: SkillRegistry = Depends(get_registry),
):
    deleted = await registry.delete_skill(skill_id)
    if not deleted:
        raise HTTPException(404, f"Skill '{skill_id}' not found")

    agents = db.query(Agent).filter(
        Agent.user_id == current_user.id,
        Agent.agent_type == "skill",
    ).all()
    for agent in agents:
        if agent.config.get("skill_id") == skill_id:
            agent.is_active = False
    db.commit()
    return None


@router.get("/{skill_id}/memory")
async def get_skill_memory_stats(
    skill_id: str,
    current_user: User = Depends(get_current_user),
    registry: SkillRegistry = Depends(get_registry),
):
    skill = await registry.get_skill(skill_id)
    if not skill:
        raise HTTPException(404, f"Skill '{skill_id}' not found")
    return await registry.get_memory_stats(skill_id)