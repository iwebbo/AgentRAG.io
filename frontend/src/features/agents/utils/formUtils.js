// Mise à jour immuable d'un champ de formData par chemin ("config.x.y" | "mcp_config.server.key").
// Partagé par CreateAgentModal et AgentConfigModal (implémentation auparavant dupliquée).
export const applyConfigPath = (prev, path, value) => {
  const keys = path.split('.');
  const next = { ...prev, config: { ...prev.config }, mcp_config: { ...prev.mcp_config } };
  let cur = keys[0] === 'mcp_config' ? next.mcp_config : next.config;
  for (let i = 1; i < keys.length - 1; i++) {
    cur[keys[i]] = { ...(cur[keys[i]] || {}) };
    cur = cur[keys[i]];
  }
  cur[keys[keys.length - 1]] = value;
  return next;
};
