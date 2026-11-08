# Registre des agents — ajouter un agent déterministe

Un type d'agent = **un fichier** `types/<agent_type>.jsx` + **une ligne** dans `index.js`.
`<agent_type>` doit être exactement la valeur `agent_type` attendue par le backend.

```jsx
export default {
  // ── Données (obligatoires) ──
  name, description, icon, color, badge: 'fixed' | 'skill', mcp: ['github'],
  defaultConfig: (providers) => ({ ... }),   // config initiale à la création
  mcpConfig: { github: { token: '', repo: '' } },
  requiredFields: ['github.token', 'github.repo'],   // validés à la création
  executeFields: [ { name, label, type, required, placeholder, defaultValue, options } ],

  // ── Comportement (optionnel, valeurs par défaut entre parenthèses) ──
  buildInput: (d) => ({ ... }),              // formulaire -> input_data ({} )
  validate: (d) => 'message' | null,         // (champs executeFields required non vides)
  isFieldVisible: (field, d) => boolean,     // champs conditionnels par mode (tous visibles)
  initialExecuteValues: (agent) => ({ ... }),// valeurs initiales du formulaire d'exécution ({})
  formatResult: (raw) => 'texte',            // rendu de l'Output (extraction générique)
  mergeConfig: (defaults, saved) => ({ ... }),// merge à l'édition ({ ...defaults, ...saved })
  ConfigFields: Component,                   // bloc de config Create + Edit (aucun)
  ExecuteFields: Component,                  // remplace le formulaire générique (aucun)
};
```

Briques réutilisables : `registry/shared.js` (builders/validations communs),
`components/config/*` (blocs GitHub / Gitea / Changelog / Branch generator).

À mettre à jour à la main : l'onglet Docs (`docs/docEntries.js`), si l'agent mérite une entrée.
Le tableau « Agent types reference » de cet onglet est généré depuis le registre.
