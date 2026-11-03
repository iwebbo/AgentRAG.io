"""
Routes Remote Hosts — /api/hosts

Protocols : ssh | winrm | psrp | db

Endpoints :
  POST   /api/hosts              Enregistrer un host (credentials chiffrés en DB)
  GET    /api/hosts/             Lister ses hosts (sans credentials)
  GET    /api/hosts/{id}         Détail d'un host (sans credentials)
  PUT    /api/hosts/{id}         Modifier / rotation credentials
  DELETE /api/hosts/{id}         Supprimer
  POST   /api/hosts/{id}/test    Tester la connexion (via le MCP server du protocol)
  GET    /api/hosts/protocol/{p} Filtrer par protocol (ssh | winrm | psrp | db)
"""
import logging
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models import User
from app.models.remote_host import RemoteHost
from app.utils.security import encrypt_api_key

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/hosts", tags=["Remote Hosts"])

VALID_PROTOCOLS  = {"ssh", "winrm", "psrp", "db"}
VALID_CRED_TYPES = {"password", "key", "key+passphrase", "ntlm", "kerberos", "negotiate", "credssp"}
DEFAULT_PORTS    = {"ssh": 22, "winrm": 5985, "psrp": 5985}

# Restriction des credential_type par protocol (ssh / winrm : comportement historique inchangé)
PROTOCOL_CRED_TYPES = {
    "psrp": {"password", "ntlm", "negotiate", "kerberos", "credssp"},
    "db":   {"password"},
}

# ── PSRP ──────────────────────────────────────────────────────────────────────
PSRP_TRANSPORTS = {"negotiate", "ntlm", "kerberos", "basic", "credssp"}   # → pypsrp `auth`
PSRP_AUTH_CRED_TYPES = {"ntlm", "negotiate", "kerberos", "credssp"}       # credential_type → transport

# ── DB ────────────────────────────────────────────────────────────────────────
DB_TYPE_ALIASES = {
    "mysql": "mysql", "mariadb": "mariadb",
    "postgresql": "postgresql", "postgres": "postgresql", "pg": "postgresql",
    "mssql": "mssql", "sqlserver": "mssql",
}
DB_DEFAULT_PORTS = {"mysql": 3306, "mariadb": 3306, "postgresql": 5432, "mssql": 1433}

# kwargs driver autorisés dans db_options (liste blanche : pas d'init_command, local_infile, etc.)
DB_ALLOWED_OPTIONS = {
    "mysql":      {"ssl", "ssl_ca", "ssl_cert", "ssl_key", "ssl_verify_cert", "ssl_verify_identity"},
    "mariadb":    {"ssl", "ssl_ca", "ssl_cert", "ssl_key", "ssl_verify_cert", "ssl_verify_identity"},
    "postgresql": {"sslmode", "sslrootcert", "sslcert", "sslkey", "application_name"},
    "mssql":      {"tds_version", "appname"},
}


# ── Schemas ────────────────────────────────────────────────────────────────────

class RemoteHostCreate(BaseModel):
    name:             str              = Field(..., min_length=1, max_length=255)
    protocol:         str              = Field(..., pattern="^(ssh|winrm|psrp|db)$")
    host:             str              = Field(..., min_length=1, max_length=255)
    port:             Optional[int]    = Field(None, ge=1, le=65535)
    username:         str              = Field(..., min_length=1)
    credential_type:  str              = Field(...)
    # Auth fields (en clair à la réception → chiffrés immédiatement)
    password:         Optional[str]    = None
    key_content:      Optional[str]    = None   # PEM string (ssh)
    key_passphrase:   Optional[str]    = None
    domain:           Optional[str]    = None   # WinRM / PSRP NTLM
    # WinRM / PSRP options (PSRP : winrm_transport = méthode d'auth pypsrp)
    winrm_transport:               Optional[str] = None
    winrm_server_cert_validation:  Optional[str] = None
    # DB options (protocol=db)
    db_type:     Optional[str]            = None   # mysql | mariadb | postgresql | mssql
    db_name:     Optional[str]            = Field(None, max_length=128)   # base par défaut
    db_options:  Optional[Dict[str, Any]] = None   # kwargs driver (liste blanche)
    # Metadata
    tags:   Optional[List[str]] = []
    notes:  Optional[str]       = None


class RemoteHostUpdate(BaseModel):
    name:             Optional[str]    = None
    host:             Optional[str]    = None
    port:             Optional[int]    = Field(None, ge=1, le=65535)
    username:         Optional[str]    = None
    credential_type:  Optional[str]    = None
    password:         Optional[str]    = None
    key_content:      Optional[str]    = None
    key_passphrase:   Optional[str]    = None
    domain:           Optional[str]    = None
    winrm_transport:              Optional[str] = None
    winrm_server_cert_validation: Optional[str] = None
    db_type:     Optional[str]            = None
    db_name:     Optional[str]            = Field(None, max_length=128)
    db_options:  Optional[Dict[str, Any]] = None
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
    db_type:          Optional[str] = None
    db_name:          Optional[str] = None
    db_options:       Optional[dict] = None
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


def _check_credential_type(protocol: str, credential_type: str) -> None:
    if credential_type not in VALID_CRED_TYPES:
        raise HTTPException(400, f"Invalid credential_type. Valid: {sorted(VALID_CRED_TYPES)}")
    allowed = PROTOCOL_CRED_TYPES.get(protocol)
    if allowed and credential_type not in allowed:
        raise HTTPException(
            400, f"credential_type '{credential_type}' invalid for protocol '{protocol}'. Valid: {sorted(allowed)}"
        )


def _normalize_db_type(value: Optional[str]) -> str:
    t = DB_TYPE_ALIASES.get((value or "").strip().lower())
    if not t:
        raise HTTPException(400, f"Invalid or missing db_type. Valid: {sorted(set(DB_TYPE_ALIASES.values()))}")
    return t


def _check_db_options(db_type: str, options: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not options:
        return None
    unknown = set(options) - DB_ALLOWED_OPTIONS[db_type]
    if unknown:
        raise HTTPException(
            400, f"Unsupported db_options for {db_type}: {sorted(unknown)}. "
                 f"Allowed: {sorted(DB_ALLOWED_OPTIONS[db_type])}"
        )
    return options


def _check_psrp_transport(transport: str) -> str:
    if transport not in PSRP_TRANSPORTS:
        raise HTTPException(400, f"Invalid winrm_transport for psrp. Valid: {sorted(PSRP_TRANSPORTS)}")
    return transport


async def _probe_host(host: RemoteHost, db: Session, user_id: UUID) -> Tuple[bool, Optional[str]]:
    """Appelle le MCP server du protocol. Retourne (success, error)."""
    uid = str(user_id)

    if host.protocol == "ssh":
        from app.mcp.servers.ssh_server import SSHMCPServer
        mcp = SSHMCPServer(db=db, user_id=uid)
        result = await mcp.exec_command(host=host.name, cmd="echo agentrag_ok", timeout=10)
        success = result["success"] and "agentrag_ok" in result["stdout"]

    elif host.protocol == "winrm":
        from app.mcp.servers.winrm_server import WinRMMCPServer
        mcp = WinRMMCPServer(db=db, user_id=uid)
        result = await mcp.exec_powershell(host=host.name, script="Write-Output 'agentrag_ok'")
        success = result["success"] and "agentrag_ok" in result["stdout"]

    elif host.protocol == "psrp":
        from app.mcp.servers.psrp_server import PSRPMCPServer
        mcp = PSRPMCPServer(db=db, user_id=uid)
        result = await mcp.exec_powershell(
            host=host.name, script="Write-Output 'agentrag_ok'", timeout=15
        )
        success = result["success"] and "agentrag_ok" in result["stdout"]

    elif host.protocol == "db":
        from app.mcp.servers.db_server import DBMCPServer
        mcp = DBMCPServer(db=db, user_id=uid)
        result = await mcp.test_connection(host=host.name)
        success = bool(result["success"])

    else:
        raise ValueError(f"Unknown protocol: {host.protocol}")

    return success, (None if success else (result.get("stderr") or result.get("error") or "connection test failed"))


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

    Exemples :
    - SSH par clé    : protocol="ssh",   credential_type="key", key_content="-----BEGIN RSA..."
    - SSH par mdp    : protocol="ssh",   credential_type="password", password="monmdp"
    - WinRM NTLM     : protocol="winrm", credential_type="ntlm", password="monmdp"
    - PSRP NTLM      : protocol="psrp",  credential_type="ntlm", password="monmdp"
    - PSRP Kerberos  : protocol="psrp",  credential_type="kerberos" (ticket système, sans password)
    - DB             : protocol="db", credential_type="password", username="app", password="***",
                       db_type="mysql", db_name="appdb", port=3306 (défaut selon db_type), tags=["db"]
    """
    _check_credential_type(payload.protocol, payload.credential_type)

    # Vérifier unicité name pour ce user
    existing = db.query(RemoteHost).filter(
        RemoteHost.user_id == current_user.id,
        RemoteHost.name == payload.name,
    ).first()
    if existing:
        raise HTTPException(409, f"Host with name '{payload.name}' already exists")

    port = payload.port or DEFAULT_PORTS.get(payload.protocol)
    transport: Optional[str] = None
    cert_validation: Optional[str] = None
    db_type = db_name = db_options = None

    if payload.protocol != "db" and (payload.db_type or payload.db_name or payload.db_options):
        raise HTTPException(400, "db_type / db_name / db_options are only valid for protocol='db'")

    if payload.protocol == "winrm":
        transport = payload.winrm_transport or "ntlm"
        cert_validation = payload.winrm_server_cert_validation or "ignore"

    elif payload.protocol == "psrp":
        transport = _check_psrp_transport(
            payload.winrm_transport
            or (payload.credential_type if payload.credential_type in PSRP_AUTH_CRED_TYPES else "negotiate")
        )
        cert_validation = payload.winrm_server_cert_validation or "ignore"
        if transport != "kerberos" and not payload.password:
            raise HTTPException(400, f"password is required for psrp transport '{transport}'")

    elif payload.protocol == "db":
        db_type = _normalize_db_type(payload.db_type)
        db_name = payload.db_name
        db_options = _check_db_options(db_type, payload.db_options)
        port = payload.port or DB_DEFAULT_PORTS[db_type]
        if not payload.password:
            raise HTTPException(400, "password is required for protocol='db'")

    host = RemoteHost(
        user_id          = current_user.id,
        name             = payload.name,
        protocol         = payload.protocol,
        host             = payload.host,
        port             = port,
        username         = payload.username,
        credential_type  = payload.credential_type,
        encrypted_password = _encrypt_if_set(payload.password),
        key_content        = _encrypt_if_set(payload.key_content),
        key_passphrase     = _encrypt_if_set(payload.key_passphrase),
        domain             = payload.domain,
        winrm_transport              = transport,
        winrm_server_cert_validation = cert_validation,
        db_type    = db_type,
        db_name    = db_name,
        db_options = db_options,
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
    """Raccourci : GET /api/hosts/protocol/{ssh|winrm|psrp|db}"""
    if protocol not in VALID_PROTOCOLS:
        raise HTTPException(400, f"Invalid protocol. Valid: {sorted(VALID_PROTOCOLS)}")
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
    - Modifier les tags, notes, db_name, db_options
    - Désactiver (is_active=false)
    Le protocol n'est pas modifiable.
    """
    host = _get_host_or_404(host_id, current_user.id, db)

    update_data = payload.model_dump(exclude_none=True)

    if "name" in update_data and update_data["name"] != host.name:
        clash = db.query(RemoteHost).filter(
            RemoteHost.user_id == current_user.id,
            RemoteHost.name == update_data["name"],
        ).first()
        if clash:
            raise HTTPException(409, f"Host with name '{update_data['name']}' already exists")

    if "credential_type" in update_data:
        _check_credential_type(host.protocol, update_data["credential_type"])

    if host.protocol != "db" and any(k in update_data for k in ("db_type", "db_name", "db_options")):
        raise HTTPException(400, "db_type / db_name / db_options are only valid for protocol='db'")

    if host.protocol == "psrp" and "winrm_transport" in update_data:
        _check_psrp_transport(update_data["winrm_transport"])

    if host.protocol == "db":
        if "db_type" in update_data:
            update_data["db_type"] = _normalize_db_type(update_data["db_type"])
        if "db_options" in update_data:
            effective_type = update_data.get("db_type") or host.db_type
            _check_db_options(effective_type, update_data["db_options"])

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
    Teste la connexion au host via le MCP server correspondant.
    SSH   → ssh_server.exec_command('echo agentrag_ok')
    WinRM → winrm_server.exec_powershell("Write-Output 'agentrag_ok'")
    PSRP  → psrp_server.exec_powershell("Write-Output 'agentrag_ok'")
    DB    → db_server.test_connection()  (SELECT 'agentrag_ok')
    Retourne : {"success": bool, "latency_ms": int, "error": str|null}
    """
    host = _get_host_or_404(host_id, current_user.id, db)
    start = time.time()

    try:
        success, error = await _probe_host(host, db, current_user.id)
        latency_ms = int((time.time() - start) * 1000)

        if success:
            host.last_connected = datetime.utcnow()
            db.commit()

        return {
            "success":    success,
            "latency_ms": latency_ms,
            "host":       host.name,
            "protocol":   host.protocol,
            "error":      error,
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