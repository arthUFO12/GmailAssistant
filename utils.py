import json
import os

from typing import Union
from pathlib import Path
from google.auth.transport.requests import Request
from google.auth.exceptions import RefreshError
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build, Resource
from googleapiclient.errors import HttpError
import pandas as pd
import numpy as np

SCOPES = ["https://www.googleapis.com/auth/gmail.modify",
        "https://www.googleapis.com/auth/calendar",
        "https://www.googleapis.com/auth/tasks"]

JSON_DIR = 'json_dir' # Insert your Json root directory name here

def update_json(filename: str, key: str, val):

    file = os.path.join(JSON_DIR, filename)

    with open(file, 'r') as f:
        data = json.load(f)

    data[key] = val
    
    with open(file, 'w') as f:
        json.dump(data, f, indent=4)


def get_json_field(filename: str, key: str):

    file = os.path.join(JSON_DIR, filename)

    with open(file, 'r') as f:
        data = json.load(f)

    return data.get(key, None)

def save_email_ids(filename: str, ids: np.ndarray):
    df = pd.DataFrame({ "email_ids": ids})
    df.to_csv(f'./data/{filename}')


def load_email_ids(filename: str) -> np.ndarray:
    if os.path.exists(f'./data/{filename}'):
        df = pd.read_csv(f'./data/{filename}')
        return df['email_ids'].to_numpy()
    
    return np.array([])

def get_creds():
    creds = None

    creds_json = os.path.join(JSON_DIR, "credentials.json")
    token_json = os.path.join(JSON_DIR, "token.json")

    if os.path.exists(token_json):
        creds = Credentials.from_authorized_user_file(token_json, SCOPES)
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except RefreshError:
                flow = InstalledAppFlow.from_client_secrets_file(
                    creds_json, SCOPES
                )
                creds = flow.run_local_server(port=0)
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                creds_json, SCOPES
            )

            creds = flow.run_local_server(port=0)

        with open(token_json, "w") as token:
            token.write(creds.to_json())

    return creds

creds = get_creds()