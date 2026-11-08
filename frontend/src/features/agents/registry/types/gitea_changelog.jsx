// Agent type « gitea_changelog » — tout ce qui le concerne est ici (voir registry/README.md)
import GiteaConnectionFields from '../../components/config/GiteaConnectionFields';
import ChangelogConfigFields from '../../components/config/ChangelogConfigFields';
import { buildChangelogInput, validateChangelogInput } from '../shared';

const ConfigFields = (props) => (
  <>
    <GiteaConnectionFields {...props} />
    <ChangelogConfigFields {...props} />
  </>
);

export default {
  name: 'Gitea Changelog',
  description: 'Generate CHANGELOG.md from the latest Pull Request targeting the base branch and push it to the PR source branch on a self-hosted Gitea via MCP',
  icon: '☷', color: '#f97316', badge: 'fixed', mcp: ['gitea'],
  defaultConfig: (providers) => ({
    mcp_servers: ['gitea'],
    base_branch: 'main',
    pr_state: 'open',
    pr_scan_limit: 30,
    changelog_path: 'CHANGELOG.md',
    use_llm: true,
    language: 'en',
    skip_ci: false,
    llm_provider: providers[0]?.name || 'lmstudio',
    llm_model: 'qwen3.5-4b-claude-4.6-opus-reasoning-distilled',
    llm_temperature: 0.1,
  }),
  mcpConfig: { gitea: { url: '', token: '', repo: '' } },
  requiredFields: ['gitea.url', 'gitea.token', 'gitea.repo'],
  executeFields: [
    { name: 'version', label: 'Version', type: 'text', placeholder: 'v1.1.81', required: true },
    { name: 'pr_number', label: 'PR number (optional — default: latest PR to base branch)', type: 'number', placeholder: '42' },
    { name: 'date', label: 'Date (optional — DD/MM/YYYY, default: today)', type: 'text', placeholder: '19/10/2026' },
    { name: 'dry_run', label: 'Dry run (generate only — no commit, no push)', type: 'checkbox', defaultValue: true },
  ],
  buildInput: buildChangelogInput,
  validate: validateChangelogInput,
  ConfigFields,
};
