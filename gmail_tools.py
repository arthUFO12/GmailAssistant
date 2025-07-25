import os.path
import base64
import re
import threading
import time

from pathlib import Path
from typing import Union, Callable
from datetime import date
from urllib.parse import urlparse
from dateutil import parser

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build, Resource
from googleapiclient.errors import HttpError


SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]
gmail = None
map_of_labels = {}
user_email = None

URGENCY_LABELS = [
    "needs_reply",
    "follow_up_required",
    "no_action_required",
]
CATEGORY_LABELS = [
    "work",
    "personal",
    "newsletters",
    "financial",
    "travel",
    "health",
    "orders",
    "events",
    "notifications",
    "spam_or_junk"
]

class Email:
    def __init__(self, sender: str, recipients: list[str], date: date, subject: str, msg_id: str, label_ids: list[str], text=None):
        self.sender = sender
        self.recipients = recipients
        self.date = date
        self.subject = subject
        self.msg_id = msg_id
        self.label_ids = label_ids
        self.text = text

        self.recipients = ['me' if r.strip() == user_email else r for r in self.recipients]
    
    def __str__(self):
        return (
            f"Message from {self.sender} "
            f"to {self.recipients} "
            f"sent on {self.date.strftime("%m/%d/%Y")} "
            f"with subject {self.subject}\n"
            f"text: {self.text}\n"
        )
    
    def __repr__(self):
        return str(self)



# Scopes needed for now

def get_all_label_ids():
    response = gmail.users().labels().list(userId='me').execute()
    labels = response.get('labels', [])
    
    label_map = {label['name']: label['id'] for label in labels}
    
    return label_map
    
def print_msg():
    print("mail's here")


def add_email_label(email: Email, label_name: str):
    label_id = map_of_labels[label_name]
    try:
        gmail.users().messages().modify(
            userId='me',
            id=email.msg_id,
            body={
                'addLabelIds': [label_id]
            }
        ).execute()
    except HttpError as error:
        print(f'An error occurred: {error}')
        return
    email.label_ids.append(label_id)

def remove_email_label(email: Email, label_name: str):
    label_id = map_of_labels[label_name]
    try:
        gmail.users().messages().modify(
            userId='me',
            id=email.msg_id,
            body={
                'removeLabelIds': [label_id]
            }
        ).execute()
    except HttpError as error:
        print(f'An error occurred: {error}')
        return
    email.label_ids.remove(label_id)

def clear_all_labels(email: Email):
    try:
        gmail.users().messages().modify(
            userId='me',
            id=email.msg_id,
            body={
                'removeLabelIds': email.label_ids
            }
        ).execute()
        email.label_ids = []  # Clear local copy too
    except HttpError as error:
        print(f"An error occurred while clearing labels: {error}")

def create_label(label_name: str, color=None):
    label_body = {
        "name": label_name,
        "labelListVisibility": "labelShow",     
        "messageListVisibility": "show",        
    }

    if color:
        label_body["color"] = {
            "textColor": "#000000",
            "backgroundColor": color           
        }

    try: 
        label = gmail.users().labels().create(
            userId='me',
            body=label_body
        ).execute()
    except HttpError as error:
        print(f'An error occurred: {error}')

    return label

def _retrieve_email_from_id(gmail: Resource, id) -> Email:

    msg_data = gmail.users().messages().get(userId='me', id=id, format='full').execute()

    payload = msg_data.get('payload', {})
    headers = payload.get('headers', [])

    header_dict = {h['name']: h['value'] for h in headers}

    email = Email(header_dict['From'], header_dict.get('To', '').split(','), parser.parse(header_dict['Date']).date(),
                  header_dict.get('Subject', None), id, msg_data.get('labelIds', []))
    
    if s := extract_email_text(payload):
        body = strip_urls(s).strip()
        email.text = re.sub(r'\n+', '\n', body)
    else:
        email.text = None
    
    return email

def _retrieve_new_emails(worker_gmail: Resource, history_id) -> list[Email]:
    new_emails = []
    page_token = None
    while True:
        
        results = worker_gmail.users().history().list(
            userId='me',
            startHistoryId=history_id,
            historyTypes=['messageAdded'],
            pageToken=page_token
        ).execute()

        history = results.get('history', {})

        new_email_ids = []
        for update in history:
            for message in update.get('messagesAdded', []):
                new_email_ids.append(message['message']['id'])
        
        for id in new_email_ids:
            new_emails.append(_retrieve_email_from_id(worker_gmail, id))

        page_token = results.get('nextPageToken')
        if not page_token:
            break

    return new_emails


def _check_for_new_email(worker_gmail: Resource, func: Callable, *args):
    
    latest_id = worker_gmail.users().getProfile(userId='me').execute()['historyId']

    while True:
        time.sleep(5.)
        new_id = worker_gmail.users().getProfile(userId='me').execute()['historyId']
        if latest_id != new_id:
            if new_emails := _retrieve_new_emails(worker_gmail, latest_id):
                func(new_emails, *args)
            latest_id = new_id
        print("checked email")
        
        

        
def start_email_checking(creds, func: Callable, *args):
    worker_gmail = build('gmail', 'v1', credentials=creds)
    thread = threading.Thread(target=_check_for_new_email, daemon=False, args=(worker_gmail, func, *args))
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
    
def init_gmail(creds):
    global gmail, user_email

    gmail = build('gmail', 'v1', credentials=creds)
    user_email = gmail.users().getProfile(userId='me').execute()['emailAddress']
    ensure_required_labels(URGENCY_LABELS, CATEGORY_LABELS)

def normalize_date(d: Union[date, str]) -> str:
    return d.strftime("%Y/%m/%d") if isinstance(d, date) else d


def query_inbox(start: Union[date, str] = None, end: Union[date,str] = None, 
                sender: str = None, max_results: int = 100) -> list[Email]:
    
    start_query = '' if start is None else f'after:{normalize_date(start)} '
    end_query = '' if end is None else f'before:{normalize_date(end)} '
    sender_query = '' if sender is None else f'from:{sender} '
    query = start_query + end_query + sender_query

    
    results = gmail.users().messages().list(userId='me', q=query, maxResults=max_results).execute()

    messages = results.get('messages', [])


    query_results = []

    for msg in messages:
        email = _retrieve_email_from_id(gmail, msg['id'])
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

def ensure_required_labels(urgency_labels, category_labels):
    existing_labels = gmail.users().labels().list(userId='me').execute().get('labels', [])
    existing_names = {label['name']: label['id'] for label in existing_labels}

    # Create urgency labels with red color
    for label in urgency_labels:
        if label not in existing_names:
            result = gmail.users().labels().create(
                userId='me',
                body={
                    'name': label,
                    'labelListVisibility': 'labelShow',
                    'messageListVisibility': 'show',
                    'color': {
                        "backgroundColor": "#c04b37",  # Gmail red
                        "textColor": "#000000"
                    }
                }
            ).execute()
            map_of_labels[label] = result['id']
        else:
            map_of_labels[label] = existing_names[label]

    # Create category labels (default color)
    for label in category_labels:
        if label not in existing_names:
            result = gmail.users().labels().create(
                userId='me',
                body={
                    'name': label,
                    'labelListVisibility': 'labelShow',
                    'messageListVisibility': 'show'
                }
            ).execute()
            map_of_labels[label] = result['id']
        else:
            map_of_labels[label] = existing_names[label]

if __name__ == "__main__":
    creds = get_creds("Creds", SCOPES)
    init_gmail(creds)
    start_email_checking(creds, print_msg)

    emails = query_inbox(start='2025/07/01', max_results=30)
    add_email_label(emails[0], 'Notes')
    print(emails)
    




        