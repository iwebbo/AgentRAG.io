"""Google Drive integration - OAuth User Token (Simple)"""
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
import logging
import httpx
import asyncio

from .base_integration import BaseIntegration

logger = logging.getLogger(__name__)


class GDriveIntegration(BaseIntegration):
    """Google Drive integration using OAuth user token."""
    
    DRIVE_API_URL = "https://www.googleapis.com/drive/v3"
    
    SUPPORTED_TYPES = {
        'application/pdf': '.pdf',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document': '.docx',
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': '.xlsx',
        'application/vnd.google-apps.document': 'gdoc',
        'application/vnd.google-apps.spreadsheet': 'gsheet',
        'text/plain': '.txt',
        'text/markdown': '.md',
    }
    
    EXPORT_FORMATS = {
        'application/vnd.google-apps.document': ('application/vnd.openxmlformats-officedocument.wordprocessingml.document', '.docx'),
        'application/vnd.google-apps.spreadsheet': ('application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', '.xlsx'),
        'application/vnd.google-apps.presentation': ('application/vnd.openxmlformats-officedocument.presentationml.presentation', '.pptx'),
    }
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.access_token: str = config.get('access_token')
        self.folder_id: Optional[str] = config.get('folder_id')
        self.local_path: Path = Path(config.get('local_path', './data/gdrive'))
        self.headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Accept": "application/json"
        }
    
    async def connect(self) -> bool:
        """Test OAuth token validity."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.DRIVE_API_URL}/about?fields=user",
                    headers=self.headers,
                    timeout=10.0
                )
                
                if response.status_code == 200:
                    logger.info("✅ Google Drive connected via OAuth")
                    return True
                else:
                    logger.error(f"❌ Invalid OAuth token: {response.status_code}")
                    return False
        
        except Exception as e:
            logger.error(f"❌ Connection failed: {e}")
            return False
    
    async def fetch_documents(self, project_id: str) -> List[Dict[str, Any]]:
        """List and download documents using OAuth token."""
        documents = []
        
        # List files
        query = f"'{self.folder_id}' in parents and trashed = false" if self.folder_id else "trashed = false"
        files = await self._list_files(query)
        
        logger.info(f"📂 Found {len(files)} files in Google Drive")
        
        # Download files
        for file in files:
            mime_type = file.get('mimeType')
            
            # Skip folders
            if mime_type == 'application/vnd.google-apps.folder':
                continue
            
            # Check if supported
            if mime_type not in self.SUPPORTED_TYPES and mime_type not in self.EXPORT_FORMATS:
                logger.debug(f"⏭️  Skipping unsupported type: {mime_type}")
                continue
            
            # Download
            local_file = await self._download_file(file, project_id)
            
            if local_file:
                documents.append({
                    'path': str(local_file),
                    'name': file['name'],
                    'size': local_file.stat().st_size,
                    'modified': datetime.fromisoformat(file['modifiedTime'].replace('Z', '+00:00')),
                    'source': 'gdrive',
                    'file_id': file['id']
                })
        
        logger.info(f"✅ Downloaded {len(documents)} documents from Google Drive")
        return documents
    
    async def _list_files(self, query: str) -> List[Dict[str, Any]]:
        """List files with pagination."""
        files = []
        page_token = None
        
        async with httpx.AsyncClient() as client:
            while True:
                params = {
                    'q': query,
                    'spaces': 'drive',
                    'fields': 'nextPageToken, files(id, name, mimeType, size, modifiedTime)',
                    'pageSize': 100
                }
                
                if page_token:
                    params['pageToken'] = page_token
                
                response = await client.get(
                    f"{self.DRIVE_API_URL}/files",
                    headers=self.headers,
                    params=params,
                    timeout=30.0
                )
                
                if response.status_code != 200:
                    logger.error(f"Failed to list files: {response.text}")
                    break
                
                data = response.json()
                files.extend(data.get('files', []))
                page_token = data.get('nextPageToken')
                
                if not page_token:
                    break
        
        return files
    
    async def _download_file(self, file: Dict[str, Any], project_id: str) -> Optional[Path]:
        """Download file from Google Drive."""
        file_id = file['id']
        file_name = file['name']
        mime_type = file['mimeType']
        
        target_dir = self.local_path / project_id
        target_dir.mkdir(parents=True, exist_ok=True)
        
        async with httpx.AsyncClient() as client:
            try:
                # Determine URL and file path
                if mime_type in self.EXPORT_FORMATS:
                    # Google Workspace file - export
                    export_mime, ext = self.EXPORT_FORMATS[mime_type]
                    url = f"{self.DRIVE_API_URL}/files/{file_id}/export?mimeType={export_mime}"
                    target_file = target_dir / f"{Path(file_name).stem}{ext}"
                else:
                    # Regular file - download
                    url = f"{self.DRIVE_API_URL}/files/{file_id}?alt=media"
                    target_file = target_dir / file_name
                
                # Download
                response = await client.get(
                    url,
                    headers=self.headers,
                    timeout=120.0
                )
                
                if response.status_code == 200:
                    target_file.write_bytes(response.content)
                    logger.info(f"✅ Downloaded: {file_name}")
                    return target_file
                else:
                    logger.error(f"❌ Download failed ({response.status_code}): {file_name}")
                    return None
            
            except Exception as e:
                logger.error(f"❌ Error downloading {file_name}: {e}")
                return None
    
    async def sync(self, project_id: str) -> Dict[str, Any]:
        """Full sync."""
        start = datetime.now()
        
        try:
            documents = await self.fetch_documents(project_id)
            self.last_sync = datetime.now()
            
            return {
                'status': 'success',
                'documents_found': len(documents),
                'duration': (datetime.now() - start).total_seconds(),
                'last_sync': self.last_sync.isoformat()
            }
        except Exception as e:
            logger.error(f"❌ Sync failed: {e}")
            return {
                'status': 'error',
                'error': str(e),
                'duration': (datetime.now() - start).total_seconds()
            }
    
    def is_connected(self) -> bool:
        """Check if we have a token."""
        return bool(self.access_token)