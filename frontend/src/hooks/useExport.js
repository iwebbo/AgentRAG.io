/**
 * useExport.js
 * Hook centralisant l'export de contenu LLM via le backend AgentRAG.
 * Formats : PDF | DOCX | XLSX | HTML | MD
 *
 * Interface publique inchangée — compatible ExportButton.jsx & ExportHistory.jsx :
 *   exportContent(content, format, title)
 *   getHistory()
 *   clearHistory()
 *   exporting {boolean}
 *   exportError {string|null}
 */

import { useState, useCallback } from 'react';
import api from '../services/api';

// ─── Historique local (inchangé — ExportHistory en dépend) ────────────────────

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
  const history = loadHistory();
  history.unshift(entry);
  localStorage.setItem(HISTORY_KEY, JSON.stringify(history.slice(0, MAX_HISTORY)));
}

// ─── Hook ─────────────────────────────────────────────────────────────────────

export function useExport() {
  const [exporting, setExporting] = useState(false);
  const [exportError, setExportError] = useState(null);

  /**
   * Exporte du contenu Markdown via le backend et déclenche le téléchargement.
   *
   * @param {string} content  — Contenu Markdown du message LLM
   * @param {string} format   — 'pdf' | 'docx' | 'xlsx' | 'html' | 'md'
   * @param {string} [title]  — Titre du document (défaut : 'export')
   * @returns {object}        — Entry d'historique { id, filename, format, ... }
   */
  const exportContent = useCallback(async (content, format, title = 'export') => {
    if (!content?.trim()) {
      setExportError('Aucun contenu à exporter.');
      return;
    }

    setExporting(true);
    setExportError(null);

    try {
      const safeTitle = title.replace(/[<>:"/\\|?*\x00-\x1f]/g, '_').trim().substring(0, 80) || 'export';

      // ── Appel backend ──────────────────────────────────────────────────────
      const response = await api.post(
        `/api/export/${format}`,
        { content, title: safeTitle },
        { responseType: 'blob' }
      );

      // ── Résolution du nom de fichier (Content-Disposition RFC 5987) ────────
      const disposition = response.headers?.['content-disposition'] || '';
      let filename = `${safeTitle}.${format}`;

      const utf8Match = disposition.match(/filename\*=UTF-8''([^\s;]+)/i);
      const asciiMatch = disposition.match(/filename="?([^";\n]+)"?/i);

      if (utf8Match) {
        filename = decodeURIComponent(utf8Match[1]);
      } else if (asciiMatch) {
        filename = asciiMatch[1].trim();
      }

      // ── Téléchargement navigateur ──────────────────────────────────────────
      const url = URL.createObjectURL(response.data);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);

      // ── Historique local ───────────────────────────────────────────────────
      const entry = {
        id: crypto.randomUUID(),
        filename,
        format,
        title: safeTitle,
        size: response.data.size,
        createdAt: new Date().toISOString(),
        preview: content.substring(0, 300),
      };
      saveHistory(entry);

      return entry;

    } catch (err) {
      // Les erreurs backend arrivent comme des blobs (responseType: 'blob')
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

      console.error('[useExport]', message, err);
      setExportError(message);
      throw new Error(message);
    } finally {
      setExporting(false);
    }
  }, []);

  const getHistory = useCallback(() => loadHistory(), []);

  const clearHistory = useCallback(() => {
    localStorage.removeItem(HISTORY_KEY);
  }, []);

  return { exportContent, exporting, exportError, getHistory, clearHistory };
}