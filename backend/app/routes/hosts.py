"""
Routes Remote Hosts — /api/hosts

Endpoints :
  POST   /api/hosts              Enregistrer un host (credentials chiffrés en DB)
  GET    /api/hosts/             Lister ses hosts (sans credentials)
  GET    /api/hosts/{id}         Détail d'un host (sans credentials)
  PUT    /api/hosts/{id}         Modifier / rotation credentials
  DELETE /api/hosts/{id}         Supprimer
  POST   /api/hosts/{id}/test    Tester la connexion
  GET    /api/hosts/protocol/{p} Filtrer par protocol (ssh | winrm)
"""
import logging
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models import User
from app.models.remote_host import RemoteHost
from app.utils.security import encrypt_api_key, decrypt_api_key

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/hosts", tags=["Remote Hosts"])

VALID_PROTOCOLS   = {"ssh", "winrm"}
VALID_CRED_TYPES  = {"password", "key", "key+passphrase", "ntlm", "kerberos"}
DEFAULT_PORTS     = {"ssh": 22, "winrm": 5985}


# ── Schemas ────────────────────────────────────────────────────────────────────

class RemoteHostCreate(BaseModel):
    name:             str              = Field(..., min_length=1, max_length=255)
    protocol:         str              = Field(..., pattern="^(ssh|winrm)$")
    host:             str              = Field(..., min_length=1, max_length=255)
    port:             Optional[int]    = None
    username:         str              = Field(..., min_length=1)
    credential_type:  str              = Field(...)
    # Auth fields (en clair à la réception → chiffrés immédiatement)
    password:         Optional[str]    = None
    key_content:      Optional[str]    = None   # PEM string
    key_passphrase:   Optional[str]    = None
    domain:           Optional[str]    = None   # WinRM NTLM
    # WinRM options
    winrm_transport:               Optional[str] = "ntlm"
    winrm_server_cert_validation:  Optional[str] = "ignore"
    # Metadata
    tags:   Optional[List[str]] = []
    notes:  Optional[str]       = None


class RemoteHostUpdate(BaseModel):
    name:             Optional[str]    = None
    host:             Optional[str]    = None
    port:             Optional[int]    = None
    username:         Optional[str]    = None
    credential_type:  Optional[str]    = None
    password:         Optional[str]    = None
    key_content:      Optional[str]    = None
    key_passphrase:   Optional[str]    = None
    domain:           Optional[str]    = None
    winrm_transport:              Optional[str] = None
    winrm_server_cert_validation: Optional[str] = None
    tags:     Optional[List[str]] = None
    notes:    Optional[str]       = None
    is_active: Optional[bool]     = None


class RemoteHostResponse(BaseModel):
    """Réponse publique — jamais de credentials."""
    id:               UUID
    name:             str
    protocol:         str
    host:             str
    port:             Optional[int]
    username:         str
    credential_type:  str
    domain:           Optional[str]
    winrm_transport:  Optional[str]
    tags:             List[str]
    os_info:          Optional[dict]
    notes:            Optional[str]
    is_active:        bool
    last_connected:   Optional[datetime]
    created_at:       datetime

    class Config:
        from_attributes = True


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_host_or_404(host_id: UUID, user_id: UUID, db: Session) -> RemoteHost:
    host = db.query(RemoteHost).filter(
        RemoteHost.id == host_id,
        RemoteHost.user_id == user_id,
    ).first()
    if not host:
        raise HTTPException(404, f"Host {host_id} not found")
    return host


def _encrypt_if_set(value: Optional[str]) -> Optional[str]:
    return encrypt_api_key(value) if value else None


# ── Routes ─────────────────────────────────────────────────────────────────────

@router.post("/", response_model=RemoteHostResponse, status_code=status.HTTP_201_CREATED)
async def create_host(
    payload: RemoteHostCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Enregistre un nouveau host distant.
    Les credentials sont chiffrés immédiatement et jamais retournés en clair.

    Exemples credential_type :
    - SSH par clé    : credential_type="key", key_content="-----BEGIN RSA..."
    - SSH par mdp    : credential_type="password", password="monmdp"
    - WinRM NTLM     : credential_type="ntlm", password="monmdp"
    - WinRM Kerberos : credential_type="kerberos" (auth système)
    """
    if payload.credential_type not in VALID_CRED_TYPES:
        raise HTTPException(400, f"Invalid credential_type. Valid: {VALID_CRED_TYPES}")

    # Vérifier unicité name pour ce user
    existing = db.query(RemoteHost).filter(
        RemoteHost.user_id == current_user.id,
        RemoteHost.name == payload.name,
    ).first()
    if existing:
        raise HTTPException(409, f"Host with name '{payload.name}' already exists")

    host = RemoteHost(
        user_id          = current_user.id,
        name             = payload.name,
        protocol         = payload.protocol,
        host             = payload.host,
        port             = payload.port or DEFAULT_PORTS.get(payload.protocol),
        username         = payload.username,
        credential_type  = payload.credential_type,
        encrypted_password = _encrypt_if_set(payload.password),
        key_content        = _encrypt_if_set(payload.key_content),
        key_passphrase     = _encrypt_if_set(payload.key_passphrase),
        domain             = payload.domain,
        winrm_transport              = payload.winrm_transport,
        winrm_server_cert_validation = payload.winrm_server_cert_validation,
        tags   = payload.tags or [],
        notes  = payload.notes,
    )
    db.add(host)
    db.commit()
    db.refresh(host)
    logger.info(f"RemoteHost created: {host.name} ({host.protocol}://{host.host}) by user {current_user.id}")
    return host


@router.get("/", response_model=List[RemoteHostResponse])
async def list_hosts(
    protocol:  Optional[str]  = None,
    tag:       Optional[str]  = None,
    is_active: Optional[bool] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Liste tous les hosts de l'utilisateur. Filtres optionnels : protocol, tag, is_active."""
    q = db.query(RemoteHost).filter(RemoteHost.user_id == current_user.id)
    if protocol:
        q = q.filter(RemoteHost.protocol == protocol)
    if is_active is not None:
        q = q.filter(RemoteHost.is_active == is_active)
    hosts = q.order_by(RemoteHost.created_at.desc()).all()

    # Filtre tag en Python (JSON array)
    if tag:
        hosts = [h for h in hosts if tag in (h.tags or [])]
    return hosts


@router.get("/protocol/{protocol}", response_model=List[RemoteHostResponse])
async def list_hosts_by_protocol(
    protocol: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Raccourci : GET /api/hosts/protocol/ssh ou /api/hosts/protocol/winrm"""
    if protocol not in VALID_PROTOCOLS:
        raise HTTPException(400, f"Invalid protocol. Valid: {VALID_PROTOCOLS}")
    return db.query(RemoteHost).filter(
        RemoteHost.user_id == current_user.id,
        RemoteHost.protocol == protocol,
        RemoteHost.is_active == True,
    ).all()


@router.get("/{host_id}", response_model=RemoteHostResponse)
async def get_host(
    host_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return _get_host_or_404(host_id, current_user.id, db)


@router.put("/{host_id}", response_model=RemoteHostResponse)
async def update_host(
    host_id: UUID,
    payload: RemoteHostUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Modifier un host. Utilisé pour :
    - Rotation de credentials (nouveau password / nouvelle clé)
    - Modifier les tags, notes
    - Désactiver (is_active=false)
    """
    host = _get_host_or_404(host_id, current_user.id, db)

    update_data = payload.model_dump(exclude_none=True)

    # Chiffrer les credentials si fournis
    if "password" in update_data:
        host.encrypted_password = encrypt_api_key(update_data.pop("password"))
    if "key_content" in update_data:
        host.key_content = encrypt_api_key(update_data.pop("key_content"))
    if "key_passphrase" in update_data:
        host.key_passphrase = encrypt_api_key(update_data.pop("key_passphrase"))

    for field, value in update_data.items():
        setattr(host, field, value)

    host.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(host)
    logger.info(f"RemoteHost updated: {host.name} by user {current_user.id}")
    return host


@router.delete("/{host_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_host(
    host_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    host = _get_host_or_404(host_id, current_user.id, db)
    db.delete(host)
    db.commit()
    logger.info(f"RemoteHost deleted: {host.name} by user {current_user.id}")
    return None


@router.post("/{host_id}/test")
async def test_host_connection(
    host_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Teste la connexion au host.
    SSH  → exécute 'echo ok'
    WinRM → exécute Write-Output 'ok'
    Retourne : {"success": bool, "latency_ms": int, "error": str|null}
    """
    host = _get_host_or_404(host_id, current_user.id, db)
    import time
    start = time.time()

    try:
        if host.protocol == "ssh":
            from app.mcp.servers.ssh_server import SSHMCPServer
            mcp = SSHMCPServer(db=db, user_id=str(current_user.id))
            result = await mcp.exec_command(
                host=host.name, cmd="echo agentrag_ok", timeout=10
            )
            success = result["success"] and "agentrag_ok" in result["stdout"]

        elif host.protocol == "winrm":
            from app.mcp.servers.winrm_server import WinRMMCPServer
            mcp = WinRMMCPServer(db=db, user_id=str(current_user.id))
            result = await mcp.exec_powershell(
                host=host.name, script="Write-Output 'agentrag_ok'"
            )
            success = result["success"] and "agentrag_ok" in result["stdout"]
        else:
            raise ValueError(f"Unknown protocol: {host.protocol}")

        latency_ms = int((time.time() - start) * 1000)

        if success:
            host.last_connected = datetime.utcnow()
            db.commit()

        return {
            "success":    success,
            "latency_ms": latency_ms,
            "host":       host.name,
            "protocol":   host.protocol,
            "error":      result.get("stderr") if not success else None,
        }

    except Exception as e:
        latency_ms = int((time.time() - start) * 1000)
        logger.error(f"Connection test failed for {host.name}: {e}")
        return {
            "success":    False,
            "latency_ms": latency_ms,
            "host":       host.name,
            "protocol":   host.protocol,
            "error":      str(e),
        }