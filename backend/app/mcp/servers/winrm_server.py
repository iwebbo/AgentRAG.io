"""
WinRM MCP Server v3
===================
- exec_command() alias de exec_powershell() — cohérence avec ssh_server
- $WarningPreference = 'SilentlyContinue' sur tous les scripts
  → supprime les warnings WMI qui génèrent du XML malformé dans stderr
- get_system_info() migré vers CIM (remplacement moderne de WMI)
"""
import asyncio
import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# Préfixe injecté sur tous les scripts PS pour supprimer les warnings WMI/CIM
_PS_SILENT_PREFIX = "$WarningPreference = 'SilentlyContinue'\n$ErrorActionPreference = 'Stop'\n"


class WinRMMCPServer:

    def __init__(
        self,
        db: Session,
        user_id: str,
        timeout: int = 60,
        **kwargs,
    ):
        self.db = db
        self.user_id = user_id
        self.timeout = timeout
        logger.info(f"WinRM MCP initialized for user={user_id}")

    # ── Credential resolution ──────────────────────────────────────────────

    async def _resolve_host(self, host_name: str) -> Dict[str, Any]:
        from sqlalchemy import or_
        from app.models.remote_host import RemoteHost
        from app.utils.security import decrypt_api_key

        record = self.db.query(RemoteHost).filter(
            RemoteHost.user_id == UUID(self.user_id),
            RemoteHost.is_active == True,
            RemoteHost.protocol == "winrm",
            or_(
                RemoteHost.name == host_name,
                RemoteHost.host == host_name,
            ),
        ).first()

        if not record:
            raise ValueError(
                f"WinRM host '{host_name}' not found or inactive. "
                f"Register it first: POST /api/hosts"
            )

        return {
            "host":       record.host,
            "port":       record.port or 5985,
            "user":       record.username,
            "password":   decrypt_api_key(record.encrypted_password) if record.encrypted_password else "",
            "domain":     record.domain or "",
            "transport":  record.winrm_transport or "ntlm",
            "cert_valid": record.winrm_server_cert_validation or "ignore",
            "record":     record,
        }

    def _build_session(self, creds: Dict[str, Any]):
        try:
            import winrm
        except ImportError:
            raise RuntimeError("pywinrm not installed. Run: pip install pywinrm")

        scheme = "https" if creds["port"] == 5986 else "http"
        return winrm.Session(
            f"{scheme}://{creds['host']}:{creds['port']}/wsman",
            auth=(creds["user"], creds["password"]),
            transport=creds["transport"],
            server_cert_validation=creds["cert_valid"],
            read_timeout_sec=self.timeout,
            operation_timeout_sec=self.timeout - 5,
        )

    def _run_ps_sync(self, creds: Dict, script: str) -> Dict[str, Any]:
        """Exécute un script PowerShell. Préfixe silence warnings automatiquement."""
        import warnings
        session = self._build_session(creds)
        # Injecter le préfixe silence sur tous les scripts
        full_script = _PS_SILENT_PREFIX + script
        # Supprimer le UserWarning pywinrm XML parser au niveau Python aussi
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            result = session.run_ps(full_script)
        return {
            "stdout":    result.std_out.decode("utf-8", errors="replace").strip(),
            "stderr":    result.std_err.decode("utf-8", errors="replace").strip(),
            "exit_code": result.status_code,
            "success":   result.status_code == 0,
        }

    def _run_cmd_sync(self, creds: Dict, cmd: str, args: List[str]) -> Dict[str, Any]:
        import warnings
        session = self._build_session(creds)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            result = session.run_cmd(cmd, args)
        return {
            "stdout":    result.std_out.decode("utf-8", errors="replace").strip(),
            "stderr":    result.std_err.decode("utf-8", errors="replace").strip(),
            "exit_code": result.status_code,
            "success":   result.status_code == 0,
        }

    def _update_last_connected(self, record):
        try:
            record.last_connected = datetime.utcnow()
            self.db.commit()
        except Exception:
            pass

    # ── Public async methods ──────────────────────────────────────────────

    async def exec_command(
        self, host: str, cmd: str, timeout: Optional[int] = None, **kwargs
    ) -> Dict[str, Any]:
        """Execute a PowerShell command or script on the remote Windows host."""
        return await self.exec_powershell(host, cmd, timeout=timeout)

    async def exec_powershell(
        self, host: str, script: str, timeout: Optional[int] = None, **kwargs
    ) -> Dict[str, Any]:
        """Execute a PowerShell script on the remote Windows host."""
        creds = await self._resolve_host(host)
        logger.info(f"WinRM PS on {creds['user']}@{creds['host']} → {script[:80]}")
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None, self._run_ps_sync, creds, script
        )
        if result["success"]:
            self._update_last_connected(creds["record"])
        return result

    async def exec_multi(
        self, host: str, commands: List[str], **kwargs
    ) -> List[Dict[str, Any]]:
        """Execute multiple PowerShell commands sequentially — stops on first failure."""
        results = []
        for cmd in commands:
            r = await self.exec_command(host, cmd)
            results.append({"cmd": cmd, **r})
            if not r["success"]:
                break
        return results

    async def exec_cmd(
        self, host: str, cmd: str, args: Optional[List[str]] = None, **kwargs
    ) -> Dict[str, Any]:
        """Execute a cmd.exe command (non-PowerShell) on the remote Windows host."""
        creds = await self._resolve_host(host)
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, self._run_cmd_sync, creds, cmd, args or []
        )

    async def check_service(
        self, host: str, service: str, **kwargs
    ) -> Dict[str, Any]:
        """Check the status of a Windows service."""
        script = f"Get-Service -Name '{service}' | Select-Object Name, Status, StartType | ConvertTo-Json -Compress"
        result = await self.exec_powershell(host, script)
        try:
            svc = json.loads(result["stdout"])
            result["service"]    = svc
            result["is_running"] = svc.get("Status") == 4
        except Exception:
            result["is_running"] = "Running" in result["stdout"]
        return result

    async def restart_service(
        self, host: str, service: str, **kwargs
    ) -> Dict[str, Any]:
        """Restart a Windows service."""
        script = f"Restart-Service -Name '{service}' -Force; Get-Service '{service}' | Select Status | ConvertTo-Json -Compress"
        return await self.exec_powershell(host, script)

    async def stop_service(self, host: str, service: str, **kwargs) -> Dict[str, Any]:
        """Stop a Windows service."""
        return await self.exec_powershell(host, f"Stop-Service -Name '{service}' -Force")

    async def start_service(self, host: str, service: str, **kwargs) -> Dict[str, Any]:
        """Start a Windows service."""
        return await self.exec_powershell(host, f"Start-Service -Name '{service}'")

    async def get_event_logs(
        self,
        host: str,
        log_name: str = "System",
        level: int = 2,
        count: int = 20,
        **kwargs,
    ) -> Dict[str, Any]:
        """Retrieve Windows event log entries filtered by level."""
        script = f"""
Get-WinEvent -LogName '{log_name}' -MaxEvents {count} |
Where-Object {{$_.Level -le {level}}} |
Select-Object TimeCreated, Id, LevelDisplayName, Message |
ConvertTo-Json -Compress
"""
        return await self.exec_powershell(host, script)

    async def get_system_info(self, host: str, **kwargs) -> Dict[str, Any]:
        """Collect OS, memory, CPU and disk info. Persists to remote_hosts.os_info."""
        # CIM remplace WMI (plus de warnings XML)
        script = """
$os   = Get-CimInstance Win32_OperatingSystem
$cpu  = Get-CimInstance Win32_Processor | Select-Object -First 1
$cs   = Get-CimInstance Win32_ComputerSystem
$disk = Get-PSDrive C
$info = @{
    OS             = $os.Caption
    Version        = $os.Version
    Hostname       = $env:COMPUTERNAME
    Mem_GB         = [math]::Round($cs.TotalPhysicalMemory / 1GB, 2)
    CPU            = $cpu.Name
    Disk_C_Free_GB = [math]::Round($disk.Free / 1GB, 2)
}
$info | ConvertTo-Json -Compress
"""
        result = await self.exec_powershell(host, script)
        if result["success"]:
            try:
                os_info = json.loads(result["stdout"])
                creds = await self._resolve_host(host)
                creds["record"].os_info = os_info
                self.db.commit()
            except Exception:
                pass
        return result

    async def get_running_processes(
        self, host: str, top_n: int = 15, **kwargs
    ) -> Dict[str, Any]:
        """List top N processes sorted by memory usage."""
        script = f"""
Get-Process | Sort-Object WorkingSet64 -Descending | Select-Object -First {top_n} `
  Name, Id, @{{N='Memory_MB';E={{[math]::Round($_.WorkingSet64/1MB,1)}}}}, CPU |
ConvertTo-Json -Compress
"""
        return await self.exec_powershell(host, script)

    async def list_services(
        self, host: str, status: str = "All", **kwargs
    ) -> Dict[str, Any]:
        """List Windows services, optionally filtered by status (Running/Stopped/All)."""
        f = f"| Where-Object {{$_.Status -eq '{status}'}}" if status != "All" else ""
        script = f"Get-Service {f} | Select-Object Name, DisplayName, Status, StartType | ConvertTo-Json -Compress"
        return await self.exec_powershell(host, script)

    async def exec_cleanup(self, host: str, **kwargs) -> Dict[str, Any]:
        """Clean temp files and run garbage collection."""
        script = """
Remove-Item $env:TEMP\\* -Recurse -Force -ErrorAction SilentlyContinue
[gc]::Collect()
Write-Output 'Cleanup done'
"""
        return await self.exec_powershell(host, script)

    # ── Router ────────────────────────────────────────────────────────────

    async def call(self, method: str, params: Dict[str, Any]) -> Any:
        dispatch = {
            "exec_command":          lambda p: self.exec_command(**p),
            "exec_powershell":       lambda p: self.exec_powershell(**p),
            "exec_cmd":              lambda p: self.exec_cmd(**p),
            "exec_multi":            lambda p: self.exec_multi(**p),
            "check_service":         lambda p: self.check_service(**p),
            "restart_service":       lambda p: self.restart_service(**p),
            "stop_service":          lambda p: self.stop_service(**p),
            "start_service":         lambda p: self.start_service(**p),
            "get_event_logs":        lambda p: self.get_event_logs(**p),
            "get_system_info":       lambda p: self.get_system_info(**p),
            "get_running_processes": lambda p: self.get_running_processes(**p),
            "list_services":         lambda p: self.list_services(**p),
            "exec_cleanup":          lambda p: self.exec_cleanup(**p),
        }
        if method not in dispatch:
            raise ValueError(
                f"Unknown WinRM MCP method: '{method}'. Available: {list(dispatch)}"
            )
        return await dispatch[method](params)