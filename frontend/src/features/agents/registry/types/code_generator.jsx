// Agent type « code_generator » — tout ce qui le concerne est ici (voir registry/README.md)
import GithubConnectionFields from '../../components/config/GithubConnectionFields';

export default {
  name: 'Code Generator',
  description: 'AI-assisted code generation with RAG, automatic tests and linting',
  icon: '⌬', color: '#8b5cf6', badge: 'fixed', mcp: ['github', 'linter'],
  defaultConfig: (providers) => ({ mcp_servers: ['github', 'linter'], llm_provider: providers[0]?.name || 'ollama', llm_model: 'codestral:22b', llm_temperature: 0.2, target_branch: 'ai-feature', base_branch: 'main', auto_test: true, auto_lint: true, auto_commit: true, auto_create_pr: false }),
  mcpConfig: { github: { token: '', repo: '' } },
  requiredFields: ['github.token', 'github.repo'],
  executeFields: [
    { name: 'prompt', label: 'Code generation prompt', type: 'textarea', placeholder: 'Add OAuth2 authentication...', required: true },
    { name: 'create_new_files', label: 'Create new files', type: 'checkbox', defaultValue: true },
    { name: 'test_mode', label: 'Test mode (dry-run)', type: 'checkbox', defaultValue: true }
  ],
  buildInput: (d) => ({ prompt: d.prompt, create_new_files: d.create_new_files ?? true, test_mode: d.test_mode ?? true }),
  ConfigFields: GithubConnectionFields,
};
