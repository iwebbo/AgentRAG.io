"""
SkillRegistry — service d'indexation des skills .md dans sys_skills (Chroma).

Responsabilités :
  - Parser le frontmatter YAML d'un fichier .md
  - Embedder + indexer dans la collection sys_skills
  - CRUD skills (list, get, delete)
  - Créer automatiquement un Agent DB record si type == "agent" (lourd)
"""
import re
import yaml
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from app.services.embeddings import EmbeddingManager
from app.services.vector_store import VectorStore

logger = logging.getLogger(__name__)

SYS_SKILLS_COLLECTION = "sys_skills"


class SkillRegistry:
    """
    Service singleton d'accès à la collection sys_skills.

    Usage :
        registry = SkillRegistry()
        meta = await registry.register_from_md(md_content, user_id="global")
        skills = await registry.list_skills()
        skill = await registry.get_skill("invoice_analyzer")
        await registry.delete_skill("invoice_analyzer")
    """

    def __init__(self):
        self.embeddings = EmbeddingManager()
        self.vector_store = VectorStore()

    # ── Parsing frontmatter ────────────────────────────────────────────────────

    def parse_md(self, content: str) -> Dict[str, Any]:
        """
        Parse un fichier .md avec frontmatter YAML.

        Format attendu :
            ---
            skill_id: invoice_analyzer
            type: skill             # skill | agent
            mcp_servers: []
            project_required: false
            tags: [finance, document]
            description: "Analyse une facture PDF"
            ---

            ## Objectif
            ...

            ## Instructions
            1. ...

        Returns:
            {
                "skill_id": str,
                "type": "skill" | "agent",
                "mcp_servers": list,
                "project_required": bool,
                "tags": list,
                "description": str,
                "body": str,          # contenu sans le frontmatter
                "raw": str,           # contenu complet
            }
        """
        # Extraire frontmatter entre ---
        fm_match = re.match(r"^---\s*\n(.*?)\n---\s*\n", content, re.DOTALL)

        if fm_match:
            try:
                fm = yaml.safe_load(fm_match.group(1)) or {}
            except yaml.YAMLError as e:
                logger.warning(f"YAML parse error in skill .md: {e}")
                fm = {}
            body = content[fm_match.end():]
        else:
            # Fallback : tenter de parser les lignes ## key: value
            fm = {}
            lines = content.splitlines()
            body_lines = []
            for line in lines:
                if line.startswith("## ") and ":" in line:
                    k, _, v = line[3:].partition(":")
                    fm[k.strip().lower()] = v.strip()
                else:
                    body_lines.append(line)
            body = "\n".join(body_lines)

        # Normalisation
        skill_id = fm.get("skill_id") or fm.get("id") or fm.get("name", "").lower().replace(" ", "_")
        if not skill_id:
            raise ValueError(
                "skill_id is required in frontmatter. "
                "Add '--- skill_id: my_skill_name ---' to your .md file."
            )

        return {
            "skill_id": skill_id,
            "type": fm.get("type", "skill"),            # skill | agent
            "mcp_servers": fm.get("mcp_servers", []),
            "project_required": bool(fm.get("project_required", False)),
            "tags": fm.get("tags", []),
            "description": fm.get("description", ""),
            "version": str(fm.get("version", "1.0")),
            "body": body.strip(),
            "raw": content,
        }

    # ── Registration ──────────────────────────────────────────────────────────

    async def register_from_md(
        self,
        md_content: str,
        created_by: str = "system",
    ) -> Dict[str, Any]:
        """
        Parse + embed + indexe un skill .md dans sys_skills.

        Si type == "agent" → signale qu'un Agent DB record doit être créé
        (la route appelante crée le record — le service reste sans DB session).

        Args:
            md_content: Contenu brut du fichier .md
            created_by: user_id ou "system"

        Returns:
            metadata du skill enregistré
        """
        meta = self.parse_md(md_content)
        skill_id = meta["skill_id"]

        # Metadatas stockées en Chroma (doivent être primitives : str/int/float/bool)
        chroma_meta = {
            "skill_id":         skill_id,
            "type":             meta["type"],
            "description":      meta["description"][:500],
            "tags":             ",".join(meta["tags"]),          # liste → str
            "mcp_servers":      ",".join(meta["mcp_servers"]),   # liste → str
            "project_required": meta["project_required"],
            "version":          meta["version"],
            "created_by":       created_by,
            "indexed_at":       datetime.utcnow().isoformat(),
        }

        # Embedding sur le contenu complet (frontmatter + body)
        embedding = self.embeddings.encode_single(md_content)

        self.vector_store.add_documents(
            project_id=SYS_SKILLS_COLLECTION,
            documents=[md_content],
            metadatas=[chroma_meta],
            ids=[skill_id],
            embeddings=[embedding],
            vector_store_type="chroma",
        )

        logger.info(
            f"Skill registered: '{skill_id}' "
            f"(type={meta['type']}, tags={meta['tags']})"
        )
        return {**meta, "chroma_meta": chroma_meta}

    # ── Lecture ───────────────────────────────────────────────────────────────

    async def get_skill(self, skill_id: str) -> Optional[Dict[str, Any]]:
        """
        Récupère un skill par son ID exact.

        Returns:
            {"content": str, "metadata": dict} ou None
        """
        try:
            col = self.vector_store._chroma.get_or_create_collection(
                SYS_SKILLS_COLLECTION
            )
            results = col.get(ids=[skill_id], include=["documents", "metadatas"])
            if results and results["ids"]:
                return {
                    "skill_id": skill_id,
                    "content": results["documents"][0],
                    "metadata": results["metadatas"][0],
                }
            return None
        except Exception as e:
            logger.error(f"get_skill error: {e}")
            return None

    async def list_skills(
        self,
        skill_type: Optional[str] = None,
        tag: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Liste tous les skills indexés.

        Args:
            skill_type: Filtrer par type ("skill" | "agent")
            tag:        Filtrer par tag

        Returns:
            Liste de {"skill_id", "type", "description", "tags", "mcp_servers"}
        """
        try:
            col = self.vector_store._chroma.get_or_create_collection(
                SYS_SKILLS_COLLECTION
            )
            where = {}
            if skill_type:
                where["type"] = skill_type
            if tag:
                # tags est stocké comme string CSV → filtre partiel impossible
                # on filtre en Python après fetch
                pass

            results = col.get(
                where=where if where else None,
                include=["metadatas"],
            )

            skills = []
            if results and results["ids"]:
                for i, sid in enumerate(results["ids"]):
                    m = results["metadatas"][i]
                    if tag and tag not in m.get("tags", ""):
                        continue
                    skills.append({
                        "skill_id":    sid,
                        "type":        m.get("type", "skill"),
                        "description": m.get("description", ""),
                        "tags":        m.get("tags", "").split(","),
                        "mcp_servers": m.get("mcp_servers", "").split(","),
                        "version":     m.get("version", "1.0"),
                        "indexed_at":  m.get("indexed_at"),
                    })
            return skills
        except Exception as e:
            logger.error(f"list_skills error: {e}")
            return []

    async def delete_skill(self, skill_id: str) -> bool:
        """
        Supprime un skill de sys_skills.

        Returns:
            True si supprimé, False si non trouvé
        """
        try:
            col = self.vector_store._chroma.get_or_create_collection(
                SYS_SKILLS_COLLECTION
            )
            existing = col.get(ids=[skill_id], include=[])
            if not existing["ids"]:
                return False
            col.delete(ids=[skill_id])
            logger.info(f"Skill deleted: '{skill_id}'")
            return True
        except Exception as e:
            logger.error(f"delete_skill error: {e}")
            return False

    async def search_skills(
        self,
        query: str,
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Recherche sémantique de skills par description/contenu.
        C'est là que tu surpasses OpenClaw : trouver un skill sans connaître son nom.

        Args:
            query: Description de la tâche
            top_k: Nombre de résultats

        Returns:
            Liste de skills triés par pertinence
        """
        try:
            embedding = self.embeddings.encode_single(query)
            results = self.vector_store.query(
                project_id=SYS_SKILLS_COLLECTION,
                query_embedding=embedding,
                n_results=top_k,
                vector_store_type="chroma",
            )
            skills = []
            if results and results.get("documents"):
                for i, doc in enumerate(results["documents"][0]):
                    m = results["metadatas"][0][i] if results.get("metadatas") else {}
                    skills.append({
                        "skill_id":    m.get("skill_id", ""),
                        "type":        m.get("type", "skill"),
                        "description": m.get("description", ""),
                        "tags":        m.get("tags", "").split(","),
                        "distance":    results["distances"][0][i] if results.get("distances") else None,
                    })
            return skills
        except Exception as e:
            logger.error(f"search_skills error: {e}")
            return []

    async def get_memory_stats(self, skill_id: str) -> Dict[str, Any]:
        """
        Statistiques de mémoire épisodique pour un skill.
        """
        collection = f"sys_memory_{skill_id}"
        try:
            stats = self.vector_store.get_collection_stats(
                project_id=collection,
                vector_store_type="chroma",
            )
            return {"skill_id": skill_id, "memory_collection": collection, **stats}
        except Exception:
            return {"skill_id": skill_id, "memory_collection": collection, "count": 0}