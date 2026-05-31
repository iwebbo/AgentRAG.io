/**
 * ExportButton.jsx
 * Bouton dropdown pour exporter le contenu d'un message LLM
 * Props:
 *   content  {string}  — contenu markdown du message
 *   title    {string}  — titre suggéré (ex: 5 premiers mots du message)
 *   compact  {boolean} — mode icône seule (pour les bulles de messages)
 */

import { useState, useRef, useEffect } from 'react';
import { Download, FileText, FileSpreadsheet, Globe, File, Loader2, ChevronDown } from 'lucide-react';
import { useExport } from '../../hooks/useExport';

const FORMATS = [
  {
    id: 'html',
    label: 'HTML',
    description: 'Page web standalone',
    icon: Globe,
    color: '#e44d26',
    bg: '#fff3f0'
  },
  {
    id: 'xlsx',
    label: 'Excel',
    description: 'Tableur (.xlsx)',
    icon: FileSpreadsheet,
    color: '#1d6f42',
    bg: '#f0fff4'
  },
  {
    id: 'docx',
    label: 'Word',
    description: 'Document Word (.docx)',
    icon: FileText,
    color: '#2b579a',
    bg: '#f0f4ff'
  },
  {
    id: 'pdf',
    label: 'PDF',
    description: 'Document PDF',
    icon: File,
    color: '#cc0000',
    bg: '#fff0f0'
  }
];

export default function ExportButton({ content, title, compact = false }) {
  const [open, setOpen] = useState(false);
  const [activeFormat, setActiveFormat] = useState(null);
  const [success, setSuccess] = useState(null);
  const dropdownRef = useRef(null);
  const { exportContent, exporting, exportError } = useExport();

  // Fermer en cliquant dehors
  useEffect(() => {
    if (!open) return;
    const handler = (e) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target)) {
        setOpen(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [open]);

  const handleExport = async (format) => {
    setActiveFormat(format);
    try {
      const suggestedTitle = title || content.trim().split(/\s+/).slice(0, 6).join(' ');
      await exportContent(content, format, suggestedTitle);
      setSuccess(format);
      setTimeout(() => { setSuccess(null); setOpen(false); }, 1200);
    } catch {
      // exportError already set in hook
    } finally {
      setActiveFormat(null);
    }
  };

  const isLoading = exporting && activeFormat !== null;

  return (
    <div ref={dropdownRef} style={{ position: 'relative', display: 'inline-block' }}>
      {/* Trigger */}
      <button
        onClick={() => setOpen(o => !o)}
        disabled={isLoading}
        title="Exporter ce message"
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '4px',
          padding: compact ? '3px 6px' : '3px 8px',
          fontSize: 'var(--text-xs)',
          color: open ? 'var(--primary)' : 'var(--gray-500)',
          background: open ? 'var(--primary-light, #eff6ff)' : 'var(--gray-100)',
          border: `1px solid ${open ? 'var(--primary)' : 'var(--gray-200)'}`,
          borderRadius: 'var(--radius-sm)',
          cursor: isLoading ? 'wait' : 'pointer',
          transition: 'all 0.15s ease',
          opacity: isLoading ? 0.7 : 1,
          fontWeight: open ? '600' : '400'
        }}
      >
        {isLoading
          ? <Loader2 size={12} style={{ animation: 'spin 1s linear infinite' }} />
          : <Download size={12} />
        }
        {!compact && (
          <>
            {isLoading ? 'Export...' : 'Exporter'}
            <ChevronDown size={10} style={{ transform: open ? 'rotate(180deg)' : 'rotate(0)', transition: 'transform 0.2s' }} />
          </>
        )}
      </button>

      {/* Dropdown */}
      {open && (
        <div style={{
          position: 'absolute',
          bottom: 'calc(100% + 6px)',
          left: 0,
          zIndex: 200,
          background: 'white',
          border: '1px solid var(--gray-200)',
          borderRadius: '10px',
          boxShadow: '0 8px 24px rgba(0,0,0,0.12), 0 2px 6px rgba(0,0,0,0.06)',
          minWidth: '220px',
          overflow: 'hidden',
          animation: 'exportDropdownIn 0.18s ease'
        }}>
          <div style={{
            padding: '10px 14px 6px',
            fontSize: '10px',
            fontWeight: '700',
            letterSpacing: '0.08em',
            textTransform: 'uppercase',
            color: 'var(--gray-400)',
            borderBottom: '1px solid var(--gray-100)'
          }}>
            Choisir le format
          </div>

          {FORMATS.map(fmt => {
            const Icon = fmt.icon;
            const isThis = activeFormat === fmt.id;
            const isDone = success === fmt.id;

            return (
              <button
                key={fmt.id}
                onClick={() => !isLoading && handleExport(fmt.id)}
                disabled={isLoading}
                style={{
                  width: '100%',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '10px',
                  padding: '9px 14px',
                  background: isDone ? fmt.bg : 'white',
                  border: 'none',
                  cursor: isLoading ? 'wait' : 'pointer',
                  transition: 'background 0.15s',
                  textAlign: 'left'
                }}
                onMouseEnter={e => { if (!isLoading && !isDone) e.currentTarget.style.background = fmt.bg; }}
                onMouseLeave={e => { if (!isDone) e.currentTarget.style.background = 'white'; }}
              >
                <div style={{
                  width: 32,
                  height: 32,
                  borderRadius: '8px',
                  background: fmt.bg,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  flexShrink: 0
                }}>
                  {isThis
                    ? <Loader2 size={15} color={fmt.color} style={{ animation: 'spin 1s linear infinite' }} />
                    : isDone
                      ? <span style={{ color: '#22c55e', fontSize: 14 }}>✓</span>
                      : <Icon size={15} color={fmt.color} />
                  }
                </div>
                <div>
                  <div style={{ fontSize: '13px', fontWeight: '600', color: '#111', lineHeight: 1.2 }}>
                    {fmt.label}
                    {isDone && <span style={{ color: '#22c55e', marginLeft: 4, fontWeight: 400 }}>Téléchargé !</span>}
                  </div>
                  <div style={{ fontSize: '11px', color: 'var(--gray-500)', marginTop: 1 }}>{fmt.description}</div>
                </div>
              </button>
            );
          })}

          {exportError && (
            <div style={{
              padding: '8px 14px',
              fontSize: '11px',
              color: '#cc0000',
              background: '#fff0f0',
              borderTop: '1px solid #ffe0e0'
            }}>
              ⚠ {exportError}
            </div>
          )}
        </div>
      )}

      <style>{`
        @keyframes exportDropdownIn {
          from { opacity: 0; transform: translateY(6px) scale(0.97); }
          to   { opacity: 1; transform: translateY(0) scale(1); }
        }
        @keyframes spin {
          from { transform: rotate(0deg); }
          to   { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  );
}