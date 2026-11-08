// Agent type « gitea_branch_generator » — tout ce qui le concerne est ici (voir registry/README.md)
import GiteaConnectionFields from '../../components/config/GiteaConnectionFields';
import BranchGeneratorConfigFields from '../../components/config/BranchGeneratorConfigFields';
import { BRANCH_GENERATOR_EXECUTE_FIELDS, buildBranchGeneratorInput, validateBranchGeneratorInput } from '../shared';

const ConfigFields = (props) => (
  <>
    <GiteaConnectionFields {...props} />
    <BranchGeneratorConfigFields {...props} />
  </>
);

export default {
  name: 'Gitea Branch Generator',
  description: 'Generate files from scratch with the LLM from your prompt (kept in /tmp), create a new branch, push them and optionally open a Pull Request via MCP Gitea',
  icon: '⑂', color: '#eab308', badge: 'fixed', mcp: ['gitea'],
  defaultConfig: (providers) => ({
    mcp_servers: ['gitea'],
    base_branch: 'main',
    auto_create_pr: false,
    max_files: 40,
    max_tokens: 8000,
    llm_provider: providers[0]?.name || 'lmstudio',
    llm_model: 'openai/gpt-oss-20b',
    llm_temperature: 0.2,
  }),
  mcpConfig: { gitea: { url: '', token: '', repo: '' } },
  requiredFields: ['gitea.url', 'gitea.token', 'gitea.repo'],
  executeFields: BRANCH_GENERATOR_EXECUTE_FIELDS,
  buildInput: buildBranchGeneratorInput,
  validate: validateBranchGeneratorInput,
  ConfigFields,
};
