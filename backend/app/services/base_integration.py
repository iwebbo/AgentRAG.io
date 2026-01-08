"""Base interface for external integrations (Git, Google Drive, etc.)."""
from abc import ABC, abstractmethod
from typing import List, Dict, Any
from datetime import datetime

class BaseIntegration(ABC):
    """Base class for all external integrations."""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.last_sync: datetime = None
        self.enabled: bool = config.get('enabled', True)
    
    @abstractmethod
    async def connect(self) -> bool:
        """Test connection to external source."""
        pass
    
    @abstractmethod
    async def fetch_documents(self, project_id: str) -> List[Dict[str, Any]]:
        """Fetch documents from external source."""
        pass
    
    @abstractmethod
    async def sync(self, project_id: str) -> Dict[str, Any]:
        """Full synchronization."""
        pass
    
    def get_status(self) -> Dict[str, Any]:
        """Get integration status."""
        return {
            'enabled': self.enabled,
            'last_sync': self.last_sync.isoformat() if self.last_sync else None,
            'connected': self.is_connected()
        }
    
    @abstractmethod
    def is_connected(self) -> bool:
        """Check if connected."""
        pass