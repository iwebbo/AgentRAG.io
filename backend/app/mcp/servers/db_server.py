"""
DB MCP Server v1
================
Connecteur SQL générique (MySQL / MariaDB / PostgreSQL / SQL Server) pour les skills.
Les requêtes SQL sont passées directement dans le .md du skill — plus besoin de
SSH + `mysql -e '...'`.

Prérequis (imports paresseux, n'installer que ce qui est utilisé) :
    pip install pymysql            # mysql, mariadb
    pip install psycopg2-binary    # postgresql
    pip install pymssql            # mssql

Instanciation depuis AgentExecutor :
    DBMCPServer(db=db, user_id=str(agent_record.user_id), timeout=30)

Credentials résolus depuis remote_hosts (protocol == "db") par (user_id, name ou host) :
    host, port, username, encrypted_password        → colonnes existantes
    db_type     (str)  : mysql | mariadb | postgresql | mssql
                         (à défaut : premier tag reconnu, ex. tags=["db", "mysql"])
    db_name     (str)  : base par défaut (optionnel)
    db_options  (JSON) : kwargs driver additionnels, ex. {"ssl": {"ca": "/path/ca.pem"}} (optionnel)
    → db_type / db_name / db_options sont lues via getattr : colonnes nullable à ajouter au modèle
      RemoteHost + migration (cf. 001_remote_hosts).

Modèle de sécurité (défense en profondeur — la vraie barrière reste les GRANTs du compte DB) :
- query()      : lecture seule. Session read-only (MySQL/MariaDB/PostgreSQL) + analyse SQL
                 (1 seule instruction, pas de INTO/UPDATE/DELETE/DDL/CALL...).
- execute() / exec_multi(allow_write=True) : écriture. Transaction unique, rollback sur erreur.
                 DROP / TRUNCATE / DELETE / ALTER / GRANT / REVOKE / UPDATE sans WHERE
                 exigent confirm=True (à n'envoyer qu'après confirmation explicite de l'utilisateur).
- Toujours refusés : INTO OUTFILE/DUMPFILE, LOAD DATA, LOAD_FILE, COPY ... PROGRAM,
                 xp_cmdshell, OPENROWSET, BULK INSERT, pg_read_file, lo_import/export...
- Paramètres : utiliser `params` (placeholders %s) plutôt que de concaténer des valeurs.
                 Avec `params`, un `%` littéral doit s'écrire `%%`.
"""
import asyncio
import json
import logging
import re
import time
from datetime import date, datetime, timedelta
from datetime import time as dtime
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple, Union
from uuid import UUID

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# ── Constantes ────────────────────────────────────────────────────────────────

_DB_ALIASES = {
    "mysql": "mysql", "mariadb": "mariadb",
    "postgresql": "postgresql", "postgres": "postgresql", "pg": "postgresql",
    "mssql": "mssql", "sqlserver": "mssql", "sql-server": "mssql",
}
_DEFAULT_PORTS = {"mysql": 3306, "mariadb": 3306, "postgresql": 5432, "mssql": 1433}

_DEFAULT_MAX_ROWS = 200
_HARD_MAX_ROWS = 5000
_MAX_CELL_CHARS = 4000
_DB_NAME_RE = re.compile(r"^[A-Za-z0-9_$.\-]{1,128}$")
_RESERVED_OPTION_KEYS = {"host", "port", "user", "password", "database", "dbname", "server"}

_READ_FIRST = {"SHOW", "DESCRIBE", "DESC", "EXPLAIN"}
_SCAN_FIRST = {"SELECT", "WITH", "VALUES", "TABLE"}          # lecture seulement si aucun mot d'écriture
_WRITE_RE = re.compile(
    r"\b(INTO|UPDATE|DELETE|MERGE|DROP|ALTER|TRUNCATE|CREATE|GRANT|REVOKE|CALL|EXEC|EXECUTE)\b", re.I
)
_DESTRUCTIVE_RE = re.compile(r"\b(DROP|TRUNCATE|DELETE|ALTER|GRANT|REVOKE)\b", re.I)
_BLOCKED_RE = re.compile(
    r"\b(OUTFILE|DUMPFILE|LOAD_FILE|LOAD\s+DATA|XP_CMDSHELL|SP_OACREATE|OPENROWSET|OPENDATASOURCE|"
    r"BULK\s+INSERT|PG_READ_FILE|PG_READ_BINARY_FILE|PG_LS_DIR|LO_IMPORT|LO_EXPORT)\b"
    r"|\bCOPY\b[^;]*\bPROGRAM\b",
    re.I,
)


# ── Analyse SQL ───────────────────────────────────────────────────────────────

def _token_re(dialect: str) -> "re.Pattern":
    """Regex des segments à neutraliser (chaînes, identifiants quotés, commentaires) selon le dialecte."""
    if dialect in ("mysql", "mariadb"):
        parts = [
            r"'(?:[^'\\]|\\.|'')*'",
            r'"(?:[^"\\]|\\.|"")*"',
            r"`[^`]*`",
            r"--(?=\s|$)[^\n]*",
            r"\#[^\n]*",
            r"/\*(?!\!).*?\*/",          # /*! ... */ (conditional, exécuté par MySQL) n'est PAS un commentaire
        ]
    elif dialect == "postgresql":
        parts = [
            r"[eE]'(?:[^'\\]|\\.|'')*'",
            r"'(?:[^']|'')*'",
            r'"(?:[^"]|"")*"',
            r"\$(\w*)\$.*?\$\1\$",
            r"--[^\n]*",
            r"/\*.*?\*/",
        ]
    else:  # mssql
        parts = [
            r"'(?:[^']|'')*'",
            r'"(?:[^"]|"")*"',
            r"\[[^\]]*\]",
            r"--[^\n]*",
            r"/\*.*?\*/",
        ]
    return re.compile("|".join(parts), re.S)


_TOKEN_RES = {d: _token_re(d) for d in ("mysql", "mariadb", "postgresql", "mssql")}


def _analyze(sql: str, dialect: str) -> Dict[str, Any]:
    """
    Valide et classe UNE instruction SQL.
    Retourne {"sql", "keyword", "kind": "read"|"write", "destructive": bool}.
    Lève ValueError si non analysable / interdite.
    """
    if not isinstance(sql, str) or not sql.strip():
        raise ValueError("Empty SQL statement")

    cleaned = re.sub(r"\\[gG]\s*$", "", sql.strip())             # suffixe client mysql \G
    stripped = _TOKEN_RES[dialect].sub(" ", cleaned)
    if re.search(r"['\"`]", stripped):
        raise ValueError("SQL could not be parsed safely (unbalanced quotes)")

    statements = [s for s in stripped.split(";") if s.strip()]
    if len(statements) != 1:
        raise ValueError("Exactly one SQL statement per call is allowed")
    body = statements[0]

    if _BLOCKED_RE.search(body):
        raise ValueError("Statement uses a forbidden feature (file access / OS command / bulk import)")

    m = re.match(r"[\s(]*([A-Za-z]+)", body)
    if not m:
        raise ValueError("Unable to determine the SQL statement type")
    keyword = m.group(1).upper()

    if keyword in _READ_FIRST:
        kind = "read"
    elif keyword in _SCAN_FIRST:
        kind = "write" if _WRITE_RE.search(body) else "read"
    else:
        kind = "write"

    destructive = False
    if kind == "write":
        destructive = bool(_DESTRUCTIVE_RE.search(body)) or (
            keyword == "UPDATE" and not re.search(r"\bWHERE\b", body, re.I)
        )

    return {
        "sql":         re.sub(r"[;\s]+$", "", cleaned),
        "keyword":     keyword,
        "kind":        kind,
        "destructive": destructive,
    }


# ── Sérialisation ─────────────────────────────────────────────────────────────

def _jsonable(v: Any) -> Any:
    if v is None or isinstance(v, (bool, int, float)):
        return v
    if isinstance(v, str):
        return v if len(v) <= _MAX_CELL_CHARS else v[:_MAX_CELL_CHARS] + "…[truncated]"
    if isinstance(v, (datetime, date, dtime)):
        return v.isoformat()
    if isinstance(v, timedelta):
        return str(v)
    if isinstance(v, Decimal):
        return int(v) if v == v.to_integral_value() else str(v)
    if isinstance(v, UUID):
        return str(v)
    if isinstance(v, (bytes, bytearray, memoryview)):
        b = bytes(v)
        try:
            return _jsonable(b.decode("utf-8"))
        except UnicodeDecodeError:
            return "0x" + b[:64].hex() + ("…" if len(b) > 64 else "")
    if isinstance(v, dict):
        return {str(k): _jsonable(x) for k, x in v.items()}
    if isinstance(v, (list, tuple, set)):
        return [_jsonable(x) for x in v]
    return _jsonable(str(v))


_STDOUT_CELL_MAX = 120   # largeur max d'une cellule dans le rendu texte


def _cell_text(v: Any) -> str:
    if v is None:
        return "NULL"
    s = v if isinstance(v, str) else json.dumps(v, ensure_ascii=False, default=str)
    s = s.replace("\r", " ").replace("\n", " ").replace("|", "\\|")
    return s if len(s) <= _STDOUT_CELL_MAX else s[:_STDOUT_CELL_MAX - 1] + "…"


def _render_stdout(columns: List[str], rows: List[list], truncated: bool) -> str:
    """Rendu texte (table Markdown) du résultat — c'est ce que lisent SkillAgent / le LLM
    (même contrat que ssh/winrm/psrp : champ `stdout`)."""
    if not columns:
        return ""
    lines = [
        "| " + " | ".join(_cell_text(c) for c in columns) + " |",
        "|" + "|".join(" --- " for _ in columns) + "|",
    ]
    for r in rows:
        lines.append("| " + " | ".join(_cell_text(v) for v in r) + " |")
    lines.append(f"({len(rows)} row{'s' if len(rows) != 1 else ''}{', truncated' if truncated else ''})")
    return "\n".join(lines)


def _failure(message: str, **extra) -> Dict[str, Any]:
    return {
        "success": False, "error": message, "stderr": message, "exit_code": 1, "stdout": "",
        "columns": [], "rows": [], "row_count": 0, "truncated": False, **extra,
    }


Statement = Union[str, Dict[str, Any]]   # "SELECT 1" ou {"sql": "...", "params": [...]}


class DBMCPServer:

    def __init__(
        self,
        db: Session,
        user_id: str,
        timeout: int = 30,
        max_rows: int = _DEFAULT_MAX_ROWS,
        **kwargs,
    ):
        self.db = db
        self.user_id = user_id
        self.timeout = timeout
        self.max_rows = max_rows
        logger.info(f"DB MCP initialized for user={user_id}")

    # ── Credential resolution ──────────────────────────────────────────────

    @staticmethod
    def _detect_db_type(record) -> str:
        candidates = [getattr(record, "db_type", None)] + list(record.tags or [])
        for c in candidates:
            if c:
                t = _DB_ALIASES.get(str(c).strip().lower())
                if t:
                    return t
        raise ValueError(
            f"DB host '{record.name}': db_type not set. Set db_type or add a tag in "
            f"{sorted(set(_DB_ALIASES.values()))}."
        )

    async def _resolve_host(self, host_name: str, database: Optional[str] = None) -> Dict[str, Any]:
        from sqlalchemy import or_
        from app.models.remote_host import RemoteHost
        from app.utils.security import decrypt_api_key

        record = self.db.query(RemoteHost).filter(
            RemoteHost.user_id == UUID(self.user_id),
            RemoteHost.is_active == True,
            RemoteHost.protocol == "db",
            or_(
                RemoteHost.name == host_name,
                RemoteHost.host == host_name,
            ),
        ).first()

        if not record:
            raise ValueError(
                f"DB host '{host_name}' not found or inactive. "
                f"Register it first: POST /api/hosts (protocol=db)"
            )

        db_type = self._detect_db_type(record)

        if database is not None and not _DB_NAME_RE.match(database):
            raise ValueError(f"Invalid database name: {database!r}")

        options = getattr(record, "db_options", None) or {}
        if not isinstance(options, dict):
            options = {}
        options = {k: v for k, v in options.items() if k not in _RESERVED_OPTION_KEYS}

        return {
            "db_type":  db_type,
            "host":     record.host,
            "port":     record.port or _DEFAULT_PORTS[db_type],
            "user":     record.username,
            "password": decrypt_api_key(record.encrypted_password) if record.encrypted_password else "",
            "database": database or getattr(record, "db_name", None) or None,
            "options":  options,
            "record":   record,
        }

    # ── Connection ─────────────────────────────────────────────────────────

    def _connect(self, creds: Dict[str, Any], timeout: int, read_only: bool):
        t = creds["db_type"]
        connect_timeout = min(timeout, 30)

        if t in ("mysql", "mariadb"):
            try:
                import pymysql
            except ImportError:
                raise RuntimeError("pymysql not installed. Run: pip install pymysql")
            conn = pymysql.connect(
                host=creds["host"], port=creds["port"],
                user=creds["user"], password=creds["password"],
                database=creds["database"],
                connect_timeout=connect_timeout, read_timeout=timeout, write_timeout=timeout,
                charset="utf8mb4", autocommit=False,
                **creds["options"],
            )
            with conn.cursor() as c:
                if read_only:
                    c.execute("SET SESSION TRANSACTION READ ONLY")
                try:                                    # MySQL (ms)
                    c.execute(f"SET SESSION max_execution_time={int(timeout) * 1000}")
                except Exception:
                    try:                                # MariaDB (s)
                        c.execute(f"SET SESSION max_statement_time={int(timeout)}")
                    except Exception:
                        pass
            return conn

        if t == "postgresql":
            try:
                import psycopg2
            except ImportError:
                raise RuntimeError("psycopg2 not installed. Run: pip install psycopg2-binary")
            conn = psycopg2.connect(
                host=creds["host"], port=creds["port"],
                user=creds["user"], password=creds["password"],
                dbname=creds["database"] or "postgres",
                connect_timeout=connect_timeout,
                options=f"-c statement_timeout={int(timeout) * 1000}",
                **creds["options"],
            )
            conn.set_session(readonly=read_only, autocommit=False)
            return conn

        if t == "mssql":
            try:
                import pymssql
            except ImportError:
                raise RuntimeError("pymssql not installed. Run: pip install pymssql")
            return pymssql.connect(
                server=creds["host"], port=str(creds["port"]),
                user=creds["user"], password=creds["password"],
                database=creds["database"] or "",
                login_timeout=connect_timeout, timeout=timeout,
                autocommit=False,
                **creds["options"],
            )

        raise ValueError(f"Unsupported db_type: {t}")

    def _run_sync(
        self,
        creds: Dict[str, Any],
        items: List[Tuple[str, Optional[list]]],
        timeout: int,
        max_rows: int,
        read_only: bool,
    ) -> List[Dict[str, Any]]:
        """Exécute les instructions dans UNE connexion / transaction. Rollback si échec ou read-only."""
        conn = self._connect(creds, timeout, read_only)
        results: List[Dict[str, Any]] = []
        ok = True
        try:
            cur = conn.cursor()
            for sql, params in items:
                t0 = time.monotonic()
                try:
                    if params:
                        cur.execute(sql, params)
                    else:
                        cur.execute(sql)
                    res: Dict[str, Any] = {"success": True, "exit_code": 0, "stderr": ""}
                    if cur.description:
                        columns = [d[0] for d in cur.description]
                        fetched = cur.fetchmany(max_rows + 1)
                        rows = [[_jsonable(v) for v in r] for r in fetched[:max_rows]]
                        truncated = len(fetched) > max_rows
                        res.update(
                            columns=columns, rows=rows, row_count=len(rows),
                            truncated=truncated,
                            stdout=_render_stdout(columns, rows, truncated),
                        )
                    else:
                        affected = max(cur.rowcount if cur.rowcount is not None else 0, 0)
                        res.update(
                            columns=[], rows=[], row_count=0, truncated=False,
                            rows_affected=affected,
                            stdout=f"OK — {affected} row(s) affected",
                        )
                except Exception as e:
                    ok = False
                    res = _failure(f"{type(e).__name__}: {e}")
                res["duration_ms"] = int((time.monotonic() - t0) * 1000)
                results.append(res)
                if not ok:
                    break
            try:
                if ok and not read_only:
                    conn.commit()
                else:
                    conn.rollback()
            except Exception as e:
                if ok:
                    results.append(_failure(f"commit failed: {type(e).__name__}: {e}"))
        finally:
            try:
                conn.close()
            except Exception:
                pass
        return results

    async def _run(
        self,
        creds: Dict[str, Any],
        items: List[Tuple[str, Optional[list]]],
        timeout: Optional[int],
        max_rows: Optional[int],
        read_only: bool,
    ) -> List[Dict[str, Any]]:
        rows_cap = max(1, min(int(max_rows or self.max_rows), _HARD_MAX_ROWS))
        loop = asyncio.get_running_loop()
        results = await loop.run_in_executor(
            None, self._run_sync, creds, items, int(timeout or self.timeout), rows_cap, read_only
        )
        if results and all(r["success"] for r in results):
            self._update_last_connected(creds["record"])
        for r in results:
            r["db_type"] = creds["db_type"]
        return results

    def _update_last_connected(self, record):
        try:
            record.last_connected = datetime.utcnow()
            self.db.commit()
        except Exception:
            pass

    @staticmethod
    def _normalize_items(statements: List[Statement], dialect: str) -> List[Dict[str, Any]]:
        analyzed = []
        for s in statements:
            if isinstance(s, str):
                sql, params = s, None
            elif isinstance(s, dict) and "sql" in s:
                sql, params = s["sql"], s.get("params")
            else:
                raise ValueError("Each statement must be a string or {'sql': str, 'params': list}")
            if params is not None and not isinstance(params, (list, tuple)):
                raise ValueError("'params' must be a list")
            a = _analyze(sql, dialect)
            a["params"] = list(params) if params else None
            analyzed.append(a)
        return analyzed

    # ── Public async methods ───────────────────────────────────────────────

    async def query(
        self,
        host: str,
        sql: str,
        params: Optional[list] = None,
        database: Optional[str] = None,
        max_rows: Optional[int] = None,
        timeout: Optional[int] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Exécute UNE requête en lecture seule (SELECT / SHOW / DESCRIBE / EXPLAIN / WITH...).
        Retourne {"success", "columns", "rows", "row_count", "truncated", "duration_ms", ...}.
        """
        creds = await self._resolve_host(host, database)
        try:
            a = _analyze(sql, creds["db_type"])
        except ValueError as e:
            return _failure(str(e), blocked=True)
        if a["kind"] != "read":
            return _failure(
                f"'{a['keyword']}' is not a read-only statement. Use `execute` for writes.", blocked=True
            )
        logger.info(f"DB query on {creds['user']}@{creds['host']}:{creds['port']} ({creds['db_type']}) → {a['sql'][:80]}")
        results = await self._run(
            creds, [(a["sql"], list(params) if params else None)], timeout, max_rows, read_only=True
        )
        return results[0]

    async def exec_command(
        self, host: str, cmd: str, timeout: Optional[int] = None, **kwargs
    ) -> Dict[str, Any]:
        """Alias de `query` — cohérence avec ssh_server / winrm_server / psrp_server (lecture seule)."""
        return await self.query(host, cmd, timeout=timeout, **kwargs)

    async def execute(
        self,
        host: str,
        sql: str,
        params: Optional[list] = None,
        database: Optional[str] = None,
        confirm: bool = False,
        timeout: Optional[int] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Exécute UNE instruction d'écriture (INSERT / UPDATE / DELETE / DDL / KILL ...) en transaction.
        DROP / TRUNCATE / DELETE / ALTER / GRANT / REVOKE / UPDATE sans WHERE → confirm=True requis.
        """
        creds = await self._resolve_host(host, database)
        try:
            a = _analyze(sql, creds["db_type"])
        except ValueError as e:
            return _failure(str(e), blocked=True)
        if a["destructive"] and not confirm:
            return _failure(
                f"'{a['keyword']}' is destructive. Ask the user for explicit confirmation, "
                f"then retry with confirm=true.",
                blocked=True, requires_confirmation=True,
            )
        logger.warning(
            f"DB execute on {creds['user']}@{creds['host']}:{creds['port']} "
            f"({creds['db_type']}/{creds['database']}) → {a['sql'][:80]}"
        )
        results = await self._run(
            creds, [(a["sql"], list(params) if params else None)],
            timeout, None, read_only=False,
        )
        return results[0]

    async def exec_multi(
        self,
        host: str,
        commands: List[Statement],
        database: Optional[str] = None,
        allow_write: bool = False,
        confirm: bool = False,
        timeout: Optional[int] = None,
        max_rows: Optional[int] = None,
        **kwargs,
    ) -> List[Dict[str, Any]]:
        """
        Exécute plusieurs instructions dans UNE connexion et UNE transaction.
        - allow_write=False (défaut) : toutes doivent être en lecture, session read-only.
        - Écritures : allow_write=True ; destructives → confirm=True.
        - Stop + rollback complet au premier échec.
        """
        creds = await self._resolve_host(host, database)
        try:
            analyzed = self._normalize_items(commands, creds["db_type"])
        except ValueError as e:
            return [_failure(str(e), blocked=True)]

        has_write = any(a["kind"] == "write" for a in analyzed)
        if has_write and not allow_write:
            return [_failure("Batch contains write statements. Retry with allow_write=true.", blocked=True)]
        if any(a["destructive"] for a in analyzed) and not confirm:
            return [_failure(
                "Batch contains destructive statements. Ask the user for explicit confirmation, "
                "then retry with confirm=true.",
                blocked=True, requires_confirmation=True,
            )]

        results = await self._run(
            creds, [(a["sql"], a["params"]) for a in analyzed], timeout, max_rows, read_only=not has_write
        )
        return [{"sql": a["sql"], **r} for a, r in zip(analyzed, results)] + (
            results[len(analyzed):]   # ex. erreur de commit
        )

    # ── Introspection ──────────────────────────────────────────────────────

    async def list_databases(self, host: str, **kwargs) -> Dict[str, Any]:
        """List databases / catalogs visible to the account."""
        creds = await self._resolve_host(host)
        sql = {
            "mysql":      "SHOW DATABASES",
            "mariadb":    "SHOW DATABASES",
            "postgresql": "SELECT datname AS database_name FROM pg_database WHERE NOT datistemplate ORDER BY 1",
            "mssql":      "SELECT name AS database_name FROM sys.databases ORDER BY 1",
        }[creds["db_type"]]
        return (await self._run(creds, [(sql, None)], None, None, read_only=True))[0]

    async def list_tables(
        self,
        host: str,
        database: Optional[str] = None,
        schema: Optional[str] = None,
        max_rows: Optional[int] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """List tables/views. `schema` (MySQL: = database) optional; system schemas excluded otherwise."""
        creds = await self._resolve_host(host, database)
        system = {
            "mysql":      "('mysql','information_schema','performance_schema','sys')",
            "mariadb":    "('mysql','information_schema','performance_schema','sys')",
            "postgresql": "('pg_catalog','information_schema')",
            "mssql":      "('sys','INFORMATION_SCHEMA')",
        }[creds["db_type"]]
        sql = (
            "SELECT table_schema AS table_schema, table_name AS table_name, table_type AS table_type "
            "FROM information_schema.tables "
        )
        params: Optional[list] = None
        if schema:
            sql += "WHERE table_schema = %s "
            params = [schema]
        else:
            sql += f"WHERE table_schema NOT IN {system} "
        sql += "ORDER BY 1, 2"
        return (await self._run(creds, [(sql, params)], None, max_rows, read_only=True))[0]

    async def describe_table(
        self,
        host: str,
        table: str,
        database: Optional[str] = None,
        schema: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """Columns of a table (name, type, nullable, default, max length)."""
        creds = await self._resolve_host(host, database)
        default_schema = {
            "mysql": "DATABASE()", "mariadb": "DATABASE()",
            "postgresql": "current_schema()", "mssql": "SCHEMA_NAME()",
        }[creds["db_type"]]
        sql = (
            "SELECT column_name AS column_name, data_type AS data_type, is_nullable AS is_nullable, "
            "column_default AS column_default, character_maximum_length AS max_length "
            "FROM information_schema.columns WHERE table_name = %s "
        )
        params = [table]
        if schema:
            sql += "AND table_schema = %s "
            params.append(schema)
        else:
            sql += f"AND table_schema = {default_schema} "
        sql += "ORDER BY ordinal_position"
        return (await self._run(creds, [(sql, params)], None, None, read_only=True))[0]

    async def get_system_info(self, host: str, **kwargs) -> Dict[str, Any]:
        """Server version / current db / limits. Persists to remote_hosts.os_info."""
        creds = await self._resolve_host(host)
        sql = {
            "mysql": (
                "SELECT VERSION() AS version, @@version_comment AS version_comment, DATABASE() AS current_db, "
                "@@hostname AS hostname, @@max_connections AS max_connections"
            ),
            "postgresql": (
                "SELECT version() AS version, current_database() AS current_db, current_user AS current_user, "
                "current_setting('max_connections') AS max_connections, "
                "pg_postmaster_start_time()::text AS started_at"
            ),
            "mssql": (
                "SELECT @@VERSION AS version, DB_NAME() AS current_db, @@SERVERNAME AS hostname, "
                "SUSER_SNAME() AS login_name"
            ),
        }["mysql" if creds["db_type"] in ("mysql", "mariadb") else creds["db_type"]]
        result = (await self._run(creds, [(sql, None)], None, 1, read_only=True))[0]
        if result["success"] and result["rows"]:
            info = dict(zip(result["columns"], result["rows"][0]))
            info["db_type"] = creds["db_type"]
            result["info"] = info
            try:
                creds["record"].os_info = info
                self.db.commit()
            except Exception:
                try:
                    self.db.rollback()
                except Exception:
                    pass
        return result

    async def test_connection(self, host: str, database: Optional[str] = None, **kwargs) -> Dict[str, Any]:
        """Connectivity check (used by POST /api/hosts/{id}/test). stdout == 'agentrag_ok' on success."""
        creds = await self._resolve_host(host, database)
        result = (await self._run(creds, [("SELECT 'agentrag_ok' AS ok", None)], 10, 1, read_only=True))[0]
        ok = bool(result["success"] and result["rows"] and result["rows"][0][0] == "agentrag_ok")
        result["success"] = ok
        result["stdout"] = "agentrag_ok" if ok else ""
        return result

    # ── Router ─────────────────────────────────────────────────────────────

    async def call(self, method: str, params: Dict[str, Any]) -> Any:
        dispatch = {
            "query":           lambda p: self.query(**p),
            "execute":         lambda p: self.execute(**p),
            "exec_command":    lambda p: self.exec_command(**p),
            "exec_multi":      lambda p: self.exec_multi(**p),
            "list_databases":  lambda p: self.list_databases(**p),
            "list_tables":     lambda p: self.list_tables(**p),
            "describe_table":  lambda p: self.describe_table(**p),
            "get_system_info": lambda p: self.get_system_info(**p),
            "test_connection": lambda p: self.test_connection(**p),
        }
        if method not in dispatch:
            raise ValueError(f"Unknown DB MCP method: '{method}'. Available: {list(dispatch)}")
        return await dispatch[method](params)