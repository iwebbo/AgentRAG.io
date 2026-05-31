from sqlalchemy import Column, String, Text, JSON, Boolean, Integer, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

from app.database import Base


class RemoteHost(Base):
    """
    Host distant enregistré pour SSH ou WinRM.
    Les credentials sont chiffrés via Fernet (même clé que providers LLM).
    Jamais retournés en clair dans les réponses API.
    """
    __tablename__ = "remote_hosts"

    id      = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    # ── Identification ─────────────────────────────────────────────────────
    name     = Column(String(255), nullable=False)   # alias: "web-prod-01"
    protocol = Column(String(10),  nullable=False)   # "ssh" | "winrm"
    host     = Column(String(255), nullable=False)   # IP ou hostname
    port     = Column(Integer,     nullable=True)    # défaut: 22/5985 si null

    # ── Auth ───────────────────────────────────────────────────────────────
    username        = Column(String(255), nullable=False)
    credential_type = Column(String(30),  nullable=False)
    # "password" | "key" | "key+passphrase" | "ntlm" | "kerberos"

    encrypted_password = Column(Text, nullable=True)  # Fernet chiffré
    key_content        = Column(Text, nullable=True)  # PEM clé privée chiffré
    key_passphrase     = Column(Text, nullable=True)  # passphrase chiffrée
    domain             = Column(String(255), nullable=True)  # pour NTLM

    # ── WinRM spécifique ───────────────────────────────────────────────────
    winrm_transport          = Column(String(20), nullable=True, default="ntlm")
    winrm_server_cert_validation = Column(String(20), nullable=True, default="ignore")

    # ── Metadata ───────────────────────────────────────────────────────────
    tags           = Column(JSON,    default=list)   # ["prod", "linux", "web"]
    os_info        = Column(JSON,    nullable=True)  # détecté au premier run
    notes          = Column(Text,    nullable=True)
    is_active      = Column(Boolean, default=True)
    last_connected = Column(DateTime, nullable=True)
    created_at     = Column(DateTime, default=datetime.utcnow)
    updated_at     = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # ── Contraintes ────────────────────────────────────────────────────────
    __table_args__ = (
        UniqueConstraint("user_id", "name", name="uq_remote_host_user_name"),
    )

    def __repr__(self):
        return f"<RemoteHost {self.name} ({self.protocol}://{self.host})>"