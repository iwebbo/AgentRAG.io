// Agent type « email_expert » — tout ce qui le concerne est ici (voir registry/README.md)

// Config spécifique email_expert
const EmailConfigFields = ({ formData, updateConfigField }) => (
  <div style={{ padding: 'var(--spacing-4)', backgroundColor: 'var(--gray-100)', borderRadius: 'var(--radius)', marginBottom: 'var(--spacing-4)' }}>
    <h3 style={{ fontWeight: '600', fontSize: 'var(--text-sm)', marginBottom: 'var(--spacing-3)' }}>Email configuration</h3>
    <div className="form-group"><label className="form-label">Email address *</label><input type="email" className="form-input" value={formData.config.email_config?.email || ''} onChange={e => updateConfigField('config.email_config.email', e.target.value)} placeholder="your.email@gmail.com" /></div>
    <div className="form-group"><label className="form-label">App password * <span style={{ fontSize: 'var(--text-xs)', color: 'var(--gray-500)' }}>Use app-specific password</span></label><input type="password" className="form-input" value={formData.config.email_config?.password || ''} onChange={e => updateConfigField('config.email_config.password', e.target.value)} placeholder="App-specific password" /></div>
  </div>
);

// Champs d'exécution visibles selon le mode
const EMAIL_CONDITIONAL = ['to', 'subject', 'body', 'instructions', 'context', 'limit', 'unread_only', 'auto_send'];
const EMAIL_FIELDS_BY_MODE = {
  send_email: ['to', 'subject', 'body'],
  send_email_llm: ['to', 'subject', 'instructions', 'context', 'auto_send'],
  analyze_inbox: ['limit', 'unread_only'],
};

export default {
  name: 'Email Expert',
  description: 'Smart email management — analysis, drafting, automatic replies',
  icon: '⊠', color: '#f59e0b', badge: 'fixed', mcp: [],
  defaultConfig: (providers) => ({ llm_provider: providers[0]?.name || 'ollama', llm_model: 'mistrallite:latest', llm_temperature: 0.6, email_config: { email: '', password: '', imap_host: 'imap.gmail.com', imap_port: 993, smtp_host: 'smtp.gmail.com', smtp_port: 587, auto_categorize: true, auto_reply_enabled: false, signature: 'Best regards,\nYour AI Assistant', default_tone: 'professional', language: 'en' } }),
  mcpConfig: {}, requiredFields: ['email_config.email', 'email_config.password'],
  executeFields: [
    { name: 'mode', label: 'Email mode', type: 'select', required: true, options: [ { value: 'send_email', label: 'Send email' }, { value: 'send_email_llm', label: 'Send email (LLM-generated)' }, { value: 'analyze_inbox', label: 'Analyze inbox' } ] },
    { name: 'to', label: 'To (send modes)', type: 'text', placeholder: 'recipient@example.com' },
    { name: 'subject', label: 'Subject (send modes)', type: 'text', placeholder: 'Email subject' },
    { name: 'body', label: 'Body (send_email)', type: 'textarea', placeholder: 'Email content...' },
    { name: 'instructions', label: 'Instructions (send_email_llm)', type: 'textarea', placeholder: 'Instructions for LLM...' },
    { name: 'context', label: 'Context (send_email_llm)', type: 'text', placeholder: 'Additional context' },
    { name: 'limit', label: 'Limit (analyze_inbox)', type: 'number', placeholder: '20' },
    { name: 'unread_only', label: 'Unread only (analyze_inbox)', type: 'checkbox', defaultValue: true },
    { name: 'auto_send', label: 'Auto send (send_email_llm)', type: 'checkbox', defaultValue: false }
  ],
  buildInput: (d) => {
    const r = { mode: d.mode };
    if (d.mode === 'send_email') { r.to = d.to; r.subject = d.subject; r.body = d.body; }
    else if (d.mode === 'send_email_llm') { r.to = d.to; r.subject = d.subject; r.instructions = d.instructions; r.context = d.context; r.auto_send = d.auto_send ?? false; }
    else if (d.mode === 'analyze_inbox') { r.limit = parseInt(d.limit) || 20; r.unread_only = d.unread_only ?? true; }
    return r;
  },
  isFieldVisible: (field, d) => {
    if (!EMAIL_CONDITIONAL.includes(field.name)) return true;
    if (!d.mode) return false;
    const allowed = EMAIL_FIELDS_BY_MODE[d.mode];
    return allowed ? allowed.includes(field.name) : true;
  },
  ConfigFields: EmailConfigFields,
};
