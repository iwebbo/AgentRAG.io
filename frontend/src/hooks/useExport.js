/**
 * useExport.js
 * Hook centralisant l'export de contenu LLM.
 *
 *  - Formats via le backend AgentRAG : PDF | DOCX | XLSX | HTML
 *  - Formats 100 % locaux (Blob navigateur, aucun appel réseau) :
 *      · MD                      → message complet en Markdown
 *      · fichier détecté         → Jenkinsfile, .groovy, Dockerfile, values.yaml, README.md, …
 *      · ZIP de fichiers détectés → arborescence conservée (ex. chart Helm)
 *
 * Interface publique rétro-compatible (ExportButton.jsx & ExportHistory.jsx) :
 *   exportContent(content, format, title)
 *   exportFile(file)                    — file issu de utils/codeBlocks.extractFiles
 *   exportFilesZip(files, title)
 *   getHistory()
 *   clearHistory()
 *   exporting {boolean}
 *   exportError {string|null}
 */

import { useState, useCallback } from 'react';
import api from '../services/api';
import { buildZipBlob, mimeFor, toDownloadText } from '../utils/codeBlocks';

// ─── Formats rendus localement ────────────────────────────────────────────────

const LOCAL_FORMATS = new Set(['md']);

// ─── Historique local (ExportHistory en dépend) ───────────────────────────────

const HISTORY_KEY = 'agentrag_export_history';
const MAX_HISTORY = 50;

function loadHistory() {
  try {
    return JSON.parse(localStorage.getItem(HISTORY_KEY) || '[]');
  } catch {
    return [];
  }
}

function saveHistory(entry) {
  try {
    const history = loadHistory();
    history.unshift(entry);
    localStorage.setItem(HISTORY_KEY, JSON.stringify(history.slice(0, MAX_HISTORY)));
  } catch {
    /* quota dépassé ou stockage indisponible : l'historique est best-effort */
  }
}

// crypto.randomUUID n'existe qu'en contexte sécurisé (https / localhost).
function newId() {
  return globalThis.crypto?.randomUUID?.() ?? `${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
}

function recordHistory({ filename, format, title, size, preview }) {
  const entry = {
    id: newId(),
    filename,
    format,
    title,
    size,
    createdAt: new Date().toISOString(),
    preview: String(preview || '').substring(0, 300),
  };
  saveHistory(entry);
  return entry;
}

// ─── Utilitaires ──────────────────────────────────────────────────────────────

/** Nom de fichier sûr : sans symboles markdown ni caractères interdits. */
function safeName(title, fallback = 'export') {
  const cleaned = [...String(title || '').replace(/[#*`>[\]]/g, '')]
    .map((c) => (c.charCodeAt(0) < 32 || '<>:"/\\|?*'.includes(c) ? '_' : c))
    .join('')
    .replace(/\s+/g, ' ')
    .trim()
    .substring(0, 80);
  return cleaned || fallback;
}

function triggerDownload(blob, filename) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

// Les erreurs backend arrivent comme des blobs (responseType: 'blob').
async function extractErrorMessage(err) {
  let message = err.message || 'Erreur lors de la génération.';
  if (err.response?.data instanceof Blob) {
    try {
      const text = await err.response.data.text();
      const parsed = JSON.parse(text);
      message = parsed.detail || parsed.message || message;
    } catch {
      message = `Erreur serveur ${err.response.status}`;
    }
  }
  return message;
}

// ─── Hook ─────────────────────────────────────────────────────────────────────

export function useExport() {
  const [exporting, setExporting] = useState(false);
  const [exportError, setExportError] = useState(null);

  // Enveloppe commune : état de chargement + gestion d'erreur homogène.
  const run = useCallback(async (task) => {
    setExporting(true);
    setExportError(null);
    try {
      return await task();
    } catch (err) {
      const message = await extractErrorMessage(err);
      console.error('[useExport]', message, err);
      setExportError(message);
      throw new Error(message);
    } finally {
      setExporting(false);
    }
  }, []);

  /**
   * Exporte du contenu Markdown (backend, ou local pour 'md') et déclenche le téléchargement.
   *
   * @param {string} content  — Contenu Markdown du message LLM
   * @param {string} format   — 'pdf' | 'docx' | 'xlsx' | 'html' | 'md'
   * @param {string} [title]  — Titre du document (défaut : 'export')
   * @returns {object}        — Entry d'historique { id, filename, format, ... }
   */
  const exportContent = useCallback(
    async (content, format, title = 'export') => {
      if (!content?.trim()) {
        setExportError('Aucun contenu à exporter.');
        return undefined;
      }

      return run(async () => {
        const safeTitle = safeName(title);
        let blob;
        let filename = `${safeTitle}.${format}`;

        if (LOCAL_FORMATS.has(format)) {
          blob = new Blob([toDownloadText(content)], { type: mimeFor(filename) });
        } else {
          const response = await api.post(
            `/api/export/${format}`,
            { content, title: safeTitle },
            { responseType: 'blob' }
          );

          // Résolution du nom de fichier (Content-Disposition RFC 5987)
          const disposition = response.headers?.['content-disposition'] || '';
          const utf8Match = disposition.match(/filename\*=UTF-8''([^\s;]+)/i);
          const asciiMatch = disposition.match(/filename="?([^";\n]+)"?/i);
          if (utf8Match) {
            filename = decodeURIComponent(utf8Match[1]);
          } else if (asciiMatch) {
            filename = asciiMatch[1].trim();
          }
          blob = response.data;
        }

        triggerDownload(blob, filename);
        return recordHistory({ filename, format, title: safeTitle, size: blob.size, preview: content });
      });
    },
    [run]
  );

  /**
   * Télécharge un fichier détecté dans un bloc de code (aucun appel backend).
   * @param {object} file — { filename, basename, kind, content } (utils/codeBlocks)
   */
  const exportFile = useCallback(
    (file) =>
      run(async () => {
        if (!file?.content?.trim()) throw new Error('Aucun contenu à exporter.');
        const blob = new Blob([toDownloadText(file.content)], { type: mimeFor(file.basename) });
        triggerDownload(blob, file.basename);
        return recordHistory({
          filename: file.basename,
          format: file.kind,
          title: file.filename,
          size: blob.size,
          preview: file.content,
        });
      }),
    [run]
  );

  /**
   * Télécharge plusieurs fichiers détectés dans une archive ZIP (arborescence conservée).
   * @param {object[]} files — fichiers issus de utils/codeBlocks
   * @param {string} [title] — nom de l'archive (sans extension)
   */
  const exportFilesZip = useCallback(
    (files, title = 'export') =>
      run(async () => {
        if (!files?.length) throw new Error('Aucun fichier à exporter.');
        const blob = await buildZipBlob(files);
        const filename = `${safeName(title)}.zip`;
        triggerDownload(blob, filename);
        return recordHistory({
          filename,
          format: 'zip',
          title: `${filename} (${files.length} fichiers)`,
          size: blob.size,
          preview: files.map((f) => f.filename).join('\n'),
        });
      }),
    [run]
  );

  const getHistory = useCallback(() => loadHistory(), []);

  const clearHistory = useCallback(() => {
    localStorage.removeItem(HISTORY_KEY);
  }, []);

  return { exportContent, exportFile, exportFilesZip, exporting, exportError, getHistory, clearHistory };
}
