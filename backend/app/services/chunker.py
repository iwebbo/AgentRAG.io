import tiktoken
from typing import List, Dict
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class SmartChunker:
    """Découpage intelligent de texte avec gestion 256K context"""
    
    # Profils de chunking adaptatifs
    PROFILES = {
        "code_analysis": {
            "chunk_size": 8000,      # Gros chunks pour le code
            "overlap": 500,
            "description": "Analyse de code (fichiers complets)"
        },
        "documentation": {
            "chunk_size": 4000,
            "overlap": 400,
            "description": "Documentation technique"
        },
        "standard": {
            "chunk_size": 2000,
            "overlap": 200,
            "description": "Usage standard"
        },
        "project_full": {
            "chunk_size": 32000,     # ✅ ÉNORME pour projets complets
            "overlap": 1000,
            "description": "Projet complet (256K context)"
        }
    }
    
    def __init__(
        self, 
        model: str = "gpt-4", 
        chunk_size: int = 2000, 
        overlap: int = 200
    ):
        """
        chunk_size: tokens par chunk (2000 = ~1500 mots)
        overlap: chevauchement entre chunks pour continuité
        """
        try:
            self.encoding = tiktoken.encoding_for_model(model)
        except KeyError:
            # Fallback sur cl100k_base si modèle inconnu
            self.encoding = tiktoken.get_encoding("cl100k_base")
        
        self.chunk_size = chunk_size
        self.overlap = overlap
        logger.info(f"✅ Chunker initialized: {chunk_size} tokens, {overlap} overlap")
    
    #def _select_profile(self, file_path: str) -> Dict:
    def _select_profile(self, filename: str) -> Dict:
        """Sélection automatique du profil selon l'extension"""
        logger.info(f"🔎 Raw filename received: '{filename}' (type: {type(filename)})")
        #ext = Path(file_path).suffix.lower()
        ext = Path(filename).suffix.lower()
        
        # Code source
        if ext in ['.py', '.js', '.jsx', '.ts', '.tsx', '.java', '.cpp', '.c', '.go', '.rs']:
            profile = self.PROFILES["code_analysis"]
            logger.info(f"📊 Profile selected: code_analysis for {ext}")
            return profile
        
        # Documentation
        elif ext in ['.md', '.txt', '.rst', '.adoc']:
            profile = self.PROFILES["documentation"]
            logger.info(f"📄 Profile selected: documentation for {ext}")
            return profile
        
        # Standard (PDF, DOCX, etc.)
        else:
            profile = self.PROFILES["standard"]
            logger.info(f"📦 Profile selected: standard for {ext}")
            return profile
    
    def chunk_text(self, text: str, metadata: Dict) -> List[Dict]:
        """Split intelligent avec overlap et profil adaptatif"""
        if not text.strip():
            return []
        
        # ✅ Sélection automatique du profil
        profile = self._select_profile(metadata.get('filename', ''))
        chunk_size = profile['chunk_size']
        overlap = profile['overlap']
        
        # Découpage par paragraphes
        paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
        
        chunks = []
        current_chunk = []
        current_tokens = 0
        
        for para in paragraphs:
            para_tokens = len(self.encoding.encode(para))
            
            if current_tokens + para_tokens > chunk_size:
                if current_chunk:
                    # Sauvegarder chunk actuel
                    chunk_text = "\n\n".join(current_chunk)
                    chunks.append({
                        "text": chunk_text,
                        "metadata": {
                            **metadata, 
                            "chunk_index": len(chunks),
                            "profile": profile['description']
                        },
                        "tokens": current_tokens
                    })
                    
                    # Garder overlap pour continuité
                    overlap_paras = self._get_overlap_paragraphs(
                        current_chunk, 
                        overlap
                    )
                    current_chunk = overlap_paras + [para]
                    current_tokens = sum([
                        len(self.encoding.encode(p)) for p in current_chunk
                    ])
                else:
                    # Paragraphe trop long → découpe brutale
                    sub_chunks = self._split_long_paragraph(para, metadata, len(chunks), chunk_size)
                    chunks.extend(sub_chunks)
                    current_chunk = []
                    current_tokens = 0
            else:
                current_chunk.append(para)
                current_tokens += para_tokens
        
        # Dernier chunk
        if current_chunk:
            chunk_text = "\n\n".join(current_chunk)
            chunks.append({
                "text": chunk_text,
                "metadata": {
                    **metadata, 
                    "chunk_index": len(chunks),
                    "profile": profile['description']
                },
                "tokens": current_tokens
            })
        
        logger.info(f"📦 Text split into {len(chunks)} chunks (profile: {profile['description']})")
        return chunks
    
    def _get_overlap_paragraphs(self, paragraphs: List[str], max_tokens: int) -> List[str]:
        """Récupère les derniers paragraphes pour overlap"""
        overlap_paras = []
        overlap_tokens = 0
        
        for para in reversed(paragraphs):
            para_tokens = len(self.encoding.encode(para))
            if overlap_tokens + para_tokens > max_tokens:
                break
            overlap_paras.insert(0, para)
            overlap_tokens += para_tokens
        
        return overlap_paras
    
    def _split_long_paragraph(self, para: str, metadata: Dict, start_index: int, chunk_size: int) -> List[Dict]:
        """Découpe un paragraphe trop long en phrases"""
        sentences = para.split('. ')
        chunks = []
        current_chunk = []
        current_tokens = 0
        
        for sentence in sentences:
            sentence = sentence.strip() + '.'
            sentence_tokens = len(self.encoding.encode(sentence))
            
            if current_tokens + sentence_tokens > chunk_size:
                if current_chunk:
                    chunks.append({
                        "text": " ".join(current_chunk),
                        "metadata": {**metadata, "chunk_index": start_index + len(chunks)},
                        "tokens": current_tokens
                    })
                current_chunk = [sentence]
                current_tokens = sentence_tokens
            else:
                current_chunk.append(sentence)
                current_tokens += sentence_tokens
        
        if current_chunk:
            chunks.append({
                "text": " ".join(current_chunk),
                "metadata": {**metadata, "chunk_index": start_index + len(chunks)},
                "tokens": current_tokens
            })
        
        return chunks