from sentence_transformers import SentenceTransformer
from typing import List
import torch
import logging

logger = logging.getLogger(__name__)


class EmbeddingManager:
    """Gestionnaire d'embeddings avec sentence-transformers"""
    
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        """
        Modèles disponibles:
        - all-MiniLM-L6-v2: 384 dims, 80MB, rapide
        - all-mpnet-base-v2: 768 dims, 420MB, précis
        - paraphrase-multilingual-MiniLM-L12-v2: 384 dims, multilingue
        """
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.model = SentenceTransformer(model_name, device=self.device)
        logger.info(f"✅ Embedding model loaded: {model_name} on {self.device}")
        
    def encode(self, texts: List[str], batch_size: int = 32) -> List[List[float]]:
        """Génère embeddings pour une liste de textes"""
        if not texts:
            return []
        
        embeddings = self.model.encode(
            texts,
            batch_size=batch_size,
            show_progress_bar=len(texts) > 10,
            convert_to_numpy=True,
            normalize_embeddings=True
        )
        return embeddings.tolist()
    
    def encode_single(self, text: str) -> List[float]:
        """Pour les queries simples"""
        embedding = self.model.encode(
            text,
            convert_to_numpy=True,
            normalize_embeddings=True
        )
        return embedding.tolist()