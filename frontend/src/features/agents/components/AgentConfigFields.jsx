import { AGENT_TYPES } from '../registry';
import LlmConfigFields from './config/LlmConfigFields';

// Bloc de configuration partagé entre Create et Edit :
// LLM (commun) + bloc propre au type (registry/types/<agent_type>.jsx → ConfigFields).
const AgentConfigFields = ({ agentType, formData, providers, skills, updateConfigField }) => {
  const TypeConfigFields = AGENT_TYPES[agentType]?.ConfigFields;
  return (
    <>
      <LlmConfigFields formData={formData} providers={providers} updateConfigField={updateConfigField} />
      {TypeConfigFields && (
        <TypeConfigFields formData={formData} providers={providers} skills={skills} updateConfigField={updateConfigField} />
      )}
    </>
  );
};

export default AgentConfigFields;
