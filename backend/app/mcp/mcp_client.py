from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class MCPClient:
    """
    Client MCP générique pour gérer les appels aux différents servers.
    
    Architecture simple et extensible :
    - Chaque server est un objet qui implémente des méthodes
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
        Appelle une méthode sur un MCP server.
        
        Args:
            server: Nom du server
            method: Nom de la méthode
            params: Paramètres de la méthode
            
        Returns:
            Résultat de l'appel
            
        Raises:
            ValueError: Si le server n'existe pas
            AttributeError: Si la méthode n'existe pas
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
        """
        Récupère la config d'un server.
        
        Args:
            server: Nom du server
            
        Returns:
            Configuration du server
        """
        return self.config.get(server, {})