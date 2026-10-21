"""
CodeBlockCheck — validation mécanique du code contenu dans une réponse.

Séquence appliquée à chaque bloc ``` fermé :

  1. bloc non refermé             → ERROR   (réponse tronquée)
  2. python  : ast.parse          → ERROR   si la syntaxe est invalide
             : ruff (check-only)  → ERROR   bugs certains (E9, F63, F7, F823)
                                    WARNING noms indéfinis, redéfinitions, pièges B*, appels dangereux S*
  3. json    : json.loads         → WARNING (INFO si le bloc est visiblement illustratif : `...`, commentaires)
  4. yaml    : yaml.safe_load_all → WARNING (ignoré pour les templates Helm/Jinja `{{ }}` / `{% %}`)
  5. tous    : code « paresseux » → WARNING (« # ... reste du code », « votre code ici », « TODO: implement »)

Rien n'est exécuté : ni le code de la réponse, ni ses imports. `ruff` est lancé en
`--isolated --no-fix` sur stdin : il ne modifie rien et ne lit aucune config du projet.

Faux positifs maîtrisés
-----------------------
- Extraits indentés (méthodes) : dédentés avant analyse.
- Transcriptions shell / REPL (`$ `, `>>> `) : ignorées.
- L'application tourne sur Python 3.11 mais le code généré peut cibler une syntaxe plus
  récente : si `ast` échoue mais que ruff parse sans erreur, c'est signalé en INFO seulement.
- Un nom indéfini (F821) est un WARNING, pas une erreur : un extrait n'a pas ses imports.
"""
from __future__ import annotations

import json
import logging
import re
import shutil
import subprocess
import sys
import tempfile
import textwrap
from typing import Any, Dict, List, Optional, Protocol, Sequence

from .base import (
    CheckResult,
    FencedBlock,
    Finding,
    Severity,
    VerificationContext,
    extract_fenced_blocks,
    strip_think,
)

try:  # PyYAML est déjà une dépendance du backend (skill_registry) mais on reste tolérant
    import yaml  # type: ignore
except Exception:  # pragma: no cover
    yaml = None  # type: ignore

logger = logging.getLogger(__name__)

PYTHON_LANGS = {"python", "py", "python3", "py3"}
JSON_LANGS = {"json"}
YAML_LANGS = {"yaml", "yml"}
NON_CODE_LANGS = {"", "text", "txt", "md", "markdown", "csv", "diff", "patch", "console", "output", "log",
                  "json", "jsonc", "yaml", "yml", "toml", "ini", "mermaid", "plaintext"}

MAX_BLOCKS = 20
MAX_BLOCK_CHARS = 100_000

RUFF_SELECT = "E9,F63,F7,F82,F811,B006,B023,S102,S307,S506,S602,S605"
_RUFF_ERROR_PREFIXES = ("E9", "F63", "F7")
_RUFF_ERROR_CODES = {"F823"}


# ruff <= 0.3 reports syntax errors as E999; newer versions report "invalid-syntax" (or a null code
# with a "SyntaxError: ..." message). Accept all of them so the behaviour does not depend on the
# ruff version installed alongside the application.
_RUFF_SYNTAX_CODES = {"E999", "invalid-syntax", "syntax-error"}


def is_syntax_violation(violation: Dict[str, Any]) -> bool:
    code = str(violation.get("code") or violation.get("name") or "")
    if code.startswith("E9") or code in _RUFF_SYNTAX_CODES:
        return True
    return not code and str(violation.get("message") or "").lower().startswith("syntaxerror")


def ruff_severity(code: str) -> Severity:
    if code in _RUFF_ERROR_CODES or code in _RUFF_SYNTAX_CODES or code.startswith(_RUFF_ERROR_PREFIXES):
        return Severity.ERROR
    return Severity.WARNING


class LintRunner(Protocol):
    """Contrat minimal pour brancher un autre linter / un faux en test."""

    def check(self, code: str) -> Optional[List[Dict[str, Any]]]:
        """Retourne la liste des violations, ou None si le linter est indisponible."""
        ...


class RuffRunner:
    """`ruff check --no-fix` sur stdin. Indisponible (None) si ruff n'est pas installé."""

    def __init__(self, select: str = RUFF_SELECT, timeout: float = 15.0):
        self.select = select
        self.timeout = timeout
        self._command: Optional[List[str]] = None
        self._resolved = False

    def _resolve(self) -> Optional[List[str]]:
        if self._resolved:
            return self._command
        self._resolved = True
        candidates: List[List[str]] = []
        found = shutil.which("ruff")
        if found:
            candidates.append([found])
        candidates.append([sys.executable, "-m", "ruff"])
        for command in candidates:
            try:
                proc = subprocess.run(command + ["--version"], capture_output=True, text=True, timeout=10)
                if proc.returncode == 0:
                    self._command = command
                    break
            except Exception:
                continue
        if self._command is None:
            logger.info("ruff not available: python lint step of CodeBlockCheck is disabled")
        return self._command

    @property
    def available(self) -> bool:
        return self._resolve() is not None

    def check(self, code: str) -> Optional[List[Dict[str, Any]]]:
        command = self._resolve()
        if command is None:
            return None
        args = command + [
            "check", "--isolated", "--no-fix", "--select", self.select,
            "--output-format", "json", "--stdin-filename", "snippet.py", "-",
        ]
        try:
            proc = subprocess.run(
                args, input=code, capture_output=True, text=True,
                timeout=self.timeout, cwd=tempfile.gettempdir(),
            )
        except Exception as exc:
            logger.warning("ruff invocation failed: %s", exc)
            return None
        if proc.returncode not in (0, 1):
            logger.warning("ruff exited with %s: %s", proc.returncode, (proc.stderr or "")[:200])
            return None
        try:
            parsed = json.loads(proc.stdout or "[]")
        except ValueError:
            return None
        return parsed if isinstance(parsed, list) else None


# ───────────────────────────────── code paresseux ─────────────────────────────────

_LAZY_PATTERNS = [
    re.compile(r"(?:#|//|/\*|--)\s*\.\.\.\s*\(?\s*(?:rest|remaining|existing|other|same|unchanged|"
               r"le reste|la suite|inchang)", re.IGNORECASE),
    re.compile(r"(?:#|//)\s*(?:your|add your|insert|put your|votre|ton|mets ton)\s+"
               r"(?:code|logic|implementation|logique|impl)", re.IGNORECASE),
    re.compile(r"(?:#|//)\s*TODO:?\s*(?:implement|impl[ée]menter|add|ajouter|fill)", re.IGNORECASE),
    re.compile(r"^\s*pass\s*#.*(?:implement|todo|logic|logique)", re.IGNORECASE | re.MULTILINE),
]


def _prepare_python(code: str) -> Optional[str]:
    """Dédente et écarte ce qui n'est pas du Python exécutable (shell, REPL)."""
    code = textwrap.dedent(code).strip("\n")
    if not code.strip():
        return None
    lines = [line for line in code.split("\n") if line.strip()]
    first = lines[0].lstrip()
    if first.startswith(("$ ", "# $", ">>> ", "@@ ")):
        return None
    if any(line.lstrip().startswith(">>> ") for line in lines):
        return None
    return code


class CodeBlockCheck:
    name = "code"
    blocking = True  # ruff = subprocess → le pipeline exécute ce check dans un thread

    def __init__(self, lint: Optional[LintRunner] = None, use_ruff: bool = True):
        if lint is not None:
            self.lint: Optional[LintRunner] = lint
        else:
            self.lint = RuffRunner() if use_ruff else None

    def run(self, response: str, ctx: VerificationContext, prior: Sequence[CheckResult]) -> CheckResult:
        blocks = extract_fenced_blocks(strip_think(response))
        if not blocks:
            return CheckResult.skipped(self.name, "no code block")

        findings: List[Finding] = []
        analysed = 0
        for block in blocks[:MAX_BLOCKS]:
            if not block.closed:
                findings.append(Finding(
                    "code.unclosed_fence",
                    Severity.ERROR,
                    f"The code block opened at line {block.start_line} is never closed: "
                    "the answer was probably truncated.",
                    {"lang": block.lang, "line": block.start_line},
                ))
                continue
            if len(block.code) > MAX_BLOCK_CHARS:
                continue
            analysed += 1
            if block.lang in PYTHON_LANGS:
                findings.extend(self._check_python(block))
            elif block.lang in JSON_LANGS:
                findings.extend(self._check_json(block))
            elif block.lang in YAML_LANGS:
                findings.extend(self._check_yaml(block))
            if block.lang not in NON_CODE_LANGS:
                findings.extend(self._check_laziness(block))

        note = f"{analysed} block(s) analysed"
        return CheckResult.from_findings(self.name, findings, note=note)

    # ── python ────────────────────────────────────────────────────────────────────

    def _check_python(self, block: FencedBlock) -> List[Finding]:
        code = _prepare_python(block.code)
        if code is None:
            return []

        import ast

        try:
            ast.parse(code, filename="<llm-answer>")
        except SyntaxError as exc:
            return [self._syntax_finding(block, code, exc)]
        except (ValueError, RecursionError) as exc:  # null bytes, nesting trop profond
            return [Finding("code.python_unparsable", Severity.WARNING,
                            f"Python block at line {block.start_line} could not be analysed: {exc}")]

        findings: List[Finding] = []
        if self.lint is not None:
            violations = self.lint.check(code)
            for violation in (violations or [])[:10]:
                rule = str(violation.get("code") or violation.get("name") or "")
                if not rule and is_syntax_violation(violation):
                    rule = "invalid-syntax"
                if not rule:
                    continue
                row = ((violation.get("location") or {}).get("row")) or 0
                findings.append(Finding(
                    f"code.ruff.{rule}",
                    ruff_severity(rule),
                    f"Python block at line {block.start_line}, line {row}: {rule} {violation.get('message', '')}".strip(),
                    {"rule": rule, "line": row, "block_line": block.start_line},
                ))
        return findings

    def _syntax_finding(self, block: FencedBlock, code: str, exc: SyntaxError) -> Finding:
        evidence = {
            "lang": "python",
            "block_line": block.start_line,
            "line": exc.lineno,
            "text": (exc.text or "").strip(),
            "error": exc.msg,
        }
        # Le runtime est en 3.11 : un code visant une syntaxe plus récente échoue ici.
        # Si ruff (qui connaît la syntaxe récente) ne voit aucune erreur de syntaxe → INFO.
        if self.lint is not None:
            violations = self.lint.check(code)
            if violations is not None and not any(is_syntax_violation(v) for v in violations):
                return Finding(
                    "code.python_newer_syntax",
                    Severity.INFO,
                    f"Python block at line {block.start_line} uses syntax the {sys.version_info.major}."
                    f"{sys.version_info.minor} runtime cannot parse ({exc.msg}), but ruff accepts it.",
                    evidence,
                )
        return Finding(
            "code.python_syntax",
            Severity.ERROR,
            f"Python block at line {block.start_line} has a syntax error at line {exc.lineno}: {exc.msg}",
            evidence,
        )

    # ── json / yaml ───────────────────────────────────────────────────────────────

    def _check_json(self, block: FencedBlock) -> List[Finding]:
        code = block.code.strip()
        if not code:
            return []
        try:
            json.loads(code)
            return []
        except ValueError as exc:
            illustrative = bool(re.search(r"^\s*\.\.\.\s*$|//|/\*|<[A-Za-z_ -]+>", code, re.MULTILINE))
            return [Finding(
                "code.json_invalid",
                Severity.INFO if illustrative else Severity.WARNING,
                f"JSON block at line {block.start_line} is not valid JSON: {exc}",
                {"lang": "json", "block_line": block.start_line, "illustrative": illustrative},
            )]

    def _check_yaml(self, block: FencedBlock) -> List[Finding]:
        if yaml is None:
            return []
        code = block.code
        if not code.strip() or "{{" in code or "{%" in code:
            return []  # template Helm / Jinja / Go : pas du YAML pur
        try:
            list(yaml.safe_load_all(code))
            return []
        except yaml.YAMLError as exc:
            mark = getattr(exc, "problem_mark", None)
            line = (mark.line + 1) if mark is not None else None
            problem = getattr(exc, "problem", None) or str(exc).split("\n")[0]
            return [Finding(
                "code.yaml_invalid",
                Severity.WARNING,
                f"YAML block at line {block.start_line} is not valid YAML"
                + (f" (line {line})" if line else "") + f": {problem}",
                {"lang": "yaml", "block_line": block.start_line, "line": line},
            )]

    # ── code paresseux ────────────────────────────────────────────────────────────

    def _check_laziness(self, block: FencedBlock) -> List[Finding]:
        findings: List[Finding] = []
        for pattern in _LAZY_PATTERNS:
            match = pattern.search(block.code)
            if match:
                line_no = block.code.count("\n", 0, match.start()) + 1
                line = block.code.split("\n")[line_no - 1].strip()
                findings.append(Finding(
                    "code.placeholder",
                    Severity.WARNING,
                    f"Code block at line {block.start_line} contains a placeholder instead of real code "
                    f"(line {line_no}): {line[:120]}",
                    {"lang": block.lang, "block_line": block.start_line, "line": line_no},
                ))
                break
        return findings
