from data_schemas import Email

import numpy as np
import faiss
import requests
import os
import google.auth
import numpy
from google.auth.transport.requests import Request

# Get credentials
creds, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
creds.refresh(Request())

EMBEDDING_SIZE = 3072
INDEX_FILE = 'index.faiss'

url = "https://us-central1-aiplatform.googleapis.com/v1/projects/starry-diode-464720-n0/locations/us-central1/publishers/google/models/gemini-embedding-001:predict"

headers = {
    "Authorization": f"Bearer {creds.token}",
    "Content-Type": "application/json"
}

if os.path.exists(INDEX_FILE):
    index = faiss.read_index(INDEX_FILE)
else:
    index = faiss.IndexFlatIP(EMBEDDING_SIZE)

index_list = []

def parse_embeddings_json(response: requests.Response):
    obj = response.json()
    embeddings_list = []

    for prediction in obj['predictions']:
        embedding = prediction['embeddings']['values']
        embeddings_list.append(embedding)

    return embeddings_list


def add_embeddings(emails: list[Email]):
    response = requests.post(url, headers=headers, json= { "instances": [{"content": email} for email in emails] })
    index.add(np.ascontiguousarray(
        np.array(parse_embeddings_json(response), dtype='float32')
    ))

    index_list.extend([email.msg_id for email in emails])
    
def query_index(query: str, k: int) -> list[str]:
    response = requests.post(url, headers=headers, json= { "instances": [{"content": query}] })
    query_embedding = parse_embeddings_json(response)[0]
    D, I = index.search(np.ascontiguousarray(
        np.array(query_embedding, dtype='float32').reshape(1, EMBEDDING_SIZE)
    ), k)

    return [index_list[i] for i in I[0]]


def save_index():
    faiss.write_index(index, INDEX_FILE)