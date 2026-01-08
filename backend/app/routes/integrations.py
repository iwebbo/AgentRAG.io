"""API routes for external integrations (Git, Google Drive) - Per project."""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
from datetime import datetime
from sqlalchemy.orm import Session
import httpx

from app.services.sync_manager import SyncManager
from app.services.git_integration import GitIntegration
from app.services.gdrive_integration import GDriveIntegration
from app.dependencies import get_current_user, get_db
from app.models.integration import Integration

router = APIRouter(prefix="/api/integrations", tags=["integrations"])

# Pydantic models
class GitRepoConfig(BaseModel):
    project_id: str  # UUID du projet
    name: str
    url: str
    branch: str = "main"
    token: Optional[str] = None
    patterns: List[str] = ["*.md", "*.txt", "*.pdf", "*.docx"]

class GitTestConfig(BaseModel):
    url: str
    branch: str = "main"
    token: Optional[str] = None

# ===== NOUVEAUX MODELS GOOGLE DRIVE OAUTH =====
class GDriveConnectConfig(BaseModel):
    """OAuth connection config"""
    project_id: str
    access_token: str
    folder_id: Optional[str] = None

class GDriveImportFiles(BaseModel):
    """Import selected files from picker"""
    project_id: str
    access_token: str
    files: List[Dict[str, Any]]

class SyncRequest(BaseModel):
    domain: str  # project_id
    sources: Optional[List[str]] = None

# ===== GIT ROUTES (INCHANGÉES) =====
@router.post("/git/repos")
async def add_git_repo(
    repo: GitRepoConfig,
    user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Add Git repository to a project."""
    try:
        # Check if integration name already exists for this project
        existing = db.query(Integration).filter(
            Integration.project_id == repo.project_id,
            Integration.name == repo.name
        ).first()
        
        if existing:
            raise HTTPException(
                status_code=400,
                detail=f"Integration '{repo.name}' already exists for this project"
            )
        
        # Create integration record
        integration = Integration(
            project_id=repo.project_id,
            type='git',
            name=repo.name,
            config={
                'url': repo.url,
                'branch': repo.branch,
                'token': repo.token,
                'patterns': repo.patterns,
                'local_path': './data/git_repos'
            },
            enabled=True,
            status='active'
        )
        
        db.add(integration)
        db.commit()
        db.refresh(integration)
        
        return {
            "status": "success",
            "message": f"Repository {repo.name} added to project {repo.project_id}",
            "integration_id": str(integration.id)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/git/test")
async def test_git_connection(
    config: GitTestConfig,
    user = Depends(get_current_user)
):
    """Test Git repository connection."""
    try:
        integration = GitIntegration({
            'url': config.url,
            'branch': config.branch,
            'token': config.token
        })
        connected = await integration.connect()
        
        return {
            "status": "success" if connected else "failed",
            "connected": connected,
            "repo": config.url
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# ===== GOOGLE DRIVE OAUTH ROUTES (NOUVELLES) =====
@router.post("/gdrive/connect")
async def connect_gdrive(
    config: GDriveConnectConfig,
    user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Connect Google Drive with OAuth token."""
    try:
        # Validate OAuth token
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://www.googleapis.com/drive/v3/about?fields=user",
                headers={"Authorization": f"Bearer {config.access_token}"},
                timeout=10.0
            )
            
            if response.status_code != 200:
                raise HTTPException(400, "Invalid Google OAuth token")
            
            user_info = response.json().get('user', {})
            user_email = user_info.get('emailAddress')
        
        # Check if already exists
        existing = db.query(Integration).filter(
            Integration.project_id == config.project_id,
            Integration.type == 'gdrive'
        ).first()
        
        if existing:
            # Update token
            existing.config['access_token'] = config.access_token
            existing.config['folder_id'] = config.folder_id
            existing.config['user_email'] = user_email
            db.commit()
            
            return {
                "status": "success",
                "message": "Google Drive reconnected",
                "user_email": user_email
            }
        
        # Create new integration
        integration = Integration(
            project_id=config.project_id,
            type='gdrive',
            name='gdrive',
            config={
                'access_token': config.access_token,  # ⚠️ Encrypt in production
                'folder_id': config.folder_id,
                'user_email': user_email,
                'local_path': f'./data/gdrive/{config.project_id}'
            },
            enabled=True,
            status='active'
        )
        
        db.add(integration)
        db.commit()
        
        return {
            "status": "success",
            "message": "Google Drive connected",
            "user_email": user_email,
            "integration_id": str(integration.id)
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))


@router.post("/gdrive/import-files")
async def import_gdrive_files(
    data: GDriveImportFiles,
    user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Import selected files from Google Picker."""
    try:
        integration = db.query(Integration).filter(
            Integration.project_id == data.project_id,
            Integration.type == 'gdrive'
        ).first()
        
        if not integration:
            raise HTTPException(404, "Google Drive not connected for this project")
        
        # Download files using OAuth token
        gdrive = GDriveIntegration({
            'access_token': data.access_token,
            'local_path': f'./data/gdrive/{data.project_id}'
        })
        
        downloaded = []
        
        for file in data.files:
            file_path = await gdrive._download_file(file, data.project_id)
            
            if file_path:
                downloaded.append({
                    'name': file['name'],
                    'path': str(file_path),
                    'size': file_path.stat().st_size
                })
        
        return {
            "status": "success",
            "files_downloaded": len(downloaded),
            "files": downloaded
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))


@router.get("/gdrive/status/{project_id}")
async def gdrive_status(
    project_id: str,
    user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Check Google Drive connection status."""
    integration = db.query(Integration).filter(
        Integration.project_id == project_id,
        Integration.type == 'gdrive'
    ).first()
    
    if not integration:
        return {"connected": False}
    
    return {
        "connected": True,
        "user_email": integration.config.get('user_email'),
        "enabled": integration.enabled
    }


@router.delete("/gdrive/{project_id}")
async def disconnect_gdrive(
    project_id: str,
    user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Disconnect Google Drive from project."""
    integration = db.query(Integration).filter(
        Integration.project_id == project_id,
        Integration.type == 'gdrive'
    ).first()
    
    if not integration:
        raise HTTPException(404, "Google Drive not connected")
    
    db.delete(integration)
    db.commit()
    
    return {"status": "success", "message": "Google Drive disconnected"}


# ===== SYNC ROUTES (INCHANGÉES) =====
@router.post("/sync")
async def sync_sources(
    request: SyncRequest,
    user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Sync external sources for a project."""
    try:
        project_id = request.domain
        
        if request.sources:
            # Sync specific sources
            results = []
            for source_name in request.sources:
                result = await SyncManager.sync_specific_source(
                    project_id=project_id,
                    source_name=source_name,
                    db=db
                )
                results.append(result)
            
            total_docs = sum(r.get('documents_processed', 0) for r in results)
            return {
                'status': 'success',
                'project_id': project_id,
                'total_documents': total_docs,
                'sources': {request.sources[i]: results[i] for i in range(len(results))},
                'started': datetime.now().isoformat(),
                'completed': datetime.now().isoformat()
            }
        else:
            # Sync all sources for this project
            sync_result = await SyncManager.sync_project(project_id, db)
            return sync_result
            
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/projects/{project_id}/sources")
async def list_project_sources(
    project_id: str,
    user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List all integrations for a project."""
    integrations = db.query(Integration).filter(
        Integration.project_id == project_id
    ).all()
    
    return [
        {
            'id': str(i.id),
            'name': i.name,
            'type': i.type,
            'enabled': i.enabled,
            'status': i.status,
            'last_sync': i.last_sync.isoformat() if i.last_sync else None,
            'created_at': i.created_at.isoformat()
        }
        for i in integrations
    ]

@router.delete("/integrations/{integration_id}")
async def delete_integration(
    integration_id: str,
    user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete an integration."""
    integration = db.query(Integration).filter(
        Integration.id == integration_id
    ).first()
    
    if not integration:
        raise HTTPException(status_code=404, detail="Integration not found")
    
    db.delete(integration)
    db.commit()
    
    return {"status": "success", "message": "Integration deleted"}

@router.get("/sources")
async def list_sources(
    user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List all configured sources (legacy endpoint)."""
    # Return empty for now, frontend should use /projects/{id}/sources
    return []