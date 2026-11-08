import { useState } from 'react';
import Button from '../../../components/common/Button';
import Alert from '../../../components/common/Alert';
import api from '../../../services/api';

// ─────────────────────────────────────────────────────────────────────────────
// REGISTER SKILL MODAL
// ─────────────────────────────────────────────────────────────────────────────
const RegisterSkillModal = ({ onClose, onSuccess, providers }) => {
  const [mode, setMode] = useState('file');
  const [mdFile, setMdFile] = useState(null);
  const [mdContent, setMdContent] = useState('');
  const [autoCreate, setAutoCreate] = useState(true);
  const [llmProvider, setLlmProvider] = useState(providers[0]?.name || 'lmstudio');
  const [llmModel, setLlmModel] = useState('openai/gpt-oss-20b');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);

  const handleSubmit = async () => {
    setError(null);
    if (mode === 'file' && !mdFile) { setError('Select a .md file'); return; }
    if (mode === 'paste' && !mdContent.trim()) { setError('Paste your .md content'); return; }
    const formData = new FormData();
    if (mode === 'file') formData.append('file', mdFile);
    else formData.append('md_content', mdContent);
    formData.append('auto_create_agent', autoCreate ? 'true' : 'false');
    if (autoCreate) { formData.append('llm_provider', llmProvider); formData.append('llm_model', llmModel); }
    setLoading(true);
    try {
      const res = await api.post('/api/skills/register', formData, { headers: { 'Content-Type': 'multipart/form-data' } });
      setResult(res.data);
    } catch (err) {
      setError(err.response?.data?.detail || 'Registration failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ position: 'fixed', inset: 0, backgroundColor: 'var(--overlay)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000, padding: 'var(--spacing-4)' }}>
      <div className="card" style={{ width: '100%', maxWidth: '620px', maxHeight: '90vh', overflow: 'auto' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 'var(--spacing-4)' }}>
          <div>
            <h2 style={{ fontSize: 'var(--text-xl)', fontWeight: '600' }}>Register skill</h2>
            <p style={{ fontSize: 'var(--text-sm)', color: 'var(--gray-600)', marginTop: '2px' }}>Upload a <code style={{ fontSize: '11px', background: 'var(--gray-200)', padding: '0 3px', borderRadius: '3px' }}>.md</code> skill file</p>
          </div>
          <button onClick={onClose} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--gray-600)', fontSize: '1.25rem' }}>✕</button>
        </div>

        {!result ? (
          <>
            {error && <Alert type="error" style={{ marginBottom: 'var(--spacing-4)' }} onClose={() => setError(null)}>{error}</Alert>}
            <div style={{ display: 'flex', gap: 'var(--spacing-2)', marginBottom: 'var(--spacing-4)' }}>
              {[{ k: 'file', l: '📎 Upload file' }, { k: 'paste', l: 'Paste content' }].map(({ k, l }) => (
                <button key={k} onClick={() => setMode(k)} style={{ padding: 'var(--spacing-2) var(--spacing-4)', borderRadius: 'var(--radius)', border: mode === k ? '1px solid var(--primary)' : '1px solid var(--gray-300)', background: mode === k ? 'rgba(96,165,250,.1)' : 'var(--gray-100)', color: mode === k ? 'var(--primary)' : 'var(--gray-700)', fontWeight: mode === k ? '600' : '400', cursor: 'pointer', fontSize: 'var(--text-sm)' }}>{l}</button>
              ))}
            </div>
            {mode === 'file' && (
              <div className="form-group" style={{ marginBottom: 'var(--spacing-4)' }}>
                <label className="form-label">.md skill file *</label>
                <input type="file" accept=".md,text/markdown" className="form-input" onChange={e => setMdFile(e.target.files[0])} style={{ padding: 'var(--spacing-2)' }} />
                {mdFile && <p style={{ fontSize: 'var(--text-xs)', color: 'var(--gray-600)', marginTop: '4px' }}>Selected: <strong>{mdFile.name}</strong> ({(mdFile.size / 1024).toFixed(1)} KB)</p>}
              </div>
            )}
            {mode === 'paste' && (
              <div className="form-group" style={{ marginBottom: 'var(--spacing-4)' }}>
                <label className="form-label">.md content *</label>
                <textarea className="form-input" rows={12} value={mdContent} onChange={e => setMdContent(e.target.value)} placeholder={'---\nskill_id: my_skill\n...\n---\n## Mapping\n- disk  → df -h'} style={{ fontFamily: 'var(--font-mono)', fontSize: '12px' }} />
              </div>
            )}
            <div style={{ padding: 'var(--spacing-4)', backgroundColor: 'var(--gray-100)', borderRadius: 'var(--radius)', marginBottom: 'var(--spacing-4)' }}>
              <label style={{ display: 'flex', alignItems: 'center', gap: 'var(--spacing-2)', cursor: 'pointer', marginBottom: 'var(--spacing-3)' }}>
                <input type="checkbox" checked={autoCreate} onChange={e => setAutoCreate(e.target.checked)} />
                <span style={{ fontWeight: '600', fontSize: 'var(--text-sm)' }}>Auto-create agent</span>
                <span style={{ fontSize: 'var(--text-xs)', color: 'var(--gray-600)' }}>(creates skill + agent in one call)</span>
              </label>
              {autoCreate && (
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--spacing-3)' }}>
                  <div className="form-group"><label className="form-label">LLM provider</label><select className="form-input" value={llmProvider} onChange={e => setLlmProvider(e.target.value)}>{providers.map(p => <option key={p.name} value={p.name}>{p.name}</option>)}</select></div>
                  <div className="form-group"><label className="form-label">LLM model</label><input type="text" className="form-input" value={llmModel} onChange={e => setLlmModel(e.target.value)} /></div>
                </div>
              )}
            </div>
            <div style={{ display: 'flex', gap: 'var(--spacing-3)', justifyContent: 'flex-end', paddingTop: 'var(--spacing-4)', borderTop: '1px solid var(--gray-200)' }}>
              <Button variant="ghost" onClick={onClose} disabled={loading}>Cancel</Button>
              <Button variant="primary" onClick={handleSubmit} disabled={loading}>{loading ? 'Registering…' : '⬆ Register skill'}</Button>
            </div>
          </>
        ) : (
          <div>
            <div style={{ padding: 'var(--spacing-4)', border: '1px solid var(--success)', borderLeft: '3px solid var(--success)', borderRadius: 'var(--radius)', backgroundColor: 'rgba(52,211,153,.08)', marginBottom: 'var(--spacing-4)' }}>
              <p style={{ fontWeight: '600', color: 'var(--success-dark)', marginBottom: 'var(--spacing-2)' }}>✓ Skill registered successfully</p>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--spacing-2)', fontSize: 'var(--text-sm)' }}>
                <div><span style={{ color: 'var(--gray-600)' }}>skill_id</span><br /><code style={{ fontFamily: 'monospace', fontWeight: '600' }}>{result.skill_id}</code></div>
                {result.agent_id && <div><span style={{ color: 'var(--gray-600)' }}>agent_id</span><br /><code style={{ fontFamily: 'monospace', fontSize: '11px' }}>{result.agent_id}</code></div>}
              </div>
              {result.message && <p style={{ marginTop: 'var(--spacing-2)', fontSize: 'var(--text-sm)', color: 'var(--gray-700)' }}>{result.message}</p>}
            </div>
            <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
              <Button variant="primary" onClick={() => { onSuccess?.(); onClose(); }}>Done</Button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default RegisterSkillModal;
