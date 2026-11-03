"""
PSRP MCP Server v1
==================
PowerShell Remoting Protocol (PSRP) — successeur de WinRM `run_ps`.
"""
import asyncio
import json
import logging
import subprocess
import warnings
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

_PS_PREFIX = (
    "$WarningPreference = 'SilentlyContinue'\n"
    "$ProgressPreference = 'SilentlyContinue'\n"
    "$ErrorActionPreference = 'Stop'\n"
)

_AUTH_MAP = {
    "negotiate": "negotiate",
    "ntlm":      "ntlm",
    "kerberos":  "kerberos",
    "basic":     "basic",
    "plaintext": "basic",
    "credssp":   "credssp",
}

_VALID_SERVICE_STATUS = {"All", "Running", "Stopped", "Paused"}


def _ps_quote(value: Any) -> str:
    """Littéral PowerShell single-quoted sûr (double les apostrophes)."""
    return "'" + str(value).replace("'", "''") + "'"


class PSRPMCPServer:

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
        logger.info(f"PSRP MCP initialized for user={user_id}")

    # ── Credential resolution ──────────────────────────────────────────────

    async def _resolve_host(self, host_name: str) -> Dict[str, Any]:
        from sqlalchemy import or_
        from app.models.remote_host import RemoteHost
        from app.utils.security import decrypt_api_key

        record = self.db.query(RemoteHost).filter(
            RemoteHost.user_id == UUID(self.user_id),
            RemoteHost.is_active == True,
            RemoteHost.protocol == "psrp",
            or_(
                RemoteHost.name == host_name,
                RemoteHost.host == host_name,
            ),
        ).first()

        if not record:
            raise ValueError(
                f"PSRP host '{host_name}' not found or inactive. "
                f"Register it first: POST /api/hosts (protocol=psrp)"
            )

        username = record.username or ""
        domain = record.domain or ""
        if domain and "\\" not in username and "@" not in username:
            username = f"{domain}\\{username}"

        auth = _AUTH_MAP.get((record.winrm_transport or "negotiate").lower(), "negotiate")
        port = record.port or 5985
        password = (
            decrypt_api_key(record.encrypted_password) if record.encrypted_password else None
        )

        return {
            "host":       record.host,
            "port":       port,
            "ssl":        port == 5986,
            "user":       username,
            "password":   password,   # None → Kerberos via ticket cache
            "auth":       auth,
            "cert_valid": (record.winrm_server_cert_validation or "ignore").lower() != "ignore",
            "record":     record,
        }

    # ── Connection builders ────────────────────────────────────────────────

    @staticmethod
    def _timeouts(timeout: int) -> Dict[str, int]:
        timeout = max(int(timeout), 10)
        return {
            "connection_timeout": min(timeout, 30),
            "operation_timeout":  timeout,
            "read_timeout":       timeout + 10,   # pypsrp exige read_timeout > operation_timeout
        }

    def _build_wsman(self, creds: Dict[str, Any], timeout: int):
        try:
            from pypsrp.wsman import WSMan
        except ImportError:
            raise RuntimeError("pypsrp not installed. Run: pip install pypsrp")

        return WSMan(
            creds["host"],
            port=creds["port"],
            ssl=creds["ssl"],
            username=creds["user"],
            password=creds["password"],
            auth=creds["auth"],
            cert_validation=creds["cert_valid"],
            encryption="auto",
            **self._timeouts(timeout),
        )

    def _build_client(self, creds: Dict[str, Any], timeout: int):
        try:
            from pypsrp.client import Client
        except ImportError:
            raise RuntimeError("pypsrp not installed. Run: pip install pypsrp")

        return Client(
            creds["host"],
            port=creds["port"],
            ssl=creds["ssl"],
            username=creds["user"],
            password=creds["password"],
            auth=creds["auth"],
            cert_validation=creds["cert_valid"],
            encryption="auto",
            **self._timeouts(timeout),
        )

    # ── Sync executors (run_in_executor) ───────────────────────────────────

    def _run_ps_sync(
        self,
        creds: Dict[str, Any],
        scripts: List[str],
        timeout: int,
        stop_on_error: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Exécute N scripts PowerShell dans un seul RunspacePool (état partagé).
        Retourne un résultat par script exécuté.
        """
        from pypsrp.powershell import PowerShell, RunspacePool

        results: List[Dict[str, Any]] = []
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            with self._build_wsman(creds, timeout) as wsman:
                with RunspacePool(wsman) as pool:
                    for script in scripts:
                        try:
                            ps = PowerShell(pool)
                            ps.add_script(_PS_PREFIX + script)
                            ps.add_cmdlet("Out-String").add_parameter("stream")
                            ps.invoke()
                            stdout = "\n".join(str(o) for o in ps.output).strip()
                            stderr = "\n".join(str(e) for e in ps.streams.error).strip()
                            had_errors = bool(ps.had_errors)
                            result = {
                                "stdout":    stdout,
                                "stderr":    stderr,
                                "exit_code": 1 if had_errors else 0,
                                "success":   not had_errors,
                            }
                        except Exception as e:  # runspace cassé / timeout
                            results.append({
                                "stdout": "", "stderr": f"{type(e).__name__}: {e}",
                                "exit_code": -1, "success": False,
                            })
                            break
                        results.append(result)
                        if stop_on_error and not result["success"]:
                            break
        return results

    def _run_cmd_sync(
        self, creds: Dict[str, Any], command: str, timeout: int, encoding: str
    ) -> Dict[str, Any]:
        client = self._build_client(creds, timeout)
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", UserWarning)
                stdout, stderr, rc = client.execute_cmd(command, encoding=encoding)
            return {
                "stdout":    (stdout or "").strip(),
                "stderr":    (stderr or "").strip(),
                "exit_code": rc,
                "success":   rc == 0,
            }
        finally:
            try:
                client.wsman.close()
            except Exception:
                pass

    def _upload_sync(self, creds, local_path: str, remote_path: str, timeout: int):
        client = self._build_client(creds, timeout)
        try:
            dest = client.copy(local_path, remote_path)
            return {"success": True, "remote_path": dest}
        finally:
            try:
                client.wsman.close()
            except Exception:
                pass

    def _download_sync(self, creds, remote_path: str, local_path: str, timeout: int):
        client = self._build_client(creds, timeout)
        try:
            client.fetch(remote_path, local_path)
            return {"success": True, "local_path": local_path}
        finally:
            try:
                client.wsman.close()
            except Exception:
                pass

    def _update_last_connected(self, record):
        try:
            record.last_connected = datetime.utcnow()
            self.db.commit()
        except Exception:
            pass

    # ── Public async methods ───────────────────────────────────────────────

    async def exec_powershell(
        self, host: str, script: str, timeout: Optional[int] = None, **kwargs
    ) -> Dict[str, Any]:
        """Execute a PowerShell script on the remote Windows host via PSRP."""
        creds = await self._resolve_host(host)
        logger.info(f"PSRP PS on {creds['user']}@{creds['host']}:{creds['port']} → {script[:80]}")
        loop = asyncio.get_running_loop()
        results = await loop.run_in_executor(
            None, self._run_ps_sync, creds, [script], timeout or self.timeout, True
        )
        result = results[0]
        if result["success"]:
            self._update_last_connected(creds["record"])
        return result

    async def exec_command(
        self, host: str, cmd: str, timeout: Optional[int] = None, **kwargs
    ) -> Dict[str, Any]:
        """Alias de exec_powershell — cohérence avec ssh_server / winrm_server."""
        return await self.exec_powershell(host, cmd, timeout=timeout)

    async def exec_multi(
        self,
        host: str,
        commands: List[str],
        timeout: Optional[int] = None,
        **kwargs,
    ) -> List[Dict[str, Any]]:
        """
        Exécute plusieurs scripts dans UN runspace (variables conservées entre commandes).
        S'arrête au premier échec.
        """
        creds = await self._resolve_host(host)
        loop = asyncio.get_running_loop()
        raw = await loop.run_in_executor(
            None, self._run_ps_sync, creds, list(commands), timeout or self.timeout, True
        )
        results = [{"cmd": c, **r} for c, r in zip(commands, raw)]
        if results and all(r["success"] for r in results):
            self._update_last_connected(creds["record"])
        return results

    async def exec_cmd(
        self,
        host: str,
        cmd: str,
        args: Optional[List[str]] = None,
        timeout: Optional[int] = None,
        encoding: str = "850",
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute a cmd.exe command (non-PowerShell). `encoding` = codepage OEM de la cible (850 FR, 437 US)."""
        creds = await self._resolve_host(host)
        command = cmd
        if args:
            command = f"{cmd} {subprocess.list2cmdline([str(a) for a in args])}"
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None, self._run_cmd_sync, creds, command, timeout or self.timeout, encoding
        )

    async def upload_file(
        self, host: str, local_path: str, remote_path: str,
        timeout: Optional[int] = None, **kwargs
    ) -> Dict[str, Any]:
        creds = await self._resolve_host(host)
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None, self._upload_sync, creds, local_path, remote_path, timeout or self.timeout
        )

    async def download_file(
        self, host: str, remote_path: str, local_path: str,
        timeout: Optional[int] = None, **kwargs
    ) -> Dict[str, Any]:
        creds = await self._resolve_host(host)
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None, self._download_sync, creds, remote_path, local_path, timeout or self.timeout
        )

    # ── Services ───────────────────────────────────────────────────────────

    _SVC_PROJECTION = (
        "Select-Object Name, DisplayName, "
        "@{N='Status';E={$_.Status.ToString()}}, "
        "@{N='StartType';E={$_.StartType.ToString()}}"
    )

    async def check_service(self, host: str, service: str, **kwargs) -> Dict[str, Any]:
        """Check the status of a Windows service."""
        script = (
            f"Get-Service -Name {_ps_quote(service)} | {self._SVC_PROJECTION} "
            f"| ConvertTo-Json -Compress"
        )
        result = await self.exec_powershell(host, script)
        try:
            svc = json.loads(result["stdout"])
            result["service"] = svc
            result["is_running"] = svc.get("Status") == "Running"
        except Exception:
            result["is_running"] = False
        return result

    async def restart_service(self, host: str, service: str, **kwargs) -> Dict[str, Any]:
        """Restart a Windows service."""
        name = _ps_quote(service)
        script = (
            f"Restart-Service -Name {name} -Force; "
            f"Get-Service -Name {name} | {self._SVC_PROJECTION} | ConvertTo-Json -Compress"
        )
        return await self.exec_powershell(host, script)

    async def stop_service(self, host: str, service: str, **kwargs) -> Dict[str, Any]:
        """Stop a Windows service."""
        return await self.exec_powershell(host, f"Stop-Service -Name {_ps_quote(service)} -Force")

    async def start_service(self, host: str, service: str, **kwargs) -> Dict[str, Any]:
        """Start a Windows service."""
        return await self.exec_powershell(host, f"Start-Service -Name {_ps_quote(service)}")

    async def list_services(self, host: str, status: str = "All", **kwargs) -> Dict[str, Any]:
        """List Windows services, optionally filtered by status (Running/Stopped/Paused/All)."""
        if status not in _VALID_SERVICE_STATUS:
            raise ValueError(f"Invalid status '{status}'. Valid: {sorted(_VALID_SERVICE_STATUS)}")
        flt = f"| Where-Object {{ $_.Status -eq {_ps_quote(status)} }} " if status != "All" else ""
        script = f"Get-Service {flt}| {self._SVC_PROJECTION} | ConvertTo-Json -Compress"
        return await self.exec_powershell(host, script)

    # ── Diagnostics ────────────────────────────────────────────────────────

    async def get_event_logs(
        self,
        host: str,
        log_name: str = "System",
        level: int = 2,
        count: int = 20,
        **kwargs,
    ) -> Dict[str, Any]:
        """Retrieve Windows event log entries with Level <= `level` (1=Critical, 2=Error, 3=Warning)."""
        level = max(1, min(int(level), 5))
        count = max(1, min(int(count), 500))
        script = f"""
$events = Get-WinEvent -FilterHashtable @{{ LogName = {_ps_quote(log_name)}; Level = (1..{level}) }} -MaxEvents {count} -ErrorAction SilentlyContinue |
    Select-Object @{{N='TimeCreated';E={{$_.TimeCreated.ToString('o')}}}}, Id, LevelDisplayName, ProviderName, Message
if ($null -eq $events) {{ '[]' }} else {{ @($events) | ConvertTo-Json -Compress }}
"""
        return await self.exec_powershell(host, script)

    async def get_system_info(self, host: str, **kwargs) -> Dict[str, Any]:
        """Collect OS, memory, CPU and disk info. Persists to remote_hosts.os_info."""
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
    PSVersion      = $PSVersionTable.PSVersion.ToString()
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

    async def get_running_processes(self, host: str, top_n: int = 15, **kwargs) -> Dict[str, Any]:
        """List top N processes sorted by memory usage."""
        top_n = max(1, min(int(top_n), 200))
        script = f"""
Get-Process | Sort-Object WorkingSet64 -Descending | Select-Object -First {top_n} `
  Name, Id, @{{N='Memory_MB';E={{[math]::Round($_.WorkingSet64/1MB,1)}}}}, CPU |
ConvertTo-Json -Compress
"""
        return await self.exec_powershell(host, script)

    async def exec_cleanup(self, host: str, **kwargs) -> Dict[str, Any]:
        """Clean temp files of the connecting user and run garbage collection."""
        script = """
Remove-Item "$env:TEMP\\*" -Recurse -Force -ErrorAction SilentlyContinue
[gc]::Collect()
Write-Output 'Cleanup done'
"""
        return await self.exec_powershell(host, script)

    # ── Router ─────────────────────────────────────────────────────────────

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
            "list_services":         lambda p: self.list_services(**p),
            "get_event_logs":        lambda p: self.get_event_logs(**p),
            "get_system_info":       lambda p: self.get_system_info(**p),
            "get_running_processes": lambda p: self.get_running_processes(**p),
            "exec_cleanup":          lambda p: self.exec_cleanup(**p),
            "upload_file":           lambda p: self.upload_file(**p),
            "download_file":         lambda p: self.download_file(**p),
        }
        if method not in dispatch:
            raise ValueError(
                f"Unknown PSRP MCP method: '{method}'. Available: {list(dispatch)}"
            )
        return await dispatch[method](params)