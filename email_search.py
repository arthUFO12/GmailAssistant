from vertexai.language_models import TextEmbeddingModel

import numpy as np
import faiss
import math
import os

EMBEDDING_SIZE = 3072
INDEX_FILE = 'index.faiss'
model = TextEmbeddingModel.from_pretrained("gemini-embedding-001")

if os.path.exists(INDEX_FILE):
    index = faiss.read_index(INDEX_FILE)
else:
    index = faiss.IndexFlatIP(EMBEDDING_SIZE)

index_list = []

def add_embeddings(text: list[str], ids: list[str]):
    embeddings = model.get_embeddings(text)
    index.add(np.ascontiguousarray(
        np.array([embedding.values for embedding in embeddings], dtype='float32')
    ))

    index_list.extend(ids)
    
def query_index(query: str, k: int) -> list[str]:
    query_embedding = model.get_embeddings([query])[0].values
    D, I = index.search(np.ascontiguousarray(
        np.array(query_embedding, dtype='float32').reshape(1, EMBEDDING_SIZE)
    ), k)

    return [index_list[i] for i in I[0]]



def save_index():
    faiss.write_index(index, INDEX_FILE)