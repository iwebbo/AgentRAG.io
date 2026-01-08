from imap_tools import MailBox, AND
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import smtplib
import ssl
from typing import List, Dict, Optional
from datetime import datetime

class EmailService:
    """Service bas niveau IMAP/SMTP"""
    
    def __init__(self, config: dict):
        self.email = config['email']
        self.password = config['password']
        self.imap_host = config.get('imap_host', 'imap.gmail.com')
        self.imap_port = config.get('imap_port', 993)
        self.smtp_host = config.get('smtp_host', 'smtp.gmail.com')
        self.smtp_port = config.get('smtp_port', 587)
    
    def fetch_emails(
        self, 
        folder: str = 'INBOX',
        unread_only: bool = True,
        limit: int = 50,
        since_date: Optional[datetime] = None
    ) -> List[Dict]:
        """Récupère emails via IMAP"""
        
        try:
            with MailBox(self.imap_host).login(self.email, self.password) as mailbox:
                mailbox.folder.set(folder)
                
                # Critères recherche
                criteria = None
                if unread_only:
                    criteria = AND(seen=False)
                if since_date:
                    criteria = AND(date_gte=since_date)
                
                emails = []
                for msg in mailbox.fetch(criteria, limit=limit, reverse=True):
                    emails.append({
                        'uid': msg.uid,
                        'message_id': msg.headers.get('message-id', [''])[0],
                        'from': msg.from_,
                        'to': msg.to,
                        'cc': msg.cc,
                        'subject': msg.subject,
                        'date': msg.date.isoformat(),
                        'text': msg.text or '',
                        'html': msg.html or '',
                        'attachments': [
                            {
                                'filename': att.filename,
                                'size': att.size,
                                'content_type': att.content_type
                            } for att in msg.attachments
                        ],
                        'flags': msg.flags
                    })
                
                return emails
                
        except Exception as e:
            raise Exception(f"Erreur IMAP: {str(e)}")
    
    def mark_as_read(self, uid: str):
        """Marque email comme lu"""
        try:
            with MailBox(self.imap_host).login(self.email, self.password) as mailbox:
                mailbox.flag(uid, ['\\Seen'], True)
            return True
        except Exception as e:
            raise Exception(f"Erreur mark as read: {str(e)}")
    
    def send_email(
        self,
        to: str,
        subject: str,
        body: str,
        reply_to: Optional[str] = None,
        cc: Optional[List[str]] = None,
        html: bool = True
    ) -> Dict:
        """Envoie email via SMTP"""
        
        try:
            # Message
            msg = MIMEMultipart('alternative')
            msg['From'] = self.email
            msg['To'] = to
            msg['Subject'] = subject
            
            if cc:
                msg['Cc'] = ', '.join(cc)
            
            if reply_to:
                msg['In-Reply-To'] = reply_to
                msg['References'] = reply_to
            
            # Corps
            content_type = 'html' if html else 'plain'
            msg.attach(MIMEText(body, content_type, 'utf-8'))
            
            # Envoi SMTP
            context = ssl.create_default_context()
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls(context=context)
                server.login(self.email, self.password)
                server.send_message(msg)
            
            return {
                'status': 'sent',
                'to': to,
                'subject': subject,
                'timestamp': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            raise Exception(f"Erreur SMTP: {str(e)}")