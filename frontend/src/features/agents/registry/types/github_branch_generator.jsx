// Agent type « github_branch_generator » — tout ce qui le concerne est ici (voir registry/README.md)
import GithubConnectionFields from '../../components/config/GithubConnectionFields';
import BranchGeneratorConfigFields from '../../components/config/BranchGeneratorConfigFields';
import { BRANCH_GENERATOR_EXECUTE_FIELDS, buildBranchGeneratorInput, validateBranchGeneratorInput } from '../shared';

const ConfigFields = (props) => (
  <>
    <GithubConnectionFields {...props} />
    <BranchGeneratorConfigFields {...props} />
  </>
);

export default {
  name: 'GitHub Branch Generator',
  description: 'Generate files from scratch with the LLM from your prompt (kept in /tmp), create a new branch, push them and optionally open a Pull Request via MCP GitHub',
  icon: '⎇', color: '#14b8a6', badge: 'fixed', mcp: ['github'],
  defaultConfig: (providers) => ({
    mcp_servers: ['github'],
    base_branch: 'main',
    auto_create_pr: false,
    max_files: 40,
    max_tokens: 8000,
    llm_provider: providers[0]?.name || 'lmstudio',
    llm_model: 'openai/gpt-oss-20b',
    llm_temperature: 0.2,
  }),
  mcpConfig: { github: { token: '', repo: '' } },
  requiredFields: ['github.token', 'github.repo'],
  executeFields: BRANCH_GENERATOR_EXECUTE_FIELDS,
  buildInput: buildBranchGeneratorInput,
  validate: validateBranchGeneratorInput,
  ConfigFields,
};
