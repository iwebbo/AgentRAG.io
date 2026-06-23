"""
Routes Export — POST /api/export/{format}
Formats : pdf | docx | xlsx | html | md
"""
import logging
import urllib.parse
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, Conversation, Message
from app.dependencies import get_current_user
from app.services.export_service import ExportService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/export", tags=["Export"])


# ── Schemas ────────────────────────────────────────────────────────────────────

class ExportRequest(BaseModel):
    """
    Corps de la requête d'export.

    Sources mutuellement exclusives (par ordre de priorité) :
      1. content       — contenu Markdown fourni directement (agent/skill)
      2. message_id    — export d'un seul message de la DB
      3. conversation_id — export de toute la conversation

    Si aucune source n'est fournie → 422.
    """
    content: Optional[str] = None
    conversation_id: Optional[UUID] = None
    message_id: Optional[UUID] = None
    title: Optional[str] = None
    filename: Optional[str] = None          # sans extension
    options: Optional[dict] = {}

    @field_validator("content", "title", "filename", mode="before")
    @classmethod
    def strip_str(cls, v):
        return v.strip() if isinstance(v, str) else v


MIME_MAP = {
    "pdf":  "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "html": "text/html; charset=utf-8",
    "md":   "text/markdown; charset=utf-8",
}

SUPPORTED = set(MIME_MAP.keys())


# ── Helpers ────────────────────────────────────────────────────────────────────

def _conversation_to_markdown(conversation: Conversation) -> str:
    """Sérialise une conversation complète en Markdown structuré."""
    lines = [f"# {conversation.title}\n"]
    lines.append(
        f"_Provider: {conversation.provider_name} · Model: {conversation.model}_\n"
    )
    lines.append("---\n")
    for msg in conversation.messages:
        role_label = "**You**" if msg.role == "user" else "**Assistant**"
        ts = msg.created_at.strftime("%Y-%m-%d %H:%M") if msg.created_at else ""
        lines.append(f"### {role_label}  <sub>{ts}</sub>\n")
        lines.append(msg.content or "")
        lines.append("\n---\n")
    return "\n".join(lines)


def _safe_filename(name: str) -> str:
    """Encode le nom de fichier pour Content-Disposition (RFC 5987)."""
    return urllib.parse.quote(name, safe="")


# ── Routes ─────────────────────────────────────────────────────────────────────

@router.post("/{fmt}")
async def export_content(
    fmt: str,
    request: ExportRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Génère et retourne un fichier dans le format demandé.

    - **fmt** : `pdf` | `docx` | `xlsx` | `html` | `md`
    - Corps : voir `ExportRequest`

    Retourne un `StreamingResponse` avec les bons headers `Content-Disposition`.
    """
    fmt = fmt.lower()
    if fmt not in SUPPORTED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported format '{fmt}'. Supported: {sorted(SUPPORTED)}",
        )

    # ── Résolution du contenu ──────────────────────────────────────────────────
    content: str = ""
    title: str = request.title or "Export"

    if request.content:
        content = request.content

    elif request.message_id:
        msg = (
            db.query(Message)
            .join(Conversation)
            .filter(
                Message.id == request.message_id,
                Conversation.user_id == current_user.id,
            )
            .first()
        )
        if not msg:
            raise HTTPException(status_code=404, detail="Message not found")
        content = msg.content or ""
        title = request.title or f"Message export"

    elif request.conversation_id:
        conv = (
            db.query(Conversation)
            .filter(
                Conversation.id == request.conversation_id,
                Conversation.user_id == current_user.id,
            )
            .first()
        )
        if not conv:
            raise HTTPException(status_code=404, detail="Conversation not found")
        content = _conversation_to_markdown(conv)
        title = request.title or conv.title

    else:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Provide one of: content, message_id, or conversation_id",
        )

    if not content.strip():
        raise HTTPException(status_code=400, detail="Content is empty, nothing to export")

    # ── Rendu ──────────────────────────────────────────────────────────────────
    try:
        svc = ExportService()
        buf, mime, ext = await svc.render(
            content=content,
            fmt=fmt,
            title=title,
            metadata=request.options or {},
        )
    except ImportError as e:
        logger.error(f"Missing dependency for {fmt} export: {e}")
        raise HTTPException(
            status_code=501,
            detail=f"Export format '{fmt}' requires additional dependencies: {e}",
        )
    except Exception as e:
        logger.error(f"Export rendering failed [{fmt}]: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")

    # ── Nom de fichier ─────────────────────────────────────────────────────────
    base_name = request.filename or title
    # Sanitize: enlève les caractères invalides
    import re
    base_name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", base_name)[:100]
    encoded_name = _safe_filename(f"{base_name}.{ext}")

    return StreamingResponse(
        buf,
        media_type=mime,
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_name}",
            "X-Export-Format": fmt,
            "X-Export-Title": title[:100],
        },
    )


@router.get("/formats")
async def list_formats(current_user: User = Depends(get_current_user)):
    """Liste les formats d'export disponibles."""
    return {
        "formats": [
            {"id": "pdf",  "label": "PDF Document",     "mime": MIME_MAP["pdf"],  "icon": "FileText"},
            {"id": "docx", "label": "Word Document",     "mime": MIME_MAP["docx"], "icon": "FileWord"},
            {"id": "xlsx", "label": "Excel Spreadsheet", "mime": MIME_MAP["xlsx"], "icon": "FileSpreadsheet"},
            {"id": "html", "label": "HTML Page",         "mime": MIME_MAP["html"], "icon": "Globe"},
            {"id": "md",   "label": "Markdown",          "mime": MIME_MAP["md"],   "icon": "Hash"},
        ]
    }