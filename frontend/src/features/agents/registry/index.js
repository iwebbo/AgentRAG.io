// Registre des types d'agents — SEUL point d'enregistrement.
// Ajouter un agent déterministe : créer types/<agent_type>.jsx puis l'ajouter ci-dessous (voir README.md).
import branch_code_review from './types/branch_code_review';
import code_generator from './types/code_generator';
import legal_fiscal from './types/legal_fiscal';
import accounting_finance from './types/accounting_finance';
import travel_expert from './types/travel_expert';
import email_expert from './types/email_expert';
import websearch from './types/websearch';
import skill from './types/skill';
import gitea_code_generator from './types/gitea_code_generator';
import ansible_role_generator from './types/ansible_role_generator';
import gitea_ansible_role_generator from './types/gitea_ansible_role_generator';
import github_changelog from './types/github_changelog';
import gitea_changelog from './types/gitea_changelog';
import github_branch_generator from './types/github_branch_generator';
import gitea_branch_generator from './types/gitea_branch_generator';
import datagouv_explorer from './types/datagouv_explorer';
import wikijs from './types/wikijs';
import sonarqube from './types/sonarqube';
import bitbucket from './types/bitbucket';
import { extractContent, mergeMcpConfig, validateRequired } from './shared';

export const AGENT_TYPES = {
  branch_code_review,
  code_generator,
  legal_fiscal,
  accounting_finance,
  travel_expert,
  email_expert,
  websearch,
  skill,
  gitea_code_generator,
  ansible_role_generator,
  gitea_ansible_role_generator,
  github_changelog,
  gitea_changelog,
  github_branch_generator,
  gitea_branch_generator,
  datagouv_explorer,
  wikijs,
  sonarqube,
  bitbucket,
};

export { extractContent, mergeMcpConfig };

// Rendu d'un output_data / payload result selon le type d'agent
export const renderAgentOutput = (agentTypeKey, raw) => {
  if (!raw) return '';
  const formatted = AGENT_TYPES[agentTypeKey]?.formatResult?.(raw);
  if (formatted) return formatted;
  if (typeof raw === 'string') return raw;
  return extractContent(raw) || JSON.stringify(raw, null, 2);
};

// Payload input_data envoyé à POST /api/agents/{id}/execute/stream
export const buildExecuteInput = (agentTypeKey, d) => AGENT_TYPES[agentTypeKey]?.buildInput?.(d) ?? {};

// Retourne un message d'erreur, ou null si la saisie est valide
export const validateExecuteInput = (agentTypeKey, d) => {
  const t = AGENT_TYPES[agentTypeKey];
  if (t?.validate) return t.validate(d) || null;
  return validateRequired(t?.executeFields, d);
};

// Config persistée fusionnée avec les défauts du type (comble les clés ajoutées depuis la création de l'agent)
export const mergeAgentConfig = (agentTypeKey, defaults, saved) => {
  const s = saved || {};
  const t = AGENT_TYPES[agentTypeKey];
  return t?.mergeConfig ? t.mergeConfig(defaults, s) : { ...defaults, ...s };
};
