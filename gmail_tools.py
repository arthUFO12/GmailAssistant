import os.path
import random
import base64
import re
import threading
import time

from pathlib import Path
from typing import Union, Callable
from datetime import date
from urllib.parse import urlparse

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build, Resource
from googleapiclient.errors import HttpError

class Email:
    def __init__(self, sender: str, subject: str, text=None):
        self.sender = sender
        self.subject = subject
        self.text = text
    
    def __str__(self):
        return (
            f"sender: {self.sender}\n"
            f"subject: {self.subject}\n"
            f"text: {self.text}"
        )
    
    def __repr__(self):
        return str(self)


# Scopes needed for now
SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]


def print_msg():
    print("mail's here")


def check_for_new_email(gmail: Resource, func: Callable, *args):
    latest_id = gmail.users().getProfile(userId='me').execute()['historyId']
    while True:
        time.sleep(15.)
        new_id = gmail.users().getProfile(userId='me').execute()['historyId']
        if latest_id != new_id:
            func(*args)
            latest_id = new_id
        print("checked email")
        
def start_email_checking(gmail: Resource, func: Callable, *args):
    thread = threading.Thread(target=check_for_new_email, daemon=True, args=(gmail, func, *args))
    thread.start()

def get_creds(creds_dir: Union[Path, str], scopes: list[str]):
    creds = None

    creds_json = os.path.join(creds_dir, "credentials.json")
    token_json = os.path.join(creds_dir, "token.json")

    if os.path.exists(token_json):
        creds = Credentials.from_authorized_user_file(token_json, scopes)
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                creds_json, scopes
            )

            creds = flow.run_local_server(port=0)

        with open(token_json, "w") as token:
            token.write(creds.to_json())

    return creds
    
def init_gmail(creds) -> Resource:
    return build('gmail', 'v1', credentials=creds)

def init_calendar(creds) -> Resource:
    return build('calendar', 'v3', credentials=creds)

def normalize_date(d: Union[date, str]):
    return d.strftime("%Y/%m/%d") if isinstance(d, date) else d

def query_inbox(gmail_service: Resource, start: Union[date, str] = None,
                 end: Union[date,str] = None, sender: str = None, max_results: int = 100) -> list:
    
    start_query = '' if start is None else f'after:{normalize_date(start)} '
    end_query = '' if end is None else f'before:{normalize_date(end)} '
    sender_query = '' if sender is None else f'from:{sender} '
    query = start_query + end_query + sender_query


    results = gmail_service.users().messages().list(userId='me', q=query, maxResults=max_results).execute()
    messages = results.get('messages', [])


    query_results = []

    for msg in messages:
        msg_data = gmail_service.users().messages().get(userId='me', id=msg['id'], format='full').execute()

        payload = msg_data.get('payload', {})
        headers = payload.get('headers', [])
        parts = payload.get('parts', [])

        header_dict = {h['name']: h['value'] for h in headers}

        email = Email(header_dict['From'], header_dict['Subject'])
        body = strip_urls(extract_email_text(payload)).strip()
        email.text = re.sub(r'\n+', '\n', body)
        query_results.append(email)

    return query_results

def strip_urls(text: str) -> str:
    
    return re.sub(r'https?://[^\s]+',replace_helper, text)

def replace_helper(match: re.Match) -> str:
    url = match.group()
    domain = urlparse(url).netloc
    return domain.removeprefix("www.")

def extract_email_text(part):
    if part.get('mimeType') == 'text/plain' and 'data' in part.get('body', {}):
        return base64.urlsafe_b64decode(part['body']['data']).decode('utf-8', errors='replace')
    elif 'parts' in part:
        for sub_part in part['parts']:
            body = extract_email_text(sub_part)
            if body:
                return body
    return None


if __name__ == "__main__":
    creds = get_creds("ArthurCreds", SCOPES)
    gmail = init_gmail(creds)
    start_email_checking(gmail, print_msg)
    print(query_inbox(gmail, start='2025/07/01', end='2025/07/02', max_results=10))



        