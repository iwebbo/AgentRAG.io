"""Git integration for cloning and syncing repositories."""
import asyncio
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime
import logging
from .base_integration import BaseIntegration

logger = logging.getLogger(__name__)

class GitIntegration(BaseIntegration):
    """Clone and sync Git repositories (GitHub, GitLab, Gitea, etc.)."""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.repo_url: str = config['url']
        self.branch: str = config.get('branch', 'main')
        self.auth_token: str = config.get('token')
        self.local_path: Path = Path(config.get('local_path', './data/git_repos'))
        self.file_patterns: List[str] = config.get('patterns', ['*.md', '*.txt', '*.pdf', '*.docx'])
        
    async def connect(self) -> bool:
        """Test repository access."""
        try:
            cmd = ['git', 'ls-remote', self._get_auth_url()]
            result = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await result.communicate()
            return result.returncode == 0
        except Exception as e:
            logger.error(f"Git connect failed: {e}")
            return False
    
    def _get_auth_url(self) -> str:
        """URL with authentication token."""
        if not self.auth_token:
            return self.repo_url
        
        if 'github.com' in self.repo_url:
            return self.repo_url.replace('https://', f'https://{self.auth_token}@')
        elif 'gitlab.com' in self.repo_url:
            return self.repo_url.replace('https://', f'https://oauth2:{self.auth_token}@')
        return self.repo_url
    
    async def fetch_documents(self, project_id: str) -> List[Dict[str, Any]]:
        """Clone/pull and return list of files."""
        repo_name = self._get_repo_name()
        repo_path = self.local_path / project_id / repo_name
        
        if not repo_path.exists():
            await self._clone_repo(repo_path)
        else:
            await self._pull_repo(repo_path)
        
        documents = []
        for pattern in self.file_patterns:
            for file_path in repo_path.rglob(pattern):
                if self._is_valid_file(file_path):
                    documents.append({
                        'path': str(file_path),
                        'name': file_path.name,
                        'size': file_path.stat().st_size,
                        'modified': datetime.fromtimestamp(file_path.stat().st_mtime),
                        'source': 'git',
                        'repo': repo_name
                    })
        
        return documents
    
    async def _clone_repo(self, target_path: Path):
        """Clone repository."""
        target_path.parent.mkdir(parents=True, exist_ok=True)
        cmd = [
            'git', 'clone',
            '--depth', '1',
            '--branch', self.branch,
            self._get_auth_url(),
            str(target_path)
        ]
        
        result = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await result.communicate()
        
        if result.returncode != 0:
            raise Exception(f"Git clone failed: {stderr.decode()}")
        
        logger.info(f"Cloned {self.repo_url} to {target_path}")
    
    async def _pull_repo(self, repo_path: Path):
        """Pull latest changes."""
        cmd = ['git', '-C', str(repo_path), 'pull', 'origin', self.branch]
        
        result = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        await result.communicate()
        
        logger.info(f"Pulled {self.repo_url}")
    
    async def sync(self, project_id: str) -> Dict[str, Any]:
        """Full sync."""
        start = datetime.now()
        documents = await self.fetch_documents(project_id)
        self.last_sync = datetime.now()
        
        return {
            'status': 'success',
            'documents_found': len(documents),
            'duration': (datetime.now() - start).total_seconds(),
            'last_sync': self.last_sync.isoformat()
        }
    
    def _get_repo_name(self) -> str:
        """Extract repo name from URL."""
        return self.repo_url.rstrip('/').split('/')[-1].replace('.git', '')
    
    def _is_valid_file(self, file_path: Path) -> bool:
        """Filter valid files."""
        ignored = {'.git', 'node_modules', '__pycache__', '.venv'}
        return not any(part in ignored for part in file_path.parts)
    
    def is_connected(self) -> bool:
        """Check connection."""
        return self.local_path.exists() and any(self.local_path.iterdir())