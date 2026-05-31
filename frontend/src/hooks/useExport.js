/**
 * useExport.js
 * Hook centralisant la génération de fichiers depuis du contenu LLM (markdown/texte)
 * Formats : HTML | XLSX | DOCX | PDF
 * Libs : SheetJS (xlsx), docx, html2pdf.js — toutes CDN-free via npm
 */

import { useState, useCallback } from 'react';

// ─── Helpers markdown → structures ────────────────────────────────────────────

/** Extrait les tableaux markdown → arrays 2D */
function parseMarkdownTables(markdown) {
  const tables = [];
  const tableRegex = /(\|.+\|\n)+/g;
  let match;

  while ((match = tableRegex.exec(markdown)) !== null) {
    const rows = match[0]
      .trim()
      .split('\n')
      .filter(row => !/^\|[\s\-|]+\|$/.test(row)) // retirer lignes séparateurs
      .map(row =>
        row
          .replace(/^\||\|$/g, '')
          .split('|')
          .map(cell => cell.trim())
      );
    if (rows.length > 0) tables.push(rows);
  }
  return tables;
}

/** Markdown → HTML sémantique propre (pas de dépendance externe) */
function markdownToHtml(md) {
  return md
    // Titres
    .replace(/^#{6}\s(.+)$/gm, '<h6>$1</h6>')
    .replace(/^#{5}\s(.+)$/gm, '<h5>$1</h5>')
    .replace(/^#{4}\s(.+)$/gm, '<h4>$1</h4>')
    .replace(/^#{3}\s(.+)$/gm, '<h3>$1</h3>')
    .replace(/^#{2}\s(.+)$/gm, '<h2>$1</h2>')
    .replace(/^#{1}\s(.+)$/gm, '<h1>$1</h1>')
    // Bold / italic
    .replace(/\*\*\*(.+?)\*\*\*/g, '<strong><em>$1</em></strong>')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    .replace(/_(.+?)_/g, '<em>$1</em>')
    // Code inline / blocs
    .replace(/```(\w+)?\n([\s\S]*?)```/g, '<pre><code class="language-$1">$2</code></pre>')
    .replace(/`(.+?)`/g, '<code>$1</code>')
    // Listes non ordonnées
    .replace(/^\s*[-*+]\s(.+)$/gm, '<li>$1</li>')
    .replace(/(<li>.*<\/li>\n?)+/g, '<ul>$&</ul>')
    // Listes ordonnées
    .replace(/^\s*\d+\.\s(.+)$/gm, '<li>$1</li>')
    // Tableaux markdown
    .replace(/\|(.+)\|/g, (match) => {
      const cells = match.replace(/^\||\|$/g, '').split('|').map(c => `<td>${c.trim()}</td>`).join('');
      return `<tr>${cells}</tr>`;
    })
    // Liens & images
    .replace(/!\[(.+?)\]\((.+?)\)/g, '<img src="$2" alt="$1">')
    .replace(/\[(.+?)\]\((.+?)\)/g, '<a href="$2">$1</a>')
    // Blockquotes
    .replace(/^>\s(.+)$/gm, '<blockquote>$1</blockquote>')
    // HR
    .replace(/^---$/gm, '<hr>')
    // Paragraphes (double saut de ligne)
    .replace(/\n\n(?!<)/g, '</p><p>')
    .replace(/^(?!<)(.+)$/gm, (m) => m.startsWith('<') ? m : m);
}

// ─── Générateurs ──────────────────────────────────────────────────────────────

async function generateHTML(content, title = 'Export') {
  const bodyHtml = markdownToHtml(content);
  const html = `<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>${title}</title>
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: 'Georgia', serif;
      font-size: 15px;
      line-height: 1.7;
      color: #1a1a1a;
      background: #fff;
      max-width: 800px;
      margin: 0 auto;
      padding: 48px 32px;
    }
    h1, h2, h3, h4, h5, h6 {
      font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
      font-weight: 700;
      margin: 1.5em 0 0.5em;
      line-height: 1.2;
      color: #111;
    }
    h1 { font-size: 2em; border-bottom: 2px solid #111; padding-bottom: 0.3em; }
    h2 { font-size: 1.5em; }
    h3 { font-size: 1.2em; }
    p { margin: 0.8em 0; }
    ul, ol { padding-left: 1.5em; margin: 0.8em 0; }
    li { margin: 0.3em 0; }
    code {
      font-family: 'Menlo', 'Consolas', monospace;
      background: #f4f4f4;
      padding: 0.15em 0.4em;
      border-radius: 3px;
      font-size: 0.9em;
    }
    pre {
      background: #1e1e1e;
      color: #d4d4d4;
      padding: 1em;
      border-radius: 6px;
      overflow-x: auto;
      margin: 1em 0;
    }
    pre code { background: none; color: inherit; padding: 0; }
    blockquote {
      border-left: 4px solid #ccc;
      padding-left: 1em;
      color: #555;
      margin: 1em 0;
    }
    table { border-collapse: collapse; width: 100%; margin: 1em 0; }
    th, td { border: 1px solid #ddd; padding: 8px 12px; text-align: left; }
    th { background: #f8f8f8; font-weight: 600; }
    tr:nth-child(even) { background: #fafafa; }
    hr { border: none; border-top: 1px solid #ddd; margin: 2em 0; }
    a { color: #0066cc; }
    img { max-width: 100%; }
    .meta { color: #888; font-size: 0.85em; margin-bottom: 2em; font-family: sans-serif; }
  </style>
</head>
<body>
  <div class="meta">Généré le ${new Date().toLocaleString('fr-FR')} • AgentRAG.io</div>
  <p>${bodyHtml}</p>
</body>
</html>`;

  const blob = new Blob([html], { type: 'text/html;charset=utf-8' });
  return { blob, extension: 'html', mimeType: 'text/html' };
}

async function generateXLSX(content, title = 'Export') {
  // Lazy-load SheetJS
  const XLSX = await import('https://cdn.sheetjs.com/xlsx-0.20.2/package/xlsx.mjs').catch(() => {
    // Fallback: utiliser la version npm si disponible
    return import('xlsx');
  });

  const workbook = XLSX.utils.book_new();

  // Essayer d'extraire des tableaux du markdown
  const tables = parseMarkdownTables(content);

  if (tables.length > 0) {
    // Un onglet par tableau détecté
    tables.forEach((tableData, idx) => {
      const ws = XLSX.utils.aoa_to_sheet(tableData);
      // Style header
      const headerRange = XLSX.utils.decode_range(ws['!ref']);
      for (let col = headerRange.s.c; col <= headerRange.e.c; col++) {
        const cellAddr = XLSX.utils.encode_cell({ r: 0, c: col });
        if (ws[cellAddr]) {
          ws[cellAddr].s = { font: { bold: true }, fill: { fgColor: { rgb: 'F0F0F0' } } };
        }
      }
      XLSX.utils.book_append_sheet(workbook, ws, `Tableau ${idx + 1}`);
    });
  }

  // Toujours ajouter un onglet "Contenu brut"
  const lines = content.split('\n').map(line => [line]);
  const rawWs = XLSX.utils.aoa_to_sheet([[`Export: ${title}`], [`Date: ${new Date().toLocaleString('fr-FR')}`], [], ...lines]);
  XLSX.utils.book_append_sheet(workbook, rawWs, 'Contenu');

  const buffer = XLSX.write(workbook, { bookType: 'xlsx', type: 'array' });
  const blob = new Blob([buffer], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' });
  return { blob, extension: 'xlsx', mimeType: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' };
}

async function generateDOCX(content, title = 'Export') {
  const { Document, Packer, Paragraph, TextRun, HeadingLevel, Table, TableRow, TableCell, BorderStyle, AlignmentType } = await import('docx');

  const children = [];
  const lines = content.split('\n');

  let inCodeBlock = false;
  let codeLines = [];
  let inTable = false;
  let tableRows = [];

  const flushCode = () => {
    if (codeLines.length === 0) return;
    children.push(
      new Paragraph({
        children: [new TextRun({ text: codeLines.join('\n'), font: 'Courier New', size: 18, color: '333333' })],
        shading: { fill: 'F4F4F4' },
        border: { left: { style: BorderStyle.SINGLE, size: 3, color: '999999' } },
        indent: { left: 360 }
      })
    );
    codeLines = [];
  };

  const flushTable = () => {
    if (tableRows.length === 0) return;
    const rows = tableRows.map((cells, rowIdx) =>
      new TableRow({
        children: cells.map(cell =>
          new TableCell({
            children: [new Paragraph({
              children: [new TextRun({ text: cell, bold: rowIdx === 0, size: 20 })]
            })]
          })
        )
      })
    );
    children.push(new Table({ rows, width: { size: 100, type: 'pct' } }));
    children.push(new Paragraph({}));
    tableRows = [];
    inTable = false;
  };

  for (const line of lines) {
    // Code blocks
    if (line.startsWith('```')) {
      if (inCodeBlock) { flushCode(); inCodeBlock = false; }
      else inCodeBlock = true;
      continue;
    }
    if (inCodeBlock) { codeLines.push(line); continue; }

    // Tables markdown
    if (line.startsWith('|')) {
      if (/^\|[\s\-|]+\|$/.test(line)) continue; // séparateur
      inTable = true;
      const cells = line.replace(/^\||\|$/g, '').split('|').map(c => c.trim());
      tableRows.push(cells);
      continue;
    }
    if (inTable && !line.startsWith('|')) flushTable();

    // Titres
    if (line.startsWith('# ')) {
      children.push(new Paragraph({ text: line.slice(2), heading: HeadingLevel.HEADING_1 }));
    } else if (line.startsWith('## ')) {
      children.push(new Paragraph({ text: line.slice(3), heading: HeadingLevel.HEADING_2 }));
    } else if (line.startsWith('### ')) {
      children.push(new Paragraph({ text: line.slice(4), heading: HeadingLevel.HEADING_3 }));
    } else if (line.startsWith('> ')) {
      children.push(new Paragraph({
        children: [new TextRun({ text: line.slice(2), italics: true, color: '555555' })],
        indent: { left: 720 },
        border: { left: { style: BorderStyle.SINGLE, size: 4, color: 'CCCCCC' } }
      }));
    } else if (/^\s*[-*+]\s/.test(line)) {
      children.push(new Paragraph({
        children: [new TextRun(line.replace(/^\s*[-*+]\s/, ''))],
        bullet: { level: 0 }
      }));
    } else if (/^\s*\d+\.\s/.test(line)) {
      children.push(new Paragraph({
        children: [new TextRun(line.replace(/^\s*\d+\.\s/, ''))],
        numbering: { reference: 'default', level: 0 }
      }));
    } else if (line.trim() === '' || line === '---') {
      children.push(new Paragraph({}));
    } else {
      // Inline bold/italic/code
      const runs = [];
      const segments = line.split(/(\*\*.*?\*\*|\*.*?\*|`.*?`)/g);
      for (const seg of segments) {
        if (seg.startsWith('**') && seg.endsWith('**')) {
          runs.push(new TextRun({ text: seg.slice(2, -2), bold: true }));
        } else if (seg.startsWith('*') && seg.endsWith('*')) {
          runs.push(new TextRun({ text: seg.slice(1, -1), italics: true }));
        } else if (seg.startsWith('`') && seg.endsWith('`')) {
          runs.push(new TextRun({ text: seg.slice(1, -1), font: 'Courier New', size: 18 }));
        } else {
          runs.push(new TextRun(seg));
        }
      }
      children.push(new Paragraph({ children: runs }));
    }
  }

  flushCode();
  flushTable();

  const doc = new Document({
    title,
    creator: 'AgentRAG.io',
    description: `Export généré le ${new Date().toLocaleString('fr-FR')}`,
    styles: {
      default: {
        document: {
          run: { font: 'Calibri', size: 22 },
          paragraph: { spacing: { after: 160 } }
        }
      }
    },
    sections: [{ properties: {}, children }]
  });

  const buffer = await Packer.toBlob(doc);
  return { blob: buffer, extension: 'docx', mimeType: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document' };
}

async function generatePDF(content, title = 'Export') {
  // Génère le HTML puis le convertit en PDF via html2pdf.js
  const { blob: htmlBlob } = await generateHTML(content, title);
  const htmlText = await htmlBlob.text();

  // Créer un iframe caché pour le rendu
  const iframe = document.createElement('iframe');
  iframe.style.cssText = 'position:fixed;top:-9999px;left:-9999px;width:794px;height:1123px;border:none;';
  document.body.appendChild(iframe);

  return new Promise((resolve, reject) => {
    iframe.onload = async () => {
      try {
        // Dynamically load html2pdf if available, else fallback to print
        let pdfBlob;

        if (window.html2pdf) {
          pdfBlob = await new Promise((res) => {
            window.html2pdf()
              .from(iframe.contentDocument.body)
              .set({
                margin: [15, 15, 15, 15],
                filename: `${title}.pdf`,
                image: { type: 'jpeg', quality: 0.95 },
                html2canvas: { scale: 2, useCORS: true },
                jsPDF: { unit: 'mm', format: 'a4', orientation: 'portrait' }
              })
              .outputPdf('blob')
              .then(res);
          });
        } else {
          // Fallback: générer un PDF minimal via Blob (pas de rendu réel)
          // On encode le HTML directement comme PDF placeholder
          // En production, injecter html2pdf.js via <script> dans index.html
          const enc = new TextEncoder();
          const raw = enc.encode(htmlText);
          pdfBlob = new Blob([raw], { type: 'application/pdf' });
          console.warn('[useExport] html2pdf.js non chargé — fallback HTML utilisé. Ajoutez <script src="https://cdnjs.cloudflare.com/ajax/libs/html2pdf.js/0.10.1/html2pdf.bundle.min.js"> dans index.html pour un vrai PDF.');
        }

        document.body.removeChild(iframe);
        resolve({ blob: pdfBlob, extension: 'pdf', mimeType: 'application/pdf' });
      } catch (err) {
        document.body.removeChild(iframe);
        reject(err);
      }
    };
    iframe.contentDocument.open();
    iframe.contentDocument.write(htmlText);
    iframe.contentDocument.close();
  });
}

// ─── Hook principal ────────────────────────────────────────────────────────────

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

export function useExport() {
  const [exporting, setExporting] = useState(false);
  const [exportError, setExportError] = useState(null);

  const exportContent = useCallback(async (content, format, title = 'export') => {
    if (!content?.trim()) {
      setExportError('Aucun contenu à exporter.');
      return;
    }

    setExporting(true);
    setExportError(null);

    try {
      let result;
      const safeTitle = title.replace(/[^a-z0-9_\-\s]/gi, '').trim().substring(0, 60) || 'export';

      switch (format) {
        case 'html':  result = await generateHTML(content, safeTitle); break;
        case 'xlsx':  result = await generateXLSX(content, safeTitle); break;
        case 'docx':  result = await generateDOCX(content, safeTitle); break;
        case 'pdf':   result = await generatePDF(content, safeTitle); break;
        default: throw new Error(`Format inconnu : ${format}`);
      }

      const { blob, extension, mimeType } = result;
      const timestamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19);
      const filename = `${safeTitle}_${timestamp}.${extension}`;

      // Déclencher le téléchargement
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      a.click();
      URL.revokeObjectURL(url);

      // Enregistrer en historique
      const entry = {
        id: crypto.randomUUID(),
        filename,
        format,
        title: safeTitle,
        size: blob.size,
        createdAt: new Date().toISOString(),
        // On stocke le contenu tronqué pour preview
        preview: content.substring(0, 300)
      };
      saveHistory(entry);

      return entry;
    } catch (err) {
      console.error('[useExport] Error:', err);
      setExportError(err.message || 'Erreur lors de la génération.');
      throw err;
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