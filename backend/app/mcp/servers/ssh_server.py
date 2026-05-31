"""
SSH MCP Server v2 — résolution credentials depuis table remote_hosts

Prérequis : pip install paramiko
Instanciation depuis AgentExecutor :
    SSHMCPServer(db=db, user_id=str(agent_record.user_id), timeout=30)

Les credentials sont résolus depuis remote_hosts par (user_id, name ou IP).
Plus de key_path ni password dans mcp_config.
"""
import asyncio
import logging
import os
import tempfile
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class SSHMCPServer:

    def __init__(
        self,
        db: Session,
        user_id: str,
        timeout: int = 30,
        **kwargs,
    ):
        self.db = db
        self.user_id = user_id
        self.timeout = timeout
        logger.info(f"SSH MCP initialized for user={user_id}")

    # ── Credential resolution ──────────────────────────────────────────────

    async def _resolve_host(self, host_name: str) -> Dict[str, Any]:
        """
        Résout les credentials depuis remote_hosts par (user_id, name ou IP).

        Args:
            host_name: alias ("web-prod-01") ou IP ("192.168.1.10")

        Returns:
            {"host": str, "port": int, "user": str, "key_content": str|None,
             "password": str|None, "passphrase": str|None, "record": RemoteHost}

        Raises:
            ValueError si host non trouvé ou inactif
        """
        from sqlalchemy import or_
        from app.models.remote_host import RemoteHost
        from app.utils.security import decrypt_api_key

        record = self.db.query(RemoteHost).filter(
            RemoteHost.user_id == UUID(self.user_id),
            RemoteHost.is_active == True,
            RemoteHost.protocol == "ssh",
            or_(
                RemoteHost.name == host_name,
                RemoteHost.host == host_name,
            ),
        ).first()

        if not record:
            raise ValueError(
                f"SSH host '{host_name}' not found or inactive. "
                f"Register it first: POST /api/hosts"
            )

        return {
            "host":       record.host,
            "port":       record.port or 22,
            "user":       record.username,
            "key_content": decrypt_api_key(record.key_content) if record.key_content else None,
            "password":   decrypt_api_key(record.encrypted_password) if record.encrypted_password else None,
            "passphrase": decrypt_api_key(record.key_passphrase) if record.key_passphrase else None,
            "record":     record,
        }

    def _build_client(self, creds):
        import paramiko, tempfile, os
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        connect_kwargs = {
            "hostname": creds["host"],
            "port":     creds["port"],
            "username": creds["user"],
            "timeout":  self.timeout,
        }
        if creds.get("key_content"):
            with tempfile.NamedTemporaryFile(mode="w", suffix=".pem", delete=False) as f:
                f.write(creds["key_content"])
                tmp_path = f.name
            try:
                connect_kwargs["key_filename"] = tmp_path
                if creds.get("passphrase"):
                    connect_kwargs["passphrase"] = creds["passphrase"]
                client.connect(**connect_kwargs)
            finally:
                os.unlink(tmp_path)
        elif creds.get("password"):
            connect_kwargs["password"] = creds["password"]
            client.connect(**connect_kwargs)
        else:
            connect_kwargs["allow_agent"] = True
            client.connect(**connect_kwargs)
        return client

    def _run_sync(self, creds: Dict, cmd: str, timeout: int) -> Dict[str, Any]:
        client = self._build_client(creds)
        try:
            _, stdout, stderr = client.exec_command(cmd, timeout=timeout)
            exit_code = stdout.channel.recv_exit_status()
            return {
                "stdout":    stdout.read().decode("utf-8", errors="replace"),
                "stderr":    stderr.read().decode("utf-8", errors="replace"),
                "exit_code": exit_code,
                "success":   exit_code == 0,
            }
        finally:
            client.close()

    def _upload_sync(self, creds: Dict, local_path: str, remote_path: str):
        client = self._build_client(creds)
        try:
            sftp = client.open_sftp()
            sftp.put(local_path, remote_path)
            sftp.close()
            return {"success": True, "remote_path": remote_path}
        finally:
            client.close()

    def _download_sync(self, creds: Dict, remote_path: str, local_path: str):
        client = self._build_client(creds)
        try:
            sftp = client.open_sftp()
            sftp.get(remote_path, local_path)
            sftp.close()
            return {"success": True, "local_path": local_path}
        finally:
            client.close()

    # ── Update last_connected ──────────────────────────────────────────────

    def _update_last_connected(self, record):
        try:
            record.last_connected = datetime.utcnow()
            self.db.commit()
        except Exception:
            pass

    # ── Public async methods ──────────────────────────────────────────────

    async def exec_command(
        self,
        host: str,
        cmd: str,
        timeout: Optional[int] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """Exécute une commande sur le host (résolu depuis DB)."""
        creds = await self._resolve_host(host)
        timeout = timeout or self.timeout
        logger.info(f"SSH exec on {creds['user']}@{creds['host']}:{creds['port']} → {cmd[:80]}")

        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None, self._run_sync, creds, cmd, timeout
        )
        if result["success"]:
            self._update_last_connected(creds["record"])
        return result

    async def exec_multi(
        self,
        host: str,
        commands: List[str],
        **kwargs,
    ) -> List[Dict[str, Any]]:
        """Exécute plusieurs commandes séquentiellement — s'arrête au premier échec."""
        results = []
        for cmd in commands:
            r = await self.exec_command(host, cmd)
            results.append({"cmd": cmd, **r})
            if not r["success"]:
                break
        return results

    async def check_service(
        self, host: str, service: str, **kwargs
    ) -> Dict[str, Any]:
        result = await self.exec_command(host, f"systemctl status {service} --no-pager")
        return {
            **result,
            "service":   service,
            "is_active": "active (running)" in result["stdout"],
        }

    async def restart_service(
        self, host: str, service: str, **kwargs
    ) -> Dict[str, Any]:
        result = await self.exec_command(host, f"systemctl restart {service}")
        if result["success"]:
            status = await self.check_service(host, service)
            result["is_active"] = status["is_active"]
        return result

    async def get_system_info(
        self, host: str, **kwargs
    ) -> Dict[str, Any]:
        """Détecte l'OS/init du host. Mémorisé dans remote_hosts.os_info."""
        cmds = {
            "uname":    "uname -a",
            "distro":   "cat /etc/os-release 2>/dev/null | head -4 || echo unknown",
            "init":     "systemctl --version 2>/dev/null | head -1 || echo sysvinit",
            "hostname": "hostname",
            "uptime":   "uptime -p",
            "disk":     "df -h / | tail -1",
            "memory":   "free -h | grep Mem",
        }
        info = {}
        for key, cmd in cmds.items():
            r = await self.exec_command(host, cmd)
            info[key] = r["stdout"].strip() if r["success"] else "unknown"

        # Persister os_info dans remote_hosts
        try:
            creds = await self._resolve_host(host)
            creds["record"].os_info = info
            self.db.commit()
        except Exception:
            pass

        return info

    async def upload_file(
        self, host: str, local_path: str, remote_path: str, **kwargs
    ) -> Dict[str, Any]:
        creds = await self._resolve_host(host)
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, self._upload_sync, creds, local_path, remote_path
        )

    async def download_file(
        self, host: str, remote_path: str, local_path: str, **kwargs
    ) -> Dict[str, Any]:
        creds = await self._resolve_host(host)
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, self._download_sync, creds, remote_path, local_path
        )

    # ── Router ────────────────────────────────────────────────────────────

    async def call(self, method: str, params: Dict[str, Any]) -> Any:
        dispatch = {
            "exec_command":    lambda p: self.exec_command(**p),
            "exec_multi":      lambda p: self.exec_multi(**p),
            "check_service":   lambda p: self.check_service(**p),
            "restart_service": lambda p: self.restart_service(**p),
            "get_system_info": lambda p: self.get_system_info(**p),
            "upload_file":     lambda p: self.upload_file(**p),
            "download_file":   lambda p: self.download_file(**p),
        }
        if method not in dispatch:
            raise ValueError(f"Unknown SSH MCP method: '{method}'. Available: {list(dispatch)}")
        return await dispatch[method](params)