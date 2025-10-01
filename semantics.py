from data_schemas import Email
from datetime import date
import numpy as np

import faiss
import requests
import os
import google.auth

from google.auth.transport.requests import Request

import utils

# Get credentials
creds, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
creds.refresh(Request())

EMBEDDING_SIZE = 3072
INDEX_FILE = './data/index.faiss'
EMAIL_ID_FILE = 'email_ids.csv'

url = "https://us-central1-aiplatform.googleapis.com/v1/projects/starry-diode-464720-n0/locations/us-central1/publishers/google/models/gemini-embedding-001:predict"

headers = {
    "Authorization": f"Bearer {creds.token}",
    "Content-Type": "application/json"
}

if os.path.exists(INDEX_FILE):
    index = faiss.read_index(INDEX_FILE)
else:
    index = faiss.IndexFlatIP(EMBEDDING_SIZE)

index_list = utils.load_email_ids(EMAIL_ID_FILE)

def parse_embeddings_json(response: requests.Response):
    obj = response.json()
    embeddings_list = []

    for prediction in obj['predictions']:
        embedding = prediction['embeddings']['values']
        embeddings_list.append(embedding)

    return embeddings_list


def add_embeddings(emails: list[Email]):
    global index, index_list

    for i in range(0, len(emails), 10):
        embedding_map = split_texts(emails[i:i+10])
        
        index_list = np.append(index_list, embedding_map[0])
        response = requests.post(url, headers=headers, json= { "instances": [{"content": text} for text in embedding_map[1]] })
        index.add(np.ascontiguousarray(
            np.array(parse_embeddings_json(response), dtype='float32')
        ))
    
def query_index(query: str, k: int) -> list[str]:
    global index, index_list

    response = requests.post(url, headers=headers, json= { "instances": [{"content": query}] })
    query_embedding = parse_embeddings_json(response)[0]
    
    D, I = index.search(np.ascontiguousarray(
        np.array(query_embedding, dtype='float32').reshape(1, EMBEDDING_SIZE)
    ), k)
    return [index_list[i] for i in I[0] if i != -1]

def split_texts(emails: list[Email]):

    embedding_map = ([], [])
    for email in emails:
        for i in range(0, len(email.text), 1900):
            embedding_map[0].append(email.email_id)
            embedding_map[1].append(email.text[i: i + 2000])

    return embedding_map


def save_index():
    faiss.write_index(index, INDEX_FILE)
    utils.save_email_ids(EMAIL_ID_FILE, index_list)

