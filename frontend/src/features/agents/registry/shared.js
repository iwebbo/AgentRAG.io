// Helpers partagés du registre des agents — aucune dépendance React.
// Tout ce qui est commun à plusieurs types d'agents (builders de payload, validations,
// champs d'exécution communs) vit ici ; la logique propre à un seul type reste dans types/<type>.jsx.

// Champs d'exécution partagés par github_branch_generator / gitea_branch_generator
export const BRANCH_GENERATOR_EXECUTE_FIELDS = [
  { name: 'prompt', label: 'Generation prompt (what to generate)', type: 'textarea', required: true, placeholder: 'Create a Helm chart for a FastAPI app with ingress and HPA...' },
  { name: 'branch', label: 'New branch name (must not exist yet)', type: 'text', required: true, placeholder: 'feature/ai-helm-chart' },
  { name: 'base_branch', label: 'Base branch (optional — default: agent config)', type: 'text', placeholder: 'main' },
  { name: 'repo', label: 'Repository override (optional — default: agent MCP config)', type: 'text', placeholder: 'owner/repo' },
  { name: 'commit_message', label: 'Commit message (optional)', type: 'text', placeholder: 'feat: add helm chart' },
  { name: 'create_pr', label: 'Create a Pull Request after the push', type: 'checkbox', defaultValue: false },
  { name: 'pr_title', label: 'Pull request title (optional)', type: 'text', placeholder: 'feat: add helm chart' },
  { name: 'context', label: 'Additional context (optional — stack, constraints, conventions)', type: 'textarea', placeholder: 'Python 3.11, Kubernetes 1.29, ...' },
  { name: 'dry_run', label: 'Dry run (generate only — no branch, no push)', type: 'checkbox', defaultValue: true },
];

// Extraction générique du texte d'un payload agent
export const extractContent = (data) => {
  if (!data) return '';
  if (typeof data === 'string') return data;
  return data.content || data.result || data.output || data.summary || data.text
    || (data.data && extractContent(data.data)) || '';
};

// Clone profond du template mcpConfig du type, puis merge des valeurs persistées.
// Indispensable : un spread superficiel partageait les sous-objets avec AGENT_TYPES,
// et la saisie d'un token mutait la constante globale (fuite entre agents).
export const mergeMcpConfig = (template, saved) => {
  const base = JSON.parse(JSON.stringify(template || {}));
  Object.entries(saved || {}).forEach(([server, cfg]) => {
    base[server] = (cfg && typeof cfg === 'object' && !Array.isArray(cfg))
      ? { ...(base[server] || {}), ...cfg }
      : cfg;
  });
  return base;
};

// Validation par défaut : tous les executeFields marqués required doivent être renseignés.
export const validateRequired = (fields, d) => {
  for (const f of (fields || []).filter(x => x.required)) {
    if (!d[f.name]) return `"${f.label}" is required`;
  }
  return null;
};

export const isValidBranchName = (b) =>
  !!b && /^[A-Za-z0-9._/-]+$/.test(b) && !/^[/.-]|[/.]$|\.\.|\/\//.test(b);

// ── github_changelog / gitea_changelog ──────────────────────────────────────
export const buildChangelogInput = (d) => {
  const r = { version: String(d.version || '').trim(), dry_run: d.dry_run ?? true };
  if (d.pr_number !== undefined && String(d.pr_number).trim() !== '') r.pr_number = parseInt(String(d.pr_number).replace('#', ''), 10);
  if (d.date && String(d.date).trim()) r.date = String(d.date).trim();
  return r;
};

// mêmes règles que le backend (VERSION_RE / DATE_RE / pr_number entier positif)
export const validateChangelogInput = (d) => {
  if (!/^v?\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?$/.test(String(d.version || '').trim())) {
    return 'Version must be a semantic version such as v1.1.81';
  }
  const date = String(d.date || '').trim();
  if (date && !/^\d{2}\/\d{2}\/\d{4}$/.test(date)) return 'Date must use the DD/MM/YYYY format';
  const pr = String(d.pr_number ?? '').trim();
  if (pr && !/^#?[1-9]\d*$/.test(pr)) return 'PR number must be a positive integer';
  return null;
};

// ── github_branch_generator / gitea_branch_generator ────────────────────────
export const buildBranchGeneratorInput = (d) => {
  const r = {
    prompt: String(d.prompt || '').trim(),
    branch: String(d.branch || '').trim(),
    dry_run: d.dry_run ?? true,
  };
  ['base_branch', 'repo', 'commit_message', 'pr_title', 'context'].forEach(k => {
    if (d[k] && String(d[k]).trim()) r[k] = String(d[k]).trim();
  });
  if (d.create_pr) r.create_pr = true;
  return r;
};

export const validateBranchGeneratorInput = (d) => {
  if (!String(d.prompt || '').trim()) return 'Generation prompt is required';
  if (!isValidBranchName(String(d.branch || '').trim())) return 'Branch must be a valid git branch name (letters, digits, . _ - /)';
  const repo = String(d.repo || '').trim();
  if (repo && !/^[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+$/.test(repo)) return 'Repository must use the owner/repo format';
  return null;
};

// ── ansible_role_generator / gitea_ansible_role_generator ───────────────────
export const buildAnsibleRoleInput = (d) => ({
  role_name: d.role_name,
  description: d.description,
  supported_os: d.supported_os ? d.supported_os.split(',').map(s => s.trim()).filter(Boolean) : ['Debian', 'RedHat'],
  test_mode: d.test_mode ?? false,
});
