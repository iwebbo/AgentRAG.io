/**
 * codeBlocks.js
 * Détection des fichiers livrables (Jenkinsfile, Dockerfile, values.yaml, README.md, …)
 * dans un message LLM en Markdown, 100 % côté navigateur.
 *
 * API publique :
 *   extractFiles(markdown)  → File[]   (tous les blocs de code, `trivial` = pas un livrable)
 *   exportableFiles(files)  → File[]   (blocs non triviaux)
 *   buildZipBlob(files)     → Promise<Blob>
 *   sanitizePath(path)      → string | null
 *   toDownloadText(content) → string
 *   mimeFor(filename)       → string
 *
 * File : { id, line, filename, basename, kind, lang, content, lines, source, trivial }
 *   - filename : chemin relatif (peut contenir des dossiers, ex. templates/deployment.yaml)
 *   - basename : dernier segment du chemin
 *   - kind     : jeton court pour icône/historique (groovy, yaml, jenkinsfile, dockerfile, md…)
 *   - source   : meta | comment | context | content | lang  (origine du nom détecté)
 *   - line     : ligne de départ du bloc (clé de jointure avec le rendu react-markdown)
 *
 * Ordre de détection du nom : meta de la fence → commentaire en 1re ligne →
 * texte juste avant le bloc → sniffing du contenu → nom par défaut du langage.
 */

import { unified } from 'unified';
import remarkParse from 'remark-parse';
import remarkGfm from 'remark-gfm';
import { visit } from 'unist-util-visit';

// Même parseur (remark + GFM) que react-markdown : les positions de lignes concordent.
const processor = unified().use(remarkParse).use(remarkGfm);

// ─── Tables de référence ──────────────────────────────────────────────────────

const LANG_DEFAULTS = {
  groovy: 'script.groovy', gvy: 'script.groovy',
  jenkinsfile: 'Jenkinsfile',
  gradle: 'build.gradle',
  dockerfile: 'Dockerfile', docker: 'Dockerfile', containerfile: 'Containerfile',
  yaml: 'config.yaml', yml: 'config.yaml',
  json: 'data.json', jsonc: 'data.jsonc',
  toml: 'config.toml', ini: 'config.ini', properties: 'application.properties',
  xml: 'document.xml', html: 'index.html', css: 'style.css',
  bash: 'script.sh', sh: 'script.sh', shell: 'script.sh', zsh: 'script.sh',
  powershell: 'script.ps1', ps1: 'script.ps1', bat: 'script.bat', batch: 'script.bat',
  python: 'script.py', py: 'script.py',
  javascript: 'script.js', js: 'script.js', jsx: 'component.jsx',
  typescript: 'script.ts', ts: 'script.ts', tsx: 'component.tsx',
  go: 'main.go', java: 'Main.java', kotlin: 'Main.kt', kt: 'Main.kt',
  rust: 'main.rs', rs: 'main.rs', csharp: 'Program.cs', cs: 'Program.cs',
  ruby: 'script.rb', rb: 'script.rb', php: 'script.php',
  sql: 'query.sql',
  hcl: 'main.tf', terraform: 'main.tf', tf: 'main.tf',
  makefile: 'Makefile', make: 'Makefile',
  nginx: 'nginx.conf',
  markdown: 'README.md', md: 'README.md',
  gotemplate: 'templates/_helpers.tpl', tpl: 'templates/_helpers.tpl', helm: 'templates/_helpers.tpl',
  diff: 'changes.patch', patch: 'changes.patch',
};

// Sorties/transcriptions : jamais des livrables.
const NON_FILE_LANGS = new Set([
  'console', 'shell-session', 'shellsession', 'log', 'logs', 'output', 'text', 'txt', 'plaintext', 'plain',
]);
const GENERIC_LANGS = new Set(['', 'text', 'txt', 'plaintext', 'plain']);
const SHELL_LANGS = new Set(['bash', 'sh', 'shell', 'zsh']);

const KNOWN_NAMES = new Set([
  'Jenkinsfile', 'Dockerfile', 'Containerfile', 'Makefile', 'Vagrantfile',
  'Gemfile', 'Procfile', 'Caddyfile', 'Brewfile',
]);

// Extensions acceptées quand le nom est déduit d'une phrase (mode strict).
const KNOWN_EXT = new Set([
  'groovy', 'gradle', 'yaml', 'yml', 'json', 'jsonc', 'md', 'sh', 'bash', 'zsh', 'tf', 'tfvars', 'hcl',
  'py', 'js', 'jsx', 'mjs', 'cjs', 'ts', 'tsx', 'xml', 'toml', 'ini', 'cfg', 'conf', 'properties',
  'tpl', 'txt', 'sql', 'html', 'css', 'env', 'ps1', 'bat', 'cmd', 'go', 'java', 'kt', 'rs', 'rb', 'php',
  'cs', 'lock', 'gitignore', 'dockerignore', 'patch',
]);

// Familles d'extensions compatibles (évite de nommer un bloc bash « values.yaml »).
const GROUPS = [
  ['yaml', 'yml'], ['json', 'jsonc'], ['md', 'markdown'], ['groovy', 'gradle', 'jenkinsfile'],
  ['dockerfile', 'containerfile'], ['sh', 'bash', 'zsh'], ['ps1'], ['bat', 'cmd'],
  ['tf', 'tfvars', 'hcl'], ['js', 'jsx', 'mjs', 'cjs'], ['ts', 'tsx'], ['py'], ['toml'],
  ['ini', 'cfg', 'conf', 'properties', 'env'], ['xml'], ['html', 'htm'], ['css'], ['sql'],
  ['tpl'], ['makefile'], ['patch', 'diff'], ['go'], ['java'], ['kt'], ['rs'], ['rb'], ['php'], ['cs'],
];
const GROUP_OF = new Map();
GROUPS.forEach((g, i) => g.forEach((t) => GROUP_OF.set(t, i)));

const CACHE_MAX = 100;
const cache = new Map();
const EMPTY = Object.freeze([]);

// ─── Helpers de nommage ───────────────────────────────────────────────────────

function normalizeLang(raw) {
  return String(raw || '').trim().toLowerCase().replace(/^language-/, '');
}

function fileToken(filename) {
  const base = filename.split('/').pop().toLowerCase();
  const named = /^(jenkinsfile|dockerfile|containerfile|makefile)/.exec(base);
  if (named) return named[1];
  const ext = /\.([a-z0-9]+)$/.exec(base);
  return ext ? ext[1] : base;
}

function looksLikeFilename(s, strict = false) {
  if (!s || s.length > 120 || /\s/.test(s)) return false;
  if (!/^(?:[\w.@+-]+\/)*[\w.@+-]+$/.test(s)) return false;
  const base = s.split('/').pop();
  if (KNOWN_NAMES.has(base) || /^Jenkinsfile[.\w-]*$/.test(base)) return true;
  const m = /\.([A-Za-z][A-Za-z0-9]{0,9})$/.exec(base);
  if (!m) return false;
  return strict ? KNOWN_EXT.has(m[1].toLowerCase()) : true;
}

function compatible(lang, filename) {
  const def = LANG_DEFAULTS[lang];
  if (!def) return true;
  const a = GROUP_OF.get(fileToken(filename));
  const b = GROUP_OF.get(fileToken(def));
  return a === undefined || b === undefined || a === b;
}

/** Nettoie un chemin issu du LLM : pas de `..`, pas de chemin absolu, pas de caractères interdits. */
export function sanitizePath(p) {
  if (typeof p !== 'string') return null;
  const parts = p
    .replace(/\\/g, '/')
    .split('/')
    .map((seg) =>
      [...seg]
        .map((c) => (c.charCodeAt(0) < 32 || '<>:"|?*'.includes(c) ? '_' : c))
        .join('')
        .trim()
    )
    .filter((seg) => seg && seg !== '.' && seg !== '..')
    .map((seg) => seg.slice(0, 100));
  return parts.length ? parts.join('/') : null;
}

function nameFromMeta(meta) {
  if (!meta) return null;
  const kv = /(?:title|file(?:name)?|name|path)\s*=\s*(?:"([^"]+)"|'([^']+)'|(\S+))/i.exec(meta);
  if (kv) {
    const v = kv[1] || kv[2] || kv[3];
    if (looksLikeFilename(v)) return v;
  }
  for (const tok of meta.split(/\s+/)) {
    if (looksLikeFilename(tok)) return tok;
  }
  return null;
}

const FIRST_LINE_RE =
  /^\s*(?:\/\/|#|--|;|\/\*+|<!--)\s*(?:(?:file(?:name)?|path)\s*[:=]\s*)?(\S+?)\s*(?:\*\/|-->)?\s*$/i;

function nameFromFirstLine(value) {
  const first = value.split('\n', 1)[0];
  if (first.startsWith('#!')) return null;
  const m = FIRST_LINE_RE.exec(first);
  return m && looksLikeFilename(m[1]) ? m[1] : null;
}

function collectInline(node, acc) {
  if (!node) return acc;
  if (node.type === 'text') acc.text.push(node.value);
  else if (node.type === 'inlineCode') {
    acc.text.push(node.value);
    acc.codes.push(node.value);
  }
  if (Array.isArray(node.children)) node.children.forEach((c) => collectInline(c, acc));
  return acc;
}

function nameFromContext(node, lang) {
  if (!node || (node.type !== 'paragraph' && node.type !== 'heading')) return null;
  const { text, codes } = collectInline(node, { text: [], codes: [] });
  const joined = text.join(' ');
  if (joined.length > 160) return null;
  for (const c of codes) {
    if (looksLikeFilename(c) && compatible(lang, c)) return c;
  }
  for (const raw of joined.split(/\s+/)) {
    const tok = raw.replace(/^[("'[]+|[)"'\].,;:!?]+$/g, '');
    if (looksLikeFilename(tok, true) && compatible(lang, tok)) return tok;
  }
  return null;
}

function firstInstruction(code) {
  for (const line of code.split('\n')) {
    const t = line.trim();
    if (!t || t.startsWith('#') || /^ARG\s/i.test(t)) continue;
    return t;
  }
  return '';
}

function sniff(lang, code) {
  const generic = GENERIC_LANGS.has(lang);
  const yamlish = lang === 'yaml' || lang === 'yml' || generic;

  if (lang === 'jenkinsfile') return 'Jenkinsfile';
  if ((lang === 'groovy' || generic) && /^\s*pipeline\s*\{/m.test(code)) return 'Jenkinsfile';
  if (generic && /^FROM\s+\S+/i.test(firstInstruction(code))) return 'Dockerfile';

  if (yamlish) {
    if (/^services:\s*$/m.test(code) && !/^apiVersion:/m.test(code)) return 'docker-compose.yml';
    if (/^['"]?on['"]?:/m.test(code) && /^jobs:\s*$/m.test(code)) return '.github/workflows/ci.yml';
    if (/^stages:\s*$/m.test(code) && /^\s+script:/m.test(code)) return '.gitlab-ci.yml';
    const kind = /^kind:\s*([A-Za-z]+)/m.exec(code);
    if (
      /^apiVersion:\s*v[12]\s*$/m.test(code) && /^name:\s*\S+/m.test(code) &&
      /^version:\s*\S+/m.test(code) && !kind
    ) {
      return 'Chart.yaml';
    }
    if (/^apiVersion:\s*\S+/m.test(code) && kind) {
      const name = `${kind[1].toLowerCase()}.yaml`;
      return /\{\{[-\s]/.test(code) ? `templates/${name}` : name;
    }
  }

  if ((lang === 'xml' || generic) && /<project[\s>]/.test(code) && /<modelVersion>/.test(code)) {
    return 'pom.xml';
  }
  return null;
}

function countLines(value) {
  return value.replace(/\n+$/, '').split('\n').length;
}

function isTrivial(source, lang, value, lines) {
  if (source !== 'lang') return false;
  if (NON_FILE_LANGS.has(lang) || !LANG_DEFAULTS[lang]) return true;
  const min = SHELL_LANGS.has(lang) && !value.startsWith('#!') ? 6 : 3;
  return lines < min;
}

function describeBlock({ node, previous, index }) {
  const parts = String(node.lang || '').split(':');
  const lang = normalizeLang(parts[0]);
  const colonName = parts.slice(1).join(':');
  const value = node.value || '';

  let filename = null;
  let source = null;

  const explicit = (looksLikeFilename(colonName) ? colonName : null) || nameFromMeta(node.meta);
  if (explicit) { filename = explicit; source = 'meta'; }

  if (!filename) {
    const c = nameFromFirstLine(value);
    if (c) { filename = c; source = 'comment'; }
  }
  if (!filename) {
    const c = nameFromContext(previous, lang);
    if (c) { filename = c; source = 'context'; }
  }
  if (!filename) {
    const c = sniff(lang, value);
    if (c) { filename = c; source = 'content'; }
  }
  if (!filename) {
    filename = LANG_DEFAULTS[lang] || 'snippet.txt';
    source = 'lang';
  }

  const path = sanitizePath(filename) || 'snippet.txt';
  const lines = countLines(value);
  return {
    id: `block-${index}`,
    line: node.position?.start?.line ?? 0,
    filename: path,
    basename: path.split('/').pop(),
    kind: fileToken(path),
    lang,
    content: value,
    lines,
    source,
    trivial: isTrivial(source, lang, value, lines),
  };
}

/** Évite les collisions de noms (deployment.yaml, deployment-2.yaml, …). */
function dedupe(files) {
  const seen = new Map();
  return files.map((f) => {
    const key = f.filename.toLowerCase();
    const n = (seen.get(key) || 0) + 1;
    seen.set(key, n);
    if (n === 1) return f;
    const slash = f.filename.lastIndexOf('/');
    const dir = f.filename.slice(0, slash + 1);
    const base = f.filename.slice(slash + 1);
    const dot = base.lastIndexOf('.');
    const name = dot > 0 ? `${base.slice(0, dot)}-${n}${base.slice(dot)}` : `${base}-${n}`;
    return { ...f, filename: dir + name, basename: name };
  });
}

// ─── API ──────────────────────────────────────────────────────────────────────

function parse(markdown) {
  const tree = processor.parse(markdown);
  const raw = [];
  visit(tree, 'code', (node, idx, parent) => {
    if (!(node.value || '').trim()) return;
    raw.push(
      describeBlock({
        node,
        previous: parent && idx > 0 ? parent.children[idx - 1] : null,
        index: raw.length,
      })
    );
  });

  // Dédoublonnage uniquement entre livrables : un snippet trivial ne renomme pas un vrai fichier.
  const unique = dedupe(raw.filter((f) => !f.trivial));
  let cursor = 0;
  return Object.freeze(raw.map((f) => (f.trivial ? f : unique[cursor++])));
}

export function extractFiles(markdown) {
  if (typeof markdown !== 'string' || !markdown) return EMPTY;
  const hit = cache.get(markdown);
  if (hit) return hit;
  const result = parse(markdown);
  cache.set(markdown, result);
  if (cache.size > CACHE_MAX) cache.delete(cache.keys().next().value);
  return result;
}

export function exportableFiles(files) {
  return files.filter((f) => !f.trivial);
}

export function toDownloadText(content) {
  return content.endsWith('\n') ? content : `${content}\n`;
}

export function mimeFor(filename) {
  const t = fileToken(filename);
  if (t === 'md') return 'text/markdown;charset=utf-8';
  if (t === 'json' || t === 'jsonc') return 'application/json;charset=utf-8';
  return 'text/plain;charset=utf-8';
}

/** ZIP côté navigateur (fflate chargé à la demande). Bit exécutable posé sur les scripts shell. */
export async function buildZipBlob(files) {
  const { zipSync, strToU8 } = await import('fflate');
  const entries = {};
  const used = new Set();
  for (const f of files) {
    let path = f.filename;
    while (used.has(path.toLowerCase())) path = `dup-${path}`;
    used.add(path.toLowerCase());
    const text = toDownloadText(f.content);
    const executable = f.kind === 'sh' || f.content.startsWith('#!');
    entries[path] = [strToU8(text), { os: 3, attrs: (executable ? 0o100755 : 0o100644) * 65536 }];
  }
  return new Blob([zipSync(entries)], { type: 'application/zip' });
}
