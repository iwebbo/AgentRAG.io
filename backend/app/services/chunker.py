"""
Chunker sémantique (v2).

Principe : un chunk = une unité de sens, pas une tranche de N tokens.
  - Python               : AST (fonction / classe / méthode). Repli sur le découpeur générique
                           si le fichier ne parse pas.
  - Autres langages code : blocs de premier niveau (ligne en colonne 0 après une ligne vide).
  - Markdown / AsciiDoc  : sections par titre (chemin de titres dans les métadonnées),
                           blocs de code (fences) jamais coupés au milieu d'un paragraphe.
  - Le reste (txt, texte de PDF/DOCX, yaml, json...) : paragraphes.

Garanties (vérifiées par tests/test_chunker.py) :
  - aucune perte : toutes les lignes non vides du fichier se retrouvent, dans l'ordre,
    dans les chunks (l'overlap, uniquement pour les textes, ne fait qu'ajouter des doublons) ;
  - aucun chunk ne dépasse la taille cible en tokens, en-tête compris ;
  - indentation et retours à la ligne conservés ;
  - métadonnées compatibles Chroma (str / int / float / bool uniquement).

Réglages (variables d'environnement, tokens du tokenizer tiktoken) :
  RAG_CHUNK_CODE_TOKENS      défaut 600
  RAG_CHUNK_DOC_TOKENS       défaut 800
  RAG_CHUNK_STANDARD_TOKENS  défaut 800
La taille doit rester cohérente avec la fenêtre du modèle d'embedding : un texte plus long que
sa fenêtre est tronqué à l'encodage (all-MiniLM-L6-v2 : 256 tokens, Qwen3-Embedding : 32K).

"""
from __future__ import annotations

import ast
import logging
import os
import re
import warnings
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

import tiktoken

logger = logging.getLogger(__name__)

CHUNKER_VERSION = "semantic-v2"

# Place réservée à l'en-tête "# File: ... | symbole | L10-42" dans le budget de chaque chunk.
HEADER_RESERVE = 40

CODE_EXTENSIONS = {
    ".py", ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".java", ".kt", ".scala", ".swift",
    ".go", ".rs", ".c", ".h", ".cpp", ".cc", ".hpp", ".cs", ".rb", ".php", ".sh", ".bash",
    ".sql", ".vue", ".groovy", ".r", ".css",
}
DOC_EXTENSIONS = {".md", ".markdown", ".txt", ".rst", ".adoc"}

_EXTRACTOR_BANNER = re.compile(r"\A=== [^\n]+ \([^\n)]+\) ===\n\n")
_FENCE = ("```", "~~~")
_CLOSER_START = re.compile(r"^(?:[\}\)\]]|else\b|elif\b|except\b|finally\b|catch\b)")
_SENTENCE = re.compile(r".*?[.!?;](?:\s+|$)|.+$", re.S)
_GO_METHOD = re.compile(r"\bfunc\s*\([^)]*\)\s*([A-Za-z_]\w*)")
_DECL = re.compile(
    r"\b(?:function\*?|class|interface|enum|struct|trait|impl|fn|func|def|type|namespace|"
    r"module|object|record)\s+\*?([A-Za-z_$][\w$]*)"
)
_ASSIGN = re.compile(r"\b(?:const|let|var|val)\s+([A-Za-z_$][\w$]*)\s*[=:]")
_COMMENT_START = ("//", "/*", "*", "#", "@", "--")


class _ApproxEncoding:
    """Repli hors ligne si tiktoken ne peut pas charger son vocabulaire : 1 token ≈ 4 caractères."""

    def encode(self, text: str, **_kw) -> List[str]:
        return [text[i:i + 4] for i in range(0, len(text), 4)]

    def decode(self, tokens: List[str]) -> str:
        return "".join(tokens)


def _load_encoding(model: str):
    try:
        try:
            return tiktoken.encoding_for_model(model)
        except KeyError:
            return tiktoken.get_encoding("cl100k_base")
    except Exception as exc:  # pas de réseau / cache tiktoken absent
        logger.warning(
            "tiktoken indisponible (%s) : comptage approximatif (4 car./token). "
            "Définir TIKTOKEN_CACHE_DIR avec un vocabulaire pré-téléchargé.", exc
        )
        return _ApproxEncoding()


def _env_int(name: str) -> Optional[int]:
    raw = os.getenv(name, "").strip()
    try:
        value = int(raw) if raw else 0
    except ValueError:
        return None
    return value if value > 0 else None


@dataclass
class _Ctx:
    lines: List[str]
    budget: int          # tokens max du corps d'un chunk (hors en-tête)
    min_tokens: int      # en dessous, une unité est fusionnée avec sa voisine
    overlap: int         # tokens d'overlap (textes uniquement)


@dataclass
class _Unit:
    text: str
    start: int           # index de ligne 0-based, inclus
    end: int             # index de ligne 0-based, exclu
    symbol: str
    kind: str
    tokens: int
    names: List[str] = field(default_factory=list)
    atomic: bool = False  # fragment d'une ligne géante : jamais fusionné


class SmartChunker:
    """Découpage sémantique, compatible avec l'ancienne API (chunk_text(text, metadata))."""

    PROFILES = {
        "code_analysis": {
            "chunk_size": 600,
            "min_tokens": 120,
            "overlap": 0,
            "description": "Code (unités sémantiques)",
        },
        "documentation": {
            "chunk_size": 800,
            "min_tokens": 200,
            "overlap": 60,
            "description": "Documentation technique (sections)",
        },
        "standard": {
            "chunk_size": 800,
            "min_tokens": 200,
            "overlap": 60,
            "description": "Usage standard (paragraphes)",
        },
        "project_full": {
            "chunk_size": 32000,
            "overlap": 1000,
            "min_tokens": 2000,
            "description": "Projet complet (256K context)",
        },
    }
    _ENV_SIZE = {
        "code_analysis": "RAG_CHUNK_CODE_TOKENS",
        "documentation": "RAG_CHUNK_DOC_TOKENS",
        "standard": "RAG_CHUNK_STANDARD_TOKENS",
    }

    def __init__(self, model: str = "gpt-4", chunk_size: Optional[int] = 2000, overlap: Optional[int] = 200):
        """
        chunk_size : plafond en tokens par chunk (None/0 = pas de plafond). La taille effective est
                     min(profil, chunk_size) : le réglage du projet ne peut que réduire.
        overlap    : plafond d'overlap en tokens, appliqué aux textes uniquement.
        """
        self.encoding = _load_encoding(model)
        self.chunk_size = chunk_size if chunk_size and chunk_size > 0 else None
        self.overlap = overlap if overlap is not None and overlap >= 0 else None
        self.profiles = {name: dict(p) for name, p in self.PROFILES.items()}
        for name, var in self._ENV_SIZE.items():
            value = _env_int(var)
            if value:
                self.profiles[name]["chunk_size"] = value
        logger.info(
            "✅ Chunker %s initialized (cap=%s, overlap_cap=%s)", CHUNKER_VERSION, self.chunk_size, self.overlap
        )

    # ------------------------------------------------------------------ API

    def _select_profile(self, filename: str) -> Dict:
        ext = Path(filename).suffix.lower()
        if ext in CODE_EXTENSIONS:
            name = "code_analysis"
        elif ext in DOC_EXTENSIONS:
            name = "documentation"
        else:
            name = "standard"
        logger.debug("Profile selected: %s for '%s'", name, filename)
        return self.profiles[name]

    def chunk_text(self, text: str, metadata: Dict) -> List[Dict]:
        if not text or not text.strip():
            return []

        filename = str(metadata.get("filename", "") or "")
        ext = Path(filename).suffix.lower()
        profile = self._select_profile(filename)

        size = profile["chunk_size"]
        if self.chunk_size:
            size = min(size, self.chunk_size)
        budget = max(size - HEADER_RESERVE, 64)
        overlap = profile["overlap"]
        if self.overlap is not None:
            overlap = min(overlap, self.overlap)

        normalized = text.replace("\r\n", "\n").replace("\r", "\n")
        if ext in CODE_EXTENSIONS:
            # DocumentProcessor._extract_code préfixe "=== nom (type) ===" : sans ce retrait, ast.parse échoue
            # et les numéros de ligne ne correspondent plus au fichier réel.
            normalized = _EXTRACTOR_BANNER.sub("", normalized, count=1)
        ctx = _Ctx(
            lines=normalized.split("\n"),
            budget=budget,
            min_tokens=min(profile["min_tokens"], budget // 2),
            overlap=min(overlap, budget // 3),
        )

        units: Optional[List[_Unit]] = None
        if ext == ".py":
            units = self._chunk_python(ctx, normalized)
        if units is None:
            if ext in CODE_EXTENSIONS:
                units = self._chunk_code_generic(ctx)
            else:
                units = self._chunk_text_path(ctx, ext)
        units = self._pack(ctx, units)

        chunks: List[Dict] = []
        for index, unit in enumerate(units):
            header = f"# File: {filename}"
            if unit.symbol:
                header += f" | {unit.symbol}"
            header += f" | L{unit.start + 1}-{unit.end}"
            chunk_text = f"{header}\n\n{unit.text}"
            chunks.append({
                "text": chunk_text,
                "metadata": {
                    **metadata,
                    "chunk_index": index,
                    "profile": profile["description"],
                    "symbol": unit.symbol,
                    "kind": unit.kind,
                    "start_line": unit.start + 1,
                    "end_line": unit.end,
                    "chunker": CHUNKER_VERSION,
                },
                "tokens": self._count(chunk_text),
            })

        if chunks:
            sizes = [c["tokens"] for c in chunks]
            logger.info(
                "📦 %s → %d chunks (profile: %s, avg=%d, max=%d tokens)",
                filename or "<text>", len(chunks), profile["description"], sum(sizes) // len(sizes), max(sizes),
            )
        return chunks

    # ------------------------------------------------------------ primitives

    def _count(self, text: str) -> int:
        return len(self.encoding.encode(text, disallowed_special=())) if text else 0

    def _mk(self, ctx: _Ctx, a: int, b: int, symbol: str, kind: str) -> Optional[_Unit]:
        """Unité sur lignes [a, b), lignes vides de bord retirées, tokens exacts."""
        lines = ctx.lines
        while a < b and not lines[a].strip():
            a += 1
        while b > a and not lines[b - 1].strip():
            b -= 1
        if a >= b:
            return None
        text = "\n".join(lines[a:b])
        return _Unit(text, a, b, symbol, kind, self._count(text), names=[symbol] if symbol else [])

    def _fit_range(self, ctx: _Ctx, a: int, b: int, symbol: str, kind: str) -> List[_Unit]:
        unit = self._mk(ctx, a, b, symbol, kind)
        if unit is None:
            return []
        if unit.tokens <= ctx.budget:
            return [unit]
        return self._split_lines(ctx, unit.start, unit.end, symbol, kind)

    def _split_lines(self, ctx: _Ctx, lo: int, hi: int, symbol: str, kind: str) -> List[_Unit]:
        """Découpe sans perte une plage trop grande, de préférence sur une frontière de bloc."""
        lines = ctx.lines
        target = int(ctx.budget * 0.9)
        ltoks = [self._count(lines[k]) + 1 for k in range(lo, hi)]
        out: List[_Unit] = []
        i = lo
        while i < hi:
            if not lines[i].strip():
                i += 1
                continue
            j, acc = i, 0
            while j < hi and (j == i or acc + ltoks[j - lo] <= target):
                acc += ltoks[j - lo]
                j += 1
            cut = self._best_cut(ctx, i, j) if j < hi else j
            unit = self._mk(ctx, i, cut, symbol, kind)
            while unit is not None and unit.tokens > ctx.budget and cut > i + 1:
                cut -= 1
                unit = self._mk(ctx, i, cut, symbol, kind)
            if unit is None:
                i = cut
                continue
            if unit.tokens > ctx.budget:  # une seule ligne dépasse le budget
                out.extend(self._split_long_line(ctx, i, symbol, kind))
            else:
                out.append(unit)
            i = cut
        return out

    @staticmethod
    def _best_cut(ctx: _Ctx, i: int, j: int) -> int:
        """Meilleur début du chunk suivant dans (i, j] : indentation minimale, après ligne vide, le plus tard."""
        lines = ctx.lines
        best_k, best_score = j, None
        for k in range(i + max(1, (j - i) // 2), j + 1):
            line = lines[k]
            if not line.strip() or _CLOSER_START.match(line.lstrip()):
                continue
            indent = len(line) - len(line.lstrip())
            score = (indent, 0 if not lines[k - 1].strip() else 1, -k)
            if best_score is None or score < best_score:
                best_k, best_score = k, score
        return best_k

    def _split_long_line(self, ctx: _Ctx, idx: int, symbol: str, kind: str) -> List[_Unit]:
        """Ligne unique plus grande que le budget : phrases, puis découpe en caractères (sans perte)."""
        line = ctx.lines[idx]
        target = int(ctx.budget * 0.9)
        pieces: List[str] = []
        cur, cur_t = "", 0
        for part in _SENTENCE.findall(line) or [line]:
            part_t = self._count(part)
            if part_t > target:
                if cur:
                    pieces.append(cur)
                    cur, cur_t = "", 0
                pieces.extend(self._hard_split(part, target))
                continue
            if cur and cur_t + part_t > target:
                pieces.append(cur)
                cur, cur_t = "", 0
            cur += part
            cur_t += part_t
        if cur:
            pieces.append(cur)

        units: List[_Unit] = []
        for piece in pieces:
            if not piece.strip():
                continue
            for sub in ([piece] if self._count(piece) <= ctx.budget else self._hard_split(piece, ctx.budget)):
                units.append(_Unit(sub, idx, idx + 1, symbol, kind, self._count(sub),
                                   names=[symbol] if symbol else [], atomic=True))
        return units

    def _hard_split(self, text: str, budget: int) -> List[str]:
        """Dernier recours : tranches de caractères dont le nombre de tokens ≤ budget (jamais au milieu d'un caractère)."""
        total = max(self._count(text), 1)
        step = max(1, int(budget * (len(text) / total) * 0.9))
        out: List[str] = []
        rest = text
        while rest:
            n = min(step, len(rest))
            piece = rest[:n]
            while n > 1 and self._count(piece) > budget:
                n = max(1, int(n * 0.8))
                piece = rest[:n]
            out.append(piece)
            rest = rest[n:]
        return out

    # --------------------------------------------------------------- Python

    def _chunk_python(self, ctx: _Ctx, source: str) -> Optional[List[_Unit]]:
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                tree = ast.parse(source)
        except Exception:
            logger.debug("Python non parsable, repli sur le découpage générique")
            return None
        return self._py_units(ctx, tree.body, 0, len(ctx.lines), "", "")

    def _py_units(self, ctx: _Ctx, nodes, lo: int, hi: int, prefix: str, label: str) -> List[_Unit]:
        """Partition complète de [lo, hi) : defs/classes et code entre elles (imports, constantes, main)."""
        out: List[_Unit] = []
        cursor = lo
        gap_symbol = label or "<module>"
        gap_kind = "class_body" if prefix else "module"
        for node in nodes:
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                continue
            start = self._py_start(ctx, node, cursor)
            end = min(node.end_lineno or node.lineno, hi)
            if end <= start:
                continue
            if start > cursor:
                out.extend(self._fit_range(ctx, cursor, start, gap_symbol, gap_kind))
            symbol = f"{prefix}{node.name}"
            if isinstance(node, ast.ClassDef):
                unit = self._mk(ctx, start, end, symbol, "class")
                if unit is not None and unit.tokens > ctx.budget:
                    out.extend(self._py_units(ctx, node.body, start, end, symbol + ".", symbol))
                elif unit is not None:
                    out.append(unit)
            else:
                out.extend(self._fit_range(ctx, start, end, symbol, "method" if prefix else "function"))
            cursor = end
        if cursor < hi:
            out.extend(self._fit_range(ctx, cursor, hi, gap_symbol, gap_kind))
        return out

    @staticmethod
    def _py_start(ctx: _Ctx, node, cursor: int) -> int:
        """Début réel d'une def/classe : décorateurs et commentaires accolés inclus."""
        first = node.lineno - 1
        decorators = getattr(node, "decorator_list", None)
        if decorators:
            first = min(first, min(d.lineno for d in decorators) - 1)
        while first > cursor and ctx.lines[first - 1].lstrip().startswith("#"):
            first -= 1
        return max(first, cursor)

    # ------------------------------------------------- autres langages de code

    def _chunk_code_generic(self, ctx: _Ctx) -> List[_Unit]:
        lines = ctx.lines
        bounds = [0]
        for i in range(1, len(lines)):
            line = lines[i]
            if line and not line[0].isspace() and not _CLOSER_START.match(line) and not lines[i - 1].strip():
                bounds.append(i)
        bounds.append(len(lines))
        out: List[_Unit] = []
        for a, b in zip(bounds, bounds[1:]):
            out.extend(self._fit_range(ctx, a, b, self._guess_symbol(lines[a:b]), "code"))
        return out

    @staticmethod
    def _guess_symbol(block: List[str]) -> str:
        seen = 0
        for raw in block:
            line = raw.strip()
            if not line:
                continue
            seen += 1
            if seen > 8:
                break
            if line.startswith(_COMMENT_START):
                continue
            for pattern in (_GO_METHOD, _DECL, _ASSIGN):
                match = pattern.search(line)
                if match:
                    return match.group(1)
        return ""

    # ------------------------------------------------- documentation / texte

    def _chunk_text_path(self, ctx: _Ctx, ext: str) -> List[_Unit]:
        out: List[_Unit] = []
        for a, b, symbol in self._sections(ctx, ext):
            out.extend(self._split_paragraphs(ctx, a, b, symbol, "section" if symbol else "text"))
        return out

    @staticmethod
    def _sections(ctx: _Ctx, ext: str):
        """Sections par titre (Markdown / AsciiDoc), chemin de titres conservé, fences ignorées."""
        lines = ctx.lines
        if ext in (".md", ".markdown"):
            heading = re.compile(r"^(#{1,6})\s+(\S.*)$")
        elif ext == ".adoc":
            heading = re.compile(r"^(={1,6})\s+(\S.*)$")
        else:
            return [(0, len(lines), "")]
        sections = []
        stack: List[tuple] = []
        start, symbol = 0, ""
        in_fence = False
        for i, line in enumerate(lines):
            if line.lstrip().startswith(_FENCE):
                in_fence = not in_fence
                continue
            if in_fence:
                continue
            match = heading.match(line)
            if not match:
                continue
            if i > start:
                sections.append((start, i, symbol))
            level = len(match.group(1))
            title = match.group(2).strip().rstrip("#").strip()
            while stack and stack[-1][0] >= level:
                stack.pop()
            stack.append((level, title))
            start, symbol = i, " > ".join(t for _, t in stack)
        sections.append((start, len(lines), symbol))
        return sections

    @staticmethod
    def _paragraphs(ctx: _Ctx, a: int, b: int) -> List[tuple]:
        paragraphs = []
        start: Optional[int] = None
        in_fence = False
        for i in range(a, b):
            line = ctx.lines[i]
            if line.lstrip().startswith(_FENCE):
                in_fence = not in_fence
            if not line.strip() and not in_fence:
                if start is not None:
                    paragraphs.append((start, i))
                    start = None
            elif start is None:
                start = i
        if start is not None:
            paragraphs.append((start, b))
        return paragraphs

    def _split_paragraphs(self, ctx: _Ctx, a: int, b: int, symbol: str, kind: str) -> List[_Unit]:
        out: List[_Unit] = []
        current: List[tuple] = []  # (start, end, tokens)
        current_t = 0

        def flush() -> None:
            if current:
                out.extend(self._fit_range(ctx, current[0][0], current[-1][1], symbol, kind))

        for pa, pb in self._paragraphs(ctx, a, b):
            pt = self._count("\n".join(ctx.lines[pa:pb]))
            if pt > ctx.budget:
                flush()
                current, current_t = [], 0
                out.extend(self._split_lines(ctx, pa, pb, symbol, kind))
                continue
            if current and current_t + pt + 2 > ctx.budget:
                tail = self._overlap_tail(current, ctx.overlap)
                flush()
                current = list(tail) if sum(t for _, _, t in tail) + pt + 2 <= ctx.budget else []
                current_t = sum(t + 2 for _, _, t in current)
            current.append((pa, pb, pt))
            current_t += pt + 2
        flush()
        return out

    @staticmethod
    def _overlap_tail(current: List[tuple], overlap: int) -> List[tuple]:
        if overlap <= 0:
            return []
        tail: List[tuple] = []
        total = 0
        for item in reversed(current):
            if total + item[2] > overlap:
                break
            tail.insert(0, item)
            total += item[2]
        return tail[1:] if len(tail) == len(current) else tail

    # ---------------------------------------------------------------- fusion

    def _pack(self, ctx: _Ctx, units: List[_Unit]) -> List[_Unit]:
        """Fusionne les unités trop petites avec leur voisine (sans dépasser le budget)."""
        out: List[_Unit] = []
        current: Optional[_Unit] = None
        for unit in units:
            if current is None:
                current = unit
                continue
            if not current.atomic and not unit.atomic and current.tokens < ctx.min_tokens:
                merged = self._mk(ctx, current.start, unit.end, "", "")
                if merged is not None and merged.tokens <= ctx.budget:
                    names = list(dict.fromkeys(current.names + unit.names))
                    merged.names = names
                    merged.symbol = ", ".join(names[:5]) + (f" +{len(names) - 5}" if len(names) > 5 else "")
                    merged.kind = current.kind if current.kind == unit.kind else "mixed"
                    current = merged
                    continue
            out.append(current)
            current = unit
        if current is not None:
            out.append(current)
        return out
