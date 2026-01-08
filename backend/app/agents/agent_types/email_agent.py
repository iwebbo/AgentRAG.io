from app.agents.base_agent import BaseAgent
from app.services.email_service import EmailService
from app.models import Conversation, Message as MessageModel
from typing import Dict, Any, AsyncGenerator, List
from uuid import UUID


class EmailAgent(BaseAgent):
    """Agent email intelligent avec LLM"""
    
    def __init__(
        self,
        agent_id: UUID,
        user_id: UUID,
        config: Dict[str, Any],
        mcp_config: Dict[str, Any],
        db: Any
    ):
        super().__init__(agent_id, user_id, config, mcp_config, db)
        self.email_config = config.get("email_config", {})
        self.email_service = EmailService(self.email_config)
        self.signature = self.email_config.get('signature', '')
        self.default_tone = self.email_config.get('default_tone', 'professional')
    
    async def execute(self, input_data: Dict[str, Any]) -> AsyncGenerator[Dict[str, Any], None]:
        """Point d'entrée principal"""
        
        mode = input_data.get('mode', 'analyze_inbox')
        
        try:
            if mode == 'analyze_inbox':
                async for chunk in self._analyze_inbox_stream(input_data):
                    yield chunk
            
            elif mode == 'send_email':
                result = await self._send_email(input_data)
                yield {"type": "result", "data": result}
            
            elif mode == 'send_email_llm':
                async for chunk in self._send_email_llm_stream(input_data):
                    yield chunk
            
            else:
                raise ValueError(f"Mode inconnu: {mode}")
            
        except Exception as e:
            yield {"type": "error", "data": str(e)}
    
    # ========== MODE 1: ANALYZE INBOX ==========
    
    async def _analyze_inbox_stream(self, input_data: Dict) -> AsyncGenerator[Dict[str, Any], None]:
        """Analyse boîte réception avec LLM"""
        
        limit = input_data.get('limit', 20)
        unread_only = input_data.get('unread_only', True)
        
        yield {'type': 'status', 'data': f'📬 Récupération {limit} emails...'}
        
        # Récupère emails IMAP
        emails = self.email_service.fetch_emails(unread_only=unread_only, limit=limit)
        
        if not emails:
            yield {
                'type': 'result',
                'data': {
                    'total_emails': 0,
                    'emails': [],
                    'message': 'Aucun email trouvé'
                }
            }
            return
        
        yield {'type': 'status', 'data': f'✅ {len(emails)} emails récupérés'}
        yield {'type': 'status', 'data': '🤖 Analyse LLM en cours...'}
        
        # Analyse chaque email avec LLM
        analyzed_data = []
        for idx, email in enumerate(emails, 1):
            yield {'type': 'status', 'data': f'📧 Analyse email {idx}/{len(emails)}...'}
            
            # Analyse LLM de l'email
            analysis = await self._analyze_single_email_with_llm(email)
            
            analyzed_data.append({
                'uid': email['uid'],
                'from': email['from'],
                'to': email['to'],
                'subject': email['subject'],
                'date': email['date'],
                'has_attachments': len(email.get('attachments', [])) > 0,
                'preview': email['text'][:200] if email['text'] else '',
                'llm_analysis': analysis  # ✅ Ajout analyse LLM
            })
        
        yield {'type': 'status', 'data': '✅ Analyse terminée'}
        
        # Génère résumé global
        yield {'type': 'status', 'data': '📊 Génération résumé global...'}
        summary = await self._generate_inbox_summary_with_llm(analyzed_data)
        
        yield {
            'type': 'result',
            'data': {
                'total_emails': len(emails),
                'emails': analyzed_data,
                'summary': summary
            }
        }


    async def _analyze_single_email_with_llm(self, email: Dict) -> Dict:
        """Analyse un email avec LLM"""
        
        # Prompt analyse
        prompt = f"""Analyse cet email et retourne une évaluation structurée.

    EMAIL:
    De: {email['from']}
    À: {email['to']}
    Sujet: {email['subject']}
    Date: {email['date']}
    Corps: {email['text'][:1000]}
    Pièces jointes: {len(email.get('attachments', []))}

    ANALYSE ATTENDUE:
    1. Catégorie: urgent|important|normal|spam|newsletter
    2. Sentiment: positif|neutre|négatif
    3. Action requise: répondre|transférer|archiver|supprimer|planifier_réunion
    4. Priorité: 1-5 (1=faible, 5=urgent)
    5. Résumé: 1 phrase max 100 caractères
    6. Points clés: liste des éléments importants
    7. Langue détectée: fr|en|es|autre

    Réponds en format structuré clair."""
        
        # Créer conversation
        conv = Conversation(
            user_id=self.user_id,
            title=f"Email analysis - {email['subject'][:50]}",
            provider_name=self.config.get("llm_provider", "ollama"),
            model=self.config.get("llm_model", "mistral"),
            temperature=0.3
        )
        self.db.add(conv)
        self.db.flush()
        
        self.db.add(MessageModel(
            conversation_id=conv.id,
            role="user",
            content=prompt
        ))
        self.db.commit()
        
        # Appel LLM
        analysis_text = ""
        async for chunk in self.llm_service.stream_chat(
            self.user_id,
            conv.id,
            "",
            self.config.get("llm_provider", "ollama"),
            self.config.get("llm_model", "mistral"),
            0.3
        ):
            if chunk:
                analysis_text += chunk
        
        # Parse réponse LLM en structure
        return {
            'raw_analysis': analysis_text,
            'analyzed_at': email['date']
        }


    async def _generate_inbox_summary_with_llm(self, analyzed_emails: List[Dict]) -> str:
        """Génère résumé global de la boîte avec LLM"""
        
        # Compte stats
        urgent_count = sum(1 for e in analyzed_emails if 'urgent' in e.get('llm_analysis', {}).get('raw_analysis', '').lower())
        important_count = sum(1 for e in analyzed_emails if 'important' in e.get('llm_analysis', {}).get('raw_analysis', '').lower())
        
        # Top emails par sujet
        top_subjects = [e['subject'] for e in analyzed_emails[:5]]
        
        prompt = f"""Génère un résumé exécutif professionnel de cette boîte de réception.

    STATISTIQUES:
    - Total emails analysés: {len(analyzed_emails)}
    - Emails urgents détectés: {urgent_count}
    - Emails importants: {important_count}

    TOP 5 SUJETS:
    {chr(10).join([f"- {s}" for s in top_subjects])}

    CONSIGNES:
    1. Résumé en 3-4 phrases maximum
    2. Ton professionnel
    3. Mets en avant les actions prioritaires
    4. Format texte simple

    Génère le résumé."""
        
        # Conversation
        conv = Conversation(
            user_id=self.user_id,
            title="Inbox summary",
            provider_name=self.config.get("llm_provider", "ollama"),
            model=self.config.get("llm_model", "mistral"),
            temperature=0.5
        )
        self.db.add(conv)
        self.db.flush()
        
        self.db.add(MessageModel(
            conversation_id=conv.id,
            role="user",
            content=prompt
        ))
        self.db.commit()
        
        # LLM
        summary = ""
        async for chunk in self.llm_service.stream_chat(
            self.user_id,
            conv.id,
            "",
            self.config.get("llm_provider", "ollama"),
            self.config.get("llm_model", "mistral"),
            0.5
        ):
            if chunk:
                summary += chunk
        
        return summary
        
    # ========== MODE 2: SEND EMAIL (sans LLM) ==========
    
    async def _send_email(self, input_data: Dict) -> Dict:
        """Envoie email direct"""
        
        required = ['to', 'subject', 'body']
        for field in required:
            if field not in input_data:
                raise ValueError(f"Champ requis: {field}")
        
        result = self.email_service.send_email(
            to=input_data['to'],
            subject=input_data['subject'],
            body=input_data['body'],
            reply_to=input_data.get('reply_to'),
            cc=input_data.get('cc'),
            html=True
        )
        
        return result
    
    # ========== MODE 3: SEND EMAIL LLM ==========
    
    async def _send_email_llm_stream(self, input_data: Dict) -> AsyncGenerator[Dict[str, Any], None]:
        """Génère email avec LLM puis envoie"""
        
        if 'to' not in input_data:
            yield {'type': 'error', 'data': 'Champ "to" requis'}
            return
        
        to = input_data['to']
        subject = input_data.get('subject', 'Email généré par IA')
        instructions = input_data.get('instructions', '')
        context = input_data.get('context', '')
        auto_send = input_data.get('auto_send', False)
        
        yield {'type': 'status', 'data': '🤖 Génération email avec LLM...'}
        
        # Prompt
        prompt = f"""Tu es un assistant email professionnel. Génère le contenu d'un email.

DESTINATAIRE: {to}
SUJET: {subject}
CONTEXTE: {context}
INSTRUCTIONS: {instructions}

CONSIGNES:
1. Email professionnel et structuré
2. Ton adapté au contexte
3. Format HTML simple
4. Pas de signature (ajoutée automatiquement)

Génère UNIQUEMENT le corps de l'email en HTML."""
        
        # ✅ CRÉER CONVERSATION DB (comme legal_advisor_agent)
        conv = Conversation(
            user_id=self.user_id,
            title=f"Email generation - {subject}",
            provider_name=self.config.get("llm_provider", "ollama"),
            model=self.config.get("llm_model", "mistral"),
            temperature=0.7
        )
        self.db.add(conv)
        self.db.flush()
        
        # Ajouter message user
        self.db.add(MessageModel(
            conversation_id=conv.id,
            role="user",
            content=prompt
        ))
        self.db.commit()
        
        # ✅ APPEL LLM STREAM
        email_body = ""
        async for chunk in self.llm_service.stream_chat(
            self.user_id,
            conv.id,  # ✅ conversation_id
            "",       # ✅ empty string (prompt déjà dans DB)
            self.config.get("llm_provider", "ollama"),
            self.config.get("llm_model", "mistral"),
            0.7
        ):
            if chunk:
                email_body += chunk
                yield {'type': 'stream', 'data': chunk}
        
        # Signature
        if self.signature:
            email_body += f"<br><br>{self.signature}"
        
        draft = {
            'to': to,
            'subject': subject,
            'body': email_body
        }
        
        yield {'type': 'status', 'data': '✅ Email généré'}
        
        # Envoi ou draft
        if auto_send:
            yield {'type': 'status', 'data': '📤 Envoi...'}
            
            send_result = self.email_service.send_email(
                to=draft['to'],
                subject=draft['subject'],
                body=draft['body'],
                html=True
            )
            
            yield {
                'type': 'result',
                'data': {
                    'status': 'sent',
                    'email_sent': send_result,
                    'generated_body': email_body
                }
            }
        else:
            yield {
                'type': 'result',
                'data': {
                    'status': 'draft_ready',
                    'draft': draft
                }
            }