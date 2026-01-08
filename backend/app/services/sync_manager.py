"""Orchestration for multi-source synchronization per project."""
import asyncio
from typing import Dict, List, Any, Optional
from datetime import datetime
import logging
from pathlib import Path
from sqlalchemy.orm import Session

from .git_integration import GitIntegration
from .gdrive_integration import GDriveIntegration

logger = logging.getLogger(__name__)

class SyncManager:
    """Orchestrator for Git + Google Drive → Document processing (per project)."""
    
    @staticmethod
    def _create_integration(integration_type: str, config: Dict[str, Any]):
        """Factory method to create integration instance."""
        if integration_type == 'git':
            return GitIntegration(config)
        elif integration_type == 'gdrive':
            return GDriveIntegration(config)
        else:
            raise ValueError(f"Unknown integration type: {integration_type}")
    
    @staticmethod
    async def sync_project(project_id: str, db: Session) -> Dict[str, Any]:
        """Sync all integrations for a specific project."""
        from app.models.integration import Integration
        
        # Load integrations from DB for THIS project
        integrations = db.query(Integration).filter(
            Integration.project_id == project_id,
            Integration.enabled == True
        ).all()
        
        if not integrations:
            return {
                'status': 'success',
                'project_id': project_id,
                'total_documents': 0,
                'sources': {},
                'message': 'No integrations configured for this project'
            }
        
        results = {
            'project_id': project_id,
            'started': datetime.now().isoformat(),
            'sources': {}
        }
        
        total_processed = 0
        
        for integration_record in integrations:
            try:
                # Create integration instance
                integration = SyncManager._create_integration(
                    integration_record.type,
                    integration_record.config
                )
                
                # Sync and process
                result = await SyncManager._sync_integration(
                    name=integration_record.name,
                    integration=integration,
                    project_id=project_id,
                    db=db
                )
                
                results['sources'][integration_record.name] = result
                total_processed += result.get('documents_processed', 0)
                
                # Update last_sync
                integration_record.last_sync = datetime.now()
                integration_record.status = 'active'
                db.commit()
                
            except Exception as e:
                logger.error(f"Failed to sync {integration_record.name}: {e}")
                results['sources'][integration_record.name] = {
                    'status': 'error',
                    'error': str(e)
                }
                
                integration_record.status = 'error'
                db.commit()
        
        results['total_documents'] = total_processed
        results['completed'] = datetime.now().isoformat()
        
        return results
    
    @staticmethod
    async def sync_specific_source(
        project_id: str,
        source_name: str,
        db: Session
    ) -> Dict[str, Any]:
        """Sync a specific integration for a project."""
        from app.models.integration import Integration
        
        # Load specific integration
        integration_record = db.query(Integration).filter(
            Integration.project_id == project_id,
            Integration.name == source_name
        ).first()
        
        if not integration_record:
            raise ValueError(f"Integration '{source_name}' not found for project {project_id}")
        
        # Create integration instance
        integration = SyncManager._create_integration(
            integration_record.type,
            integration_record.config
        )
        
        # Sync and process
        result = await SyncManager._sync_integration(
            name=integration_record.name,
            integration=integration,
            project_id=project_id,
            db=db
        )
        
        # Update last_sync
        integration_record.last_sync = datetime.now()
        db.commit()
        
        return result
    
    @staticmethod
    async def _sync_integration(
        name: str,
        integration: Any,
        project_id: str,
        db: Session
    ) -> Dict[str, Any]:
        """Sync one integration and process documents."""
        logger.info(f"Starting sync: {name} for project {project_id}")
        
        try:
            if not await integration.connect():
                return {'status': 'error', 'error': 'Connection failed'}
            
            # Fetch documents from source
            documents = await integration.fetch_documents(project_id)
            
            if not documents:
                return {
                    'status': 'success',
                    'documents_found': 0,
                    'documents_processed': 0
                }
            
            # Process documents into database
            processed_count = 0
            
            from app.models import Project, Document
            from app.services.document_processor import DocumentProcessor
            from app.services.chunker import SmartChunker
            from app.services.vector_store import VectorStore
            
            processor = DocumentProcessor()
            vector_store = VectorStore()  # Créer une instance
            project = db.query(Project).filter(Project.id == project_id).first()
            
            if not project:
                raise ValueError(f"Project {project_id} not found")
            
            for doc_info in documents:
                try:
                    # Check if already exists (par filename seulement)
                    existing = db.query(Document).filter(
                        Document.project_id == project_id,
                        Document.filename == doc_info['name']
                    ).first()
                    
                    if existing:
                        logger.info(f"Skipping existing document: {doc_info['name']}")
                        continue
                    
                    # Extract text
                    text = processor.extract_text(Path(doc_info['path']))
                    
                    if not text:
                        logger.warning(f"No text extracted from {doc_info['name']}")
                        continue
                    
                    # Create document record
                    doc_data = {
                        'project_id': project_id,
                        'filename': doc_info['name'],
                        'file_path': str(doc_info['path']),  # ✅ Ajouter le chemin du fichier
                        'file_type': Path(doc_info['name']).suffix.lstrip('.'),
                        'file_size': doc_info['size'],
                        'status': 'processing'
                    }
                    
                    # Ajouter source si le modèle le supporte
                    try:
                        document = Document(**doc_data, source=doc_info['source'])
                    except TypeError:
                        # Le modèle n'a pas de champ 'source'
                        logger.warning("Document model has no 'source' field, skipping")
                        document = Document(**doc_data)
                    
                    db.add(document)
                    db.commit()
                    db.refresh(document)
                    
                    # Chunk text
                    chunker = SmartChunker(
                        chunk_size=project.chunk_size,
                        overlap=project.chunk_overlap
                    )
                    
                    chunks = chunker.chunk_text(text, metadata={
                        'filename': doc_info['name'],
                        'source': doc_info['source'],
                        'project_id': str(project_id)
                    })
                    
                    # Add to vector store (collection par projet)
                    texts = [c["text"] for c in chunks]
                    metadatas = [c["metadata"] for c in chunks]
                    ids = [f"{document.id}_{i}" for i in range(len(chunks))]
                    
                    vector_store.add_documents(
                        project_id=str(project_id),
                        documents=texts,
                        metadatas=metadatas,
                        ids=ids
                    )
                    
                    # Update document status
                    document.status = 'completed'
                    document.chunk_count = len(chunks)
                    document.total_tokens = sum(c["tokens"] for c in chunks)
                    db.commit()
                    
                    processed_count += 1
                    logger.info(f"✅ Processed {doc_info['name']}: {len(chunks)} chunks → project_{project_id}")
                    
                except Exception as e:
                    logger.error(f"Failed to process {doc_info['name']}: {e}")
                    db.rollback()  # ✅ Rollback pour continuer avec les autres documents
                    if 'document' in locals():
                        try:
                            document.status = 'failed'
                            document.error_message = str(e)
                            db.commit()
                        except:
                            db.rollback()
                    continue
            
            return {
                'status': 'success',
                'documents_found': len(documents),
                'documents_processed': processed_count
            }
            
        except Exception as e:
            logger.error(f"Sync failed for {name}: {e}")
            return {'status': 'error', 'error': str(e)}