// Agent type « bitbucket » — tout ce qui le concerne est ici (voir registry/README.md)
import { isValidBranchName } from '../shared';

// [BITBUCKET] Champs d'exécution visibles par mode
export const BITBUCKET_FIELDS_BY_MODE = {
  read:         ['url', 'project', 'repo', 'path', 'ref', 'question'],
  pull_request: ['url', 'project', 'repo', 'pr_id', 'post_comment'],
  write:        ['url', 'project', 'repo', 'path', 'ref', 'instruction', 'branch', 'commit_message', 'open_pr', 'pr_title'],
};

// [BITBUCKET] Rendu texte des résultats bitbucket — modes read | pull_request | write
const formatBitbucketResult = (r) => {
  if (!r || typeof r !== 'object') return '';
  const p = r.mode ? r : (r.data && r.data.mode ? r.data : r);
  if (!p.mode) return '';
  const tgt = p.target || {};
  const where = [tgt.project, tgt.repo].filter(Boolean).join('/')
    + (tgt.path ? `/${String(tgt.path).replace(/^\//, '')}` : '')
    + (tgt.ref ? ` @ ${tgt.ref}` : '');
  const L = [];
  switch (p.mode) {
    case 'read': {
      const extra = [tgt.type, tgt.entries != null ? `${tgt.entries} entries` : null, tgt.chars != null ? `${tgt.chars} chars` : null]
        .filter(Boolean).join(' · ');
      L.push(`Target: ${where}${extra ? `  (${extra})` : ''}`);
      if (p.question) L.push(`Question: ${p.question}`);
      L.push('', '── LLM analysis ──', p.analysis || '(empty)');
      break;
    }
    case 'pull_request': {
      const pr = p.pull_request || {};
      L.push(
        `PR #${pr.id ?? '?'}: ${pr.title || ''}`,
        `${pr.fromRef || '?'} → ${pr.toRef || '?'}  [${pr.state || '?'}]  by ${pr.author || '?'}`,
        `Comment posted on the PR: ${p.comment_posted ? 'yes' : 'no'}`,
        '', '── LLM review ──', p.review || '(empty)'
      );
      break;
    }
    case 'write': {
      const c = p.commit || {};
      L.push(
        `Target: ${where}`,
        `Branch: ${p.branch}  (base: ${p.base_branch})`,
        `Commit: ${c.displayId || c.commit || '—'}`
      );
      if (p.pull_request) {
        L.push(`Pull request: #${p.pull_request.id} ${p.pull_request.title || ''}`);
        if (p.pull_request.url) L.push(p.pull_request.url);
      } else {
        L.push('Pull request: none');
      }
      L.push('', '── Content preview (first 300 chars) ──', p.content_preview || '');
      break;
    }
    default:
      return JSON.stringify(p, null, 2);
  }
  if (p.metadata?.timestamp) L.push('', `Done: ${p.metadata.timestamp}`);
  return L.join('\n');
};

// [BITBUCKET] Config spécifique bitbucket
const BitbucketConfigFields = ({ formData, updateConfigField }) => {
  const bb = formData.mcp_config.bitbucket || {};
  const cfg = formData.config || {};
  const hint = { fontSize: 'var(--text-xs)', color: 'var(--gray-500)' };
  const code = { background: 'var(--gray-200)', padding: '0 3px', borderRadius: '3px' };
  return (
    <div style={{ padding: 'var(--spacing-4)', backgroundColor: 'var(--gray-100)', borderRadius: 'var(--radius)', marginBottom: 'var(--spacing-4)' }}>
      <h3 style={{ fontWeight: '600', fontSize: 'var(--text-sm)', marginBottom: 'var(--spacing-3)' }}>Bitbucket configuration</h3>

      <div className="form-group">
        <label className="form-label">Bitbucket URL * <span style={hint}>base URL, without /rest (keep the context path if any)</span></label>
        <input type="text" className="form-input" value={bb.base_url || ''} onChange={e => updateConfigField('mcp_config.bitbucket.base_url', e.target.value)} placeholder="https://bitbucket.aecoding.local" />
      </div>
      <div className="form-group">
        <label className="form-label">HTTP access token * <span style={hint}>Profile → Manage account → HTTP access tokens</span></label>
        <input type="password" className="form-input" value={bb.token || ''} onChange={e => updateConfigField('mcp_config.bitbucket.token', e.target.value)} placeholder="Bitbucket HTTP access token" />
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 2fr 1fr', gap: 'var(--spacing-3)' }}>
        <div className="form-group">
          <label className="form-label">Verify SSL</label>
          <select className="form-input" value={bb.verify_ssl === false ? 'false' : 'true'} onChange={e => updateConfigField('mcp_config.bitbucket.verify_ssl', e.target.value === 'true')}>
            <option value="true">true</option>
            <option value="false">false (not recommended)</option>
          </select>
        </div>
        <div className="form-group">
          <label className="form-label">CA bundle <span style={hint}>optional — overrides Verify SSL</span></label>
          <input type="text" className="form-input" value={bb.ca_bundle || ''} onChange={e => updateConfigField('mcp_config.bitbucket.ca_bundle', e.target.value)} placeholder="/etc/ssl/certs/internal-ca.pem" />
        </div>
        <div className="form-group">
          <label className="form-label">Timeout (s)</label>
          <input type="number" className="form-input" value={bb.timeout ?? 30} onChange={e => updateConfigField('mcp_config.bitbucket.timeout', e.target.value === '' || isNaN(parseInt(e.target.value, 10)) ? 30 : parseInt(e.target.value, 10))} />
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 2fr', gap: 'var(--spacing-3)' }}>
        <div className="form-group">
          <label className="form-label">Default mode</label>
          <select className="form-input" value={cfg.mode || 'read'} onChange={e => updateConfigField('config.mode', e.target.value)}>
            {Object.keys(BITBUCKET_FIELDS_BY_MODE).map(m => <option key={m} value={m}>{m}</option>)}
          </select>
        </div>
        <div className="form-group">
          <label className="form-label">Push on default branch <span style={hint}>mode write</span></label>
          <select className="form-input" value={cfg.allow_push_default ? 'true' : 'false'} onChange={e => updateConfigField('config.allow_push_default', e.target.value === 'true')}>
            <option value="false">forbidden (recommended) — a dedicated branch is required</option>
            <option value="true">allowed — direct commit on the default branch</option>
          </select>
        </div>
      </div>

      <div style={{ border: '1px solid var(--info)', borderLeft: '3px solid var(--info)', borderRadius: 'var(--radius)', padding: 'var(--spacing-2) var(--spacing-3)', backgroundColor: 'rgba(96,165,250,0.06)', fontSize: 'var(--text-xs)', color: 'var(--gray-700)', lineHeight: '1.6' }}>
        <strong style={{ color: 'var(--info)' }}>Token permissions.</strong> <code style={code}>Repository read</code> is enough for modes read and pull_request.
        Mode <code style={code}>write</code>, <code style={code}>open_pr</code> and <code style={code}>post_comment</code> need <code style={code}>Repository write</code>.
        Merging a pull request is intentionally not exposed by the MCP server.
      </div>
    </div>
  );
};

export default {
  name: 'Bitbucket Assistant',
  description: 'Bitbucket Server / Data Center — analyze a file or repository, review a Pull Request with the LLM, or rewrite a file on a dedicated branch (optional PR) via MCP Bitbucket',
  icon: '⬡', color: '#2684FF', badge: 'fixed', mcp: ['bitbucket'],
  defaultConfig: (providers) => ({
    mcp_servers: ['bitbucket'],
    mode: 'read',
    allow_push_default: false,
    llm_provider: providers[0]?.name || 'lmstudio',
    llm_model: 'openai/gpt-oss-20b',
    llm_temperature: 0.2,
  }),
  mcpConfig: { bitbucket: { base_url: '', token: '', verify_ssl: true, ca_bundle: '', timeout: 30 } },
  requiredFields: ['bitbucket.base_url', 'bitbucket.token'],
  executeFields: [
    { name: 'mode', label: 'Mode', type: 'select', required: true, options: [
        { value: 'read',         label: 'read — analyze a file / folder / repository' },
        { value: 'pull_request', label: 'pull_request — LLM code review of a PR' },
        { value: 'write',        label: 'write — LLM rewrite of a file on a dedicated branch' },
      ], defaultValue: 'read' },
    { name: 'url', label: 'Bitbucket URL (optional if project + repo are set)', type: 'text', placeholder: 'https://bitbucket.example.fr/projects/KEY/repos/my-repo/browse/path?at=main' },
    { name: 'project', label: 'Project key (overrides URL)', type: 'text', placeholder: 'KEY  (personal repo: ~username)' },
    { name: 'repo', label: 'Repository slug (overrides URL)', type: 'text', placeholder: 'my-repo' },
    { name: 'path', label: 'Path (file or folder — mode write: file required)', type: 'text', placeholder: 'charts/app/values.yaml' },
    { name: 'ref', label: 'Branch / tag / commit (optional — default: repo default branch)', type: 'text', placeholder: 'main' },
    { name: 'question', label: 'Question (optional — default: general synthesis)', type: 'text', placeholder: 'How is the ingress configured?' },
    { name: 'pr_id', label: 'Pull request ID (or use a .../pull-requests/<id> URL)', type: 'number', placeholder: '42' },
    { name: 'post_comment', label: 'Post the review as a comment on the PR', type: 'checkbox', defaultValue: false },
    { name: 'instruction', label: 'Rewrite instruction', type: 'textarea', required: false, placeholder: 'Add a readiness probe on /health and bump the image tag to 1.2.3...' },
    { name: 'branch', label: 'Target branch (optional — default: auto mcp/<timestamp>-<file>)', type: 'text', placeholder: 'feature/ai-readiness-probe' },
    { name: 'commit_message', label: 'Commit message (optional)', type: 'text', placeholder: 'chore(values): add readiness probe' },
    { name: 'open_pr', label: 'Open a Pull Request after the commit', type: 'checkbox', defaultValue: false },
    { name: 'pr_title', label: 'Pull request title (optional)', type: 'text', placeholder: 'values.yaml: add readiness probe' },
  ],
  // seuls les champs du mode courant sont envoyés ; les booléens sont explicites
  buildInput: (d) => {
    const mode = d.mode || 'read';
    const allowed = BITBUCKET_FIELDS_BY_MODE[mode] || [];
    const has = (k) => allowed.includes(k) && d[k] !== undefined && d[k] !== false && String(d[k]).trim() !== '';
    const r = { mode };
    ['url', 'project', 'repo', 'path', 'ref', 'question', 'instruction', 'branch', 'commit_message', 'pr_title'].forEach(k => {
      if (has(k)) r[k] = String(d[k]).trim();
    });
    if (has('pr_id') && !isNaN(parseInt(d.pr_id, 10))) r.pr_id = parseInt(d.pr_id, 10);
    if (mode === 'pull_request') r.post_comment = !!d.post_comment;
    if (mode === 'write') r.open_pr = !!d.open_pr;
    return r;
  },
  validate: (d) => {
    const m = d.mode || 'read';
    const url = String(d.url || '').trim();
    const project = String(d.project || '').trim();
    const repo = String(d.repo || '').trim();
    if (!url && !(project && repo)) return 'Provide a Bitbucket URL or project + repository';
    if (url && !/^https?:\/\//i.test(url)) return 'URL must start with http:// or https://';
    if (m === 'pull_request') {
      const pr = String(d.pr_id ?? '').trim();
      if (pr && !/^[1-9]\d*$/.test(pr)) return 'PR ID must be a positive integer';
      if (!pr && !/\/pull-requests\/\d+/.test(url)) return 'A pull request URL (.../pull-requests/<id>) or a PR ID is required';
    }
    if (m === 'write') {
      if (!String(d.instruction || '').trim()) return 'Rewrite instruction is required';
      const path = String(d.path || '').trim();
      if (!path && !/\/browse\/[^?#]+/.test(url)) return 'A file path is required (.../browse/<file> URL or Path field)';
      const branch = String(d.branch || '').trim();
      if (branch && !isValidBranchName(branch)) return 'Branch must be a valid git branch name (letters, digits, . _ - /)';
    }
    return null;
  },
  isFieldVisible: (field, d) => {
    if (field.name === 'mode') return true;
    return (BITBUCKET_FIELDS_BY_MODE[d.mode || 'read'] || []).includes(field.name);
  },
  initialExecuteValues: (agent) => (agent.config?.mode ? { mode: agent.config.mode } : {}),
  formatResult: formatBitbucketResult,
  ConfigFields: BitbucketConfigFields,
};
