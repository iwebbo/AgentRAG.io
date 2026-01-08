import chromadb
from chromadb.config import Settings
from typing import List, Dict, Optional
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class VectorStore:
    """Interface ChromaDB pour stockage vectoriel"""
    
    def __init__(self, persist_directory: str = "./data/chromadb"):
        self.persist_dir = Path(persist_directory)
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        
        self.client = chromadb.PersistentClient(
            path=str(self.persist_dir),
            settings=Settings(
                anonymized_telemetry=False,
                allow_reset=True
            )
        )
        logger.info(f"✅ ChromaDB initialized at {self.persist_dir}")
        
    def get_or_create_collection(self, project_id: str):
        """Crée une collection par projet"""
        collection_name = f"project_{project_id}".replace("-", "_")
        
        collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={
                "hnsw:space": "cosine",
                "hnsw:construction_ef": 200,
                "hnsw:search_ef": 100
            }
        )
        return collection
    
    def add_documents(
        self,
        project_id: str,
        documents: List[str],
        metadatas: List[Dict],
        ids: List[str],
        embeddings: Optional[List[List[float]]] = None
    ):
        """Ajoute des documents vectorisés"""
        collection = self.get_or_create_collection(project_id)
        
        if embeddings:
            collection.add(
                documents=documents,
                metadatas=metadatas,
                ids=ids,
                embeddings=embeddings
            )
        else:
            # ChromaDB génère les embeddings (si modèle configuré)
            collection.add(
                documents=documents,
                metadatas=metadatas,
                ids=ids
            )
        
        logger.info(f"✅ {len(documents)} chunks added to project {project_id}")
    
    def query(
        self,
        project_id: str,
        query_embedding: List[float],
        n_results: int = 5,
        where: Optional[Dict] = None
    ) -> Dict:
        """Recherche sémantique avec filtres"""
        collection = self.get_or_create_collection(project_id)
        
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            where=where,
            include=["documents", "metadatas", "distances"]
        )
        
        return results
    
    def delete_document(self, project_id: str, document_id: str):
        """Supprime tous les chunks d'un document"""
        collection = self.get_or_create_collection(project_id)
        
        # Récupérer tous les IDs commençant par document_id
        results = collection.get(
            where={"document_id": document_id},
            include=[]
        )
        
        if results['ids']:
            collection.delete(ids=results['ids'])
            logger.info(f"🗑️ Document {document_id} deleted from project {project_id}")
    
    def delete_collection(self, project_id: str):
        """Supprime un projet complet"""
        collection_name = f"project_{project_id}".replace("-", "_")
        try:
            self.client.delete_collection(name=collection_name)
            logger.info(f"🗑️ Collection {collection_name} deleted")
        except Exception as e:
            logger.error(f"Error deleting collection: {e}")
    
    def get_collection_stats(self, project_id: str) -> Dict:
        """Statistiques d'une collection"""
        collection = self.get_or_create_collection(project_id)
        return {
            "count": collection.count(),
            "name": collection.name
        }