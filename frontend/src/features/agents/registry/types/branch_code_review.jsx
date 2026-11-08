// Agent type « branch_code_review » — tout ce qui le concerne est ici (voir registry/README.md)
import GithubConnectionFields from '../../components/config/GithubConnectionFields';

export default {
  name: 'Code Review',
  description: 'Automatic code review on Git branches with fix suggestions and PR creation',
  icon: '⎔', color: '#3b82f6', badge: 'fixed', mcp: ['github'],
  defaultConfig: (providers) => ({ mcp_servers: ['github'], use_llm: true, llm_provider: providers[0]?.name || 'ollama', llm_model: 'codestral:22b', llm_temperature: 0.3, review_focus: 'security', auto_fix: true, auto_create_pr: true }),
  mcpConfig: { github: { token: '', repo: '' } },
  requiredFields: ['github.token', 'github.repo'],
  executeFields: [
    { name: 'branch', label: 'Branch name', type: 'text', placeholder: 'feature/my-branch', required: true }
  ],
  buildInput: (d) => ({ branch: d.branch }),
  ConfigFields: GithubConnectionFields,
};
