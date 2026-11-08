import { createContext } from 'react';

// État de la dernière exécution : { status, error, logs, nodes: { [nodeId]: { status, output, logs, error } } }
// Fourni par WorkflowEditor, lu par AgentNode / RunSummary / NodePropertiesPanel.
export const EMPTY_RUN = { status: 'idle', error: null, logs: [], nodes: {} };

export const RunStateContext = createContext(EMPTY_RUN);
