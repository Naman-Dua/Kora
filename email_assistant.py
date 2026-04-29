import imaplib
import smtplib
import email
from email.message import EmailMessage
import re

from storage import load_setting

# Default server settings
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
IMAP_SERVER = "imap.gmail.com"

def is_email_request(query: str) -> bool:
    query_lower = query.lower()
    return "email" in query_lower or "inbox" in query_lower or "draft an email" in query_lower

def _draft_email(query: str) -> str:
    import ollama
    from settings import get_setting
    import pyperclip
    
    model = get_setting("model_name", "llama3.1:8b")
    prompt = (
        "You are an AI Email Assistant. The user wants to draft an email. "
        f"Based on their request: '{query}', draft a professional, concise email. "
        "Return ONLY the drafted email text (Subject and Body). Do not include any conversational filler."
    )
    
    try:
        response = ollama.generate(model=model, prompt=prompt)
        draft = response["response"].strip()
        pyperclip.copy(draft)
        return f"I have drafted the email and copied it to your clipboard:\n\n{draft}"
    except Exception as e:
        return f"I encountered an error while drafting the email: {e}"

def _check_inbox() -> str:
    email_address = load_setting("email_address", "")
    email_password = load_setting("email_password", "")
    
    if not email_address or not email_password:
        return "I cannot check your inbox because your email credentials are not configured in Kora's database."
    
    try:
        mail = imaplib.IMAP4_SSL(IMAP_SERVER)
        mail.login(email_address, email_password)
        mail.select('inbox')
        
        # Search for unread emails
        status, messages = mail.search(None, 'UNSEEN')
        if status == 'OK':
            unread_ids = messages[0].split()
            count = len(unread_ids)
            return f"You have {count} unread emails in your inbox."
        return "I couldn't fetch your inbox status at this time."
    except Exception as e:
        return f"Failed to check inbox: {str(e)}"

def handle_email_command(query: str) -> dict:
    query_lower = query.lower()
    
    reply = ""
    if "check" in query_lower or "read" in query_lower or "inbox" in query_lower:
        reply = _check_inbox()
    elif "draft" in query_lower or "write" in query_lower or "send" in query_lower:
        reply = _draft_email(query)
    else:
        reply = "I can help you check your inbox or draft an email. What would you like to do?"
        
    return {
        "action": "email",
        "reply": reply
    }
