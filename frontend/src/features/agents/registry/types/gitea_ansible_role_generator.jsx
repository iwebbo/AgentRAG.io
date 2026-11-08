// Agent type « gitea_ansible_role_generator » — tout ce qui le concerne est ici (voir registry/README.md)
import GiteaCodeGenFields from '../../components/config/GiteaCodeGenFields';
import { buildAnsibleRoleInput } from '../shared';

export default {
  name: 'Gitea Ansible Role Generator',
  description: 'Scaffold and push a complete Ansible role (Galaxy structure) to a self-hosted Gitea repo via MCP',
  icon: '⚙', color: '#f97316', badge: 'fixed', mcp: ['gitea', 'linter'],
  defaultConfig: (providers) => ({
    mcp_servers: ['gitea', 'linter'],
    llm_provider: providers[0]?.name || 'lmstudio',
    llm_model: 'openai/gpt-oss-20b',
    llm_temperature: 0.2,
    base_branch: 'main',
    auto_lint: true,
    auto_commit: true,
    auto_create_pr: false,
    roles_path: 'roles',
  }),
  mcpConfig: { gitea: { url: '', token: '', repo: '' } },
  requiredFields: ['gitea.url', 'gitea.token', 'gitea.repo'],
  executeFields: [
    { name: 'role_name', label: 'Role name', type: 'text', required: true, placeholder: 'nginx_hardening' },
    { name: 'description', label: 'Description', type: 'textarea', required: true },
    { name: 'supported_os', label: 'Supported OS (comma-separated)', type: 'text', placeholder: 'Debian, RedHat' },
  ],
  buildInput: buildAnsibleRoleInput,
  ConfigFields: GiteaCodeGenFields,
};
