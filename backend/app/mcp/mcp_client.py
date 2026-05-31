from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class MCPClient:
    """
    Client MCP gÃ©nÃ©rique pour gÃ©rer les appels aux diffÃ©rents servers.
    
    Architecture simple et extensible :
    - Chaque server est un objet qui implÃ©mente des mÃ©thodes
    - Le client route les appels vers le bon server
    """
    
    def __init__(self, mcp_config: Dict[str, Any]):
        """
        Args:
            mcp_config: Configuration des MCP servers
            {
                "github": {"token": "...", "repo": "..."},
                "jira": {"url": "...", "token": "..."},
                ...
            }
        """
        self.config = mcp_config
        self.servers: Dict[str, Any] = {}
        
        logger.info("MCP Client initialized")
    
    def register_server(self, name: str, server_instance: Any):
        """
        Enregistre un MCP server.
        
        Args:
            name: Nom du server (github, jira, slack, etc.)
            server_instance: Instance du server
        """
        self.servers[name] = server_instance
        logger.info(f"MCP server registered: {name}")
    
    async def call(self, server: str, method: str, params: Dict[str, Any]) -> Any:
        """
        Appelle une mÃ©thode sur un MCP server.
        
        Args:
            server: Nom du server
            method: Nom de la mÃ©thode
            params: ParamÃ¨tres de la mÃ©thode
            
        Returns:
            RÃ©sultat de l'appel
            
        Raises:
            ValueError: Si le server n'existe pas
            AttributeError: Si la mÃ©thode n'existe pas
        """
        if server not in self.servers:
            raise ValueError(f"MCP server '{server}' not registered")
        
        server_instance = self.servers[server]
        
        if not hasattr(server_instance, method):
            raise AttributeError(f"Method '{method}' not found on server '{server}'")
        
        method_func = getattr(server_instance, method)
        
        logger.debug(f"Calling {server}.{method}({params})")
        
        # Call the method
        result = await method_func(**params)
        
        return result
    
    def get_server_config(self, server: str) -> Dict[str, Any]:
        """Récupère la config d'un server."""
        return self.config.get(server, {})

    def get_schema(self, server: str) -> Dict[str, Any]:
        """
        Introspects a registered MCP server and returns its full method schema.

        Works generically on ANY server — no hardcoded knowledge required.
        Skips private methods (_*) and the router method 'call'.

        Returns:
            {
              "exec_command": {
                "description": "Run a single shell command.",
                "params": {
                  "host": {"type": "str", "required": True},
                  "cmd":  {"type": "str", "required": True},
                  "timeout": {"type": "int", "required": False, "default": 30}
                }
              },
              ...
            }
        """
        import inspect

        if server not in self.servers:
            raise ValueError(f"MCP server '{server}' not registered")

        instance = self.servers[server]
        schema: Dict[str, Any] = {}

        for name, member in inspect.getmembers(instance, predicate=inspect.ismethod):
            if name.startswith("_") or name == "call":
                continue

            sig = inspect.signature(member)
            params: Dict[str, Any] = {}

            for pname, p in sig.parameters.items():
                if pname in ("self",):
                    continue
                if p.kind == inspect.Parameter.VAR_KEYWORD:
                    continue

                annotation = p.annotation
                if annotation is inspect.Parameter.empty:
                    type_name = "any"
                elif hasattr(annotation, "__name__"):
                    type_name = annotation.__name__
                else:
                    type_name = str(annotation)

                entry: Dict[str, Any] = {
                    "type":     type_name,
                    "required": p.default is inspect.Parameter.empty,
                }
                if p.default is not inspect.Parameter.empty:
                    entry["default"] = p.default

                params[pname] = entry

            doc = (member.__doc__ or "").strip()
            description = doc.split("\n")[0] if doc else ""

            schema[name] = {
                "description": description,
                "params":      params,
            }

        return schema

    def get_schema_as_text(self, server: str) -> str:
        """
        Returns the server schema as a compact text block for LLM injection.

        Example output:
            exec_command(host: str, cmd: str, timeout: int = 30)
              Run a single shell command.
        """
        schema = self.get_schema(server)
        lines = [f"MCP server '{server}' — available methods:\n"]

        for method_name, info in sorted(schema.items()):
            params = info["params"]
            sig_parts = []
            for pname, pmeta in params.items():
                ptype = pmeta["type"]
                if pmeta["required"]:
                    sig_parts.append(f"{pname}: {ptype}")
                else:
                    sig_parts.append(f"{pname}: {ptype} = {pmeta.get('default', '?')}")

            sig = ", ".join(sig_parts)
            desc = info.get("description", "")
            lines.append(f"  {method_name}({sig})")
            if desc:
                lines.append(f"    {desc}")

        return "\n".join(lines)