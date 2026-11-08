import { DOC_ENTRIES } from '../docs/docEntries';

// ─────────────────────────────────────────────────────────────────────────────
// DOCUMENTATION TAB
// ─────────────────────────────────────────────────────────────────────────────
const DocumentationTab = () => (
  <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-5)' }}>
    {DOC_ENTRIES.map(entry => (
      <div key={entry.key} style={{ border: '1px solid var(--gray-300)', borderRadius: 'var(--radius-md)', overflow: 'hidden' }}>
        <div style={{ padding: 'var(--spacing-4)', backgroundColor: 'var(--gray-100)', borderBottom: '1px solid var(--gray-300)' }}>
          <h3 style={{ fontWeight: '600', fontSize: 'var(--text-base)', display: 'flex', alignItems: 'center', gap: 'var(--spacing-2)' }}>
            <span>{entry.icon}</span> {entry.title}
            {entry.static && (
              <span style={{ fontSize: '10px', fontWeight: '600', padding: '2px 8px', borderRadius: '99px', background: 'rgba(251,191,36,.15)', color: 'var(--warning-dark)' }}>
                static — no DB source
              </span>
            )}
          </h3>
          <p style={{ fontSize: 'var(--text-sm)', color: 'var(--gray-700)', marginTop: 'var(--spacing-1)', lineHeight: '1.6' }}>{entry.desc}</p>
        </div>

        {entry.steps && (
          <div style={{ padding: 'var(--spacing-4)', display: 'flex', flexDirection: 'column', gap: 'var(--spacing-3)' }}>
            {entry.steps.map(step => (
              <div key={step.n} style={{ display: 'flex', gap: 'var(--spacing-3)', alignItems: 'flex-start' }}>
                <span style={{ minWidth: '22px', height: '22px', borderRadius: '50%', background: 'var(--gray-200)', border: '1px solid var(--gray-400)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 'var(--text-xs)', fontWeight: '600', color: 'var(--gray-800)', flexShrink: 0 }}>{step.n}</span>
                <p style={{ fontSize: 'var(--text-sm)', color: 'var(--gray-800)', lineHeight: '1.6' }}>{step.text}</p>
              </div>
            ))}
          </div>
        )}

        {entry.examples && (
          <div style={{ padding: 'var(--spacing-4)', display: 'flex', flexDirection: 'column', gap: 'var(--spacing-4)' }}>
            {entry.examples.map(ex => (
              <div key={ex.key}>
                <div style={{ fontSize: 'var(--text-xs)', fontWeight: '600', color: 'var(--gray-600)', marginBottom: 'var(--spacing-2)', fontFamily: 'monospace' }}>
                  {ex.filename}
                </div>
                <pre style={{ margin: 0, padding: 'var(--spacing-3)', background: 'var(--bg-main)', color: 'var(--text-primary)', borderRadius: 'var(--radius)', fontSize: '11px', lineHeight: '1.6', overflowX: 'auto', whiteSpace: 'pre' }}>
                  <code>{ex.content}</code>
                </pre>
              </div>
            ))}
            {entry.curl && (
              <div>
                <div style={{ fontSize: 'var(--text-xs)', fontWeight: '600', color: 'var(--gray-600)', marginBottom: 'var(--spacing-2)' }}>
                  Register via API
                </div>
                <pre style={{ margin: 0, padding: 'var(--spacing-3)', background: 'var(--bg-main)', color: '#86efac', borderRadius: 'var(--radius)', fontSize: '11px', lineHeight: '1.6', overflowX: 'auto', whiteSpace: 'pre' }}>
                  <code>{entry.curl}</code>
                </pre>
              </div>
            )}
          </div>
        )}

        {entry.table && (
          <div style={{ padding: 'var(--spacing-4)', overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 'var(--text-sm)' }}>
              <thead>
                <tr style={{ borderBottom: '1px solid var(--gray-300)' }}>
                  {entry.columns.map(h => (
                    <th key={h} style={{ textAlign: 'left', padding: 'var(--spacing-2) var(--spacing-3)', color: 'var(--gray-600)', fontWeight: '600', fontSize: 'var(--text-xs)', textTransform: 'uppercase', letterSpacing: '.05em' }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {entry.table.map((row, i) => (
                  <tr key={row.key} style={{ borderBottom: i < entry.table.length - 1 ? '1px solid var(--gray-200)' : 'none' }}>
                    {entry.key === 'reference' ? (
                      <>
                        <td style={{ padding: 'var(--spacing-2) var(--spacing-3)', fontFamily: 'monospace', fontSize: 'var(--text-xs)', color: 'var(--gray-800)' }}>{row.key}</td>
                        <td style={{ padding: 'var(--spacing-2) var(--spacing-3)', fontWeight: '500' }}>{row.name}</td>
                        <td style={{ padding: 'var(--spacing-2) var(--spacing-3)' }}>
                          <span style={{ fontSize: '10px', fontWeight: '600', padding: '2px 8px', borderRadius: '99px', background: row.badge === 'skill' ? 'rgba(34,197,94,.15)' : 'rgba(96,165,250,.15)', color: row.badge === 'skill' ? 'var(--success-dark)' : 'var(--primary-dark)' }}>{row.badge}</span>
                        </td>
                        <td style={{ padding: 'var(--spacing-2) var(--spacing-3)', color: 'var(--gray-700)', fontSize: 'var(--text-xs)' }}>{row.mcp}</td>
                      </>
                    ) : (
                      <>
                        <td style={{ padding: 'var(--spacing-2) var(--spacing-3)', fontFamily: 'monospace', fontSize: 'var(--text-xs)', color: 'var(--gray-800)', fontWeight: '600' }}>{row.key}</td>
                        <td style={{ padding: 'var(--spacing-2) var(--spacing-3)' }}>
                          <span style={{ fontSize: '10px', fontWeight: '600', padding: '1px 7px', borderRadius: '99px', background: row.transport === 'HTTP' ? 'rgba(96,165,250,.15)' : 'rgba(139,92,246,.15)', color: row.transport === 'HTTP' ? 'var(--primary-dark)' : '#6d28d9' }}>{row.transport}</span>
                        </td>
                        <td style={{ padding: 'var(--spacing-2) var(--spacing-3)', color: 'var(--gray-700)', fontSize: 'var(--text-xs)', fontFamily: 'monospace' }}>{row.credential}</td>
                        <td style={{ padding: 'var(--spacing-2) var(--spacing-3)', color: 'var(--gray-700)', fontSize: 'var(--text-xs)' }}>{row.tools}</td>
                      </>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    ))}
  </div>
);

export default DocumentationTab;
