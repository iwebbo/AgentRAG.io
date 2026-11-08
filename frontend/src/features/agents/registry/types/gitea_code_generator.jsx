// Agent type « gitea_code_generator » — tout ce qui le concerne est ici (voir registry/README.md)
import GiteaCodeGenFields from '../../components/config/GiteaCodeGenFields';

export default {
  name: 'Gitea Code Generator',
  description: 'Generate code, lint, commit and create PRs on a self-hosted Gitea repo via MCP Gitea + Linter',
  icon: '⟐', color: '#f97316', badge: 'fixed', mcp: ['gitea', 'linter'],
  defaultConfig: (providers) => ({ mcp_servers: ['gitea', 'linter'], llm_provider: providers[0]?.name || 'lmstudio', llm_model: 'openai/gpt-oss-20b', llm_temperature: 0.2, target_branch: 'ai-feature', base_branch: 'main', auto_test: false, auto_lint: true, auto_commit: true, auto_create_pr: false }),
  mcpConfig: { gitea: { url: '', token: '', repo: '' } },
  requiredFields: ['gitea.url', 'gitea.token', 'gitea.repo'],
  executeFields: [
    { name: 'prompt', label: 'Code generation prompt', type: 'textarea', placeholder: 'Add a health check endpoint /healthz returning JSON status…', required: true },
    { name: 'create_new_files', label: 'Create new files', type: 'checkbox', defaultValue: true },
    { name: 'test_mode', label: 'Test mode (dry-run, no commit)', type: 'checkbox', defaultValue: false }
  ],
  buildInput: (d) => ({ prompt: d.prompt, create_new_files: d.create_new_files ?? true, test_mode: d.test_mode ?? false }),
  ConfigFields: GiteaCodeGenFields,
};
