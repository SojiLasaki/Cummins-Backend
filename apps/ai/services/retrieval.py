import hashlib
import json
import math
import os
import re
from collections import Counter
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.db import transaction

from apps.ai.models import KnowledgeChunk


TOKEN_PATTERN = re.compile(r"[A-Za-z0-9_]+")
OPENAI_EMBEDDINGS_URL = "https://api.openai.com/v1/embeddings"
OPENAI_EMBEDDING_MODEL = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
FALLBACK_EMBEDDING_DIMENSION = 128


def tokenize(text):
    return [match.group(0).lower() for match in TOKEN_PATTERN.finditer(text or "")]


def split_text_into_chunks(content, chunk_size=120, overlap=20):
    words = (content or "").split()
    if not words:
        return []

    chunk_size = max(int(chunk_size), 1)
    overlap = max(min(int(overlap), chunk_size - 1), 0) if chunk_size > 1 else 0
    step = max(chunk_size - overlap, 1)

    chunks = []
    for start in range(0, len(words), step):
        chunk_words = words[start : start + chunk_size]
        if not chunk_words:
            continue
        chunks.append(" ".join(chunk_words))
        if start + chunk_size >= len(words):
            break
    return chunks


def _normalize_vector(vector):
    if not vector:
        return []
    norm = math.sqrt(sum(value * value for value in vector))
    if norm <= 0:
        return [0.0 for _ in vector]
    return [round(value / norm, 8) for value in vector]


def deterministic_embedding(text, dimensions=FALLBACK_EMBEDDING_DIMENSION):
    tokens = tokenize(text)
    if not tokens:
        tokens = [""]

    vector = [0.0] * int(dimensions)
    for token in tokens:
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        for offset in range(0, 24, 4):
            b1, b2, b3, b4 = digest[offset : offset + 4]
            bucket = ((b1 << 8) | b2) % dimensions
            sign = 1.0 if (b3 % 2 == 0) else -1.0
            magnitude = (float(b4) / 255.0) + 0.5
            vector[bucket] += sign * magnitude

    return _normalize_vector(vector)


def _coerce_vector(candidate):
    if not isinstance(candidate, list) or not candidate:
        return []
    vector = []
    for value in candidate:
        try:
            vector.append(float(value))
        except (TypeError, ValueError):
            return []
    return _normalize_vector(vector)


def _embed_with_openai(texts):
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None

    payload = {
        "model": OPENAI_EMBEDDING_MODEL,
        "input": [text or "" for text in texts],
    }
    request = Request(
        OPENAI_EMBEDDINGS_URL,
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urlopen(request, timeout=20) as response:
            data = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, json.JSONDecodeError, TimeoutError, ValueError):
        return None

    records = data.get("data", [])
    if not isinstance(records, list) or len(records) != len(texts):
        return None
    records = sorted(
        records,
        key=lambda row: row.get("index", 0) if isinstance(row, dict) else 0,
    )

    vectors = []
    for record in records:
        vector = _coerce_vector(record.get("embedding") if isinstance(record, dict) else None)
        if not vector:
            return None
        vectors.append(vector)
    return vectors


def build_embeddings(texts):
    normalized_texts = [text or "" for text in texts]
    if not normalized_texts:
        return [], "none"

    openai_vectors = _embed_with_openai(normalized_texts)
    if openai_vectors:
        return openai_vectors, "openai"

    return [deterministic_embedding(text) for text in normalized_texts], "deterministic"


def _cosine_similarity(left, right):
    if not left or not right or len(left) != len(right):
        return None
    similarity = sum(a * b for a, b in zip(left, right))
    return float(round(similarity, 8))


def rebuild_document_chunks(document, chunk_size=120, overlap=20):
    chunk_texts = split_text_into_chunks(document.content, chunk_size=chunk_size, overlap=overlap)
    embeddings, embedding_source = build_embeddings(chunk_texts)
    chunk_models = [
        KnowledgeChunk(
            document=document,
            chunk_index=index,
            content=chunk_text,
            token_count=len(tokenize(chunk_text)),
            embedding=embeddings[index] if index < len(embeddings) else [],
        )
        for index, chunk_text in enumerate(chunk_texts)
    ]

    with transaction.atomic():
        deleted_chunks, _ = KnowledgeChunk.objects.filter(document=document).delete()
        KnowledgeChunk.objects.bulk_create(chunk_models)

    return {
        "deleted_chunks": deleted_chunks,
        "created_chunks": len(chunk_models),
        "chunk_size": int(chunk_size),
        "overlap": int(overlap),
        "embedding_source": embedding_source,
    }


def keyword_score(text, query_terms, query_text):
    if not query_terms:
        return 0.0
    token_counts = Counter(tokenize(text))
    score = float(sum(token_counts.get(term, 0) for term in query_terms))
    if query_text and query_text.lower() in (text or "").lower():
        score += float(len(query_terms))
    return score


def search_knowledge_chunks(query, limit=20, return_meta=False):
    query_text = (query or "").strip()
    query_terms = tokenize(query_text)
    if not query_terms:
        return {"results": [], "mode": "none", "embedding_source": "none"} if return_meta else []

    limit = max(int(limit), 1)
    query_vectors, embedding_source = build_embeddings([query_text])
    query_vector = query_vectors[0] if query_vectors else []

    rows = []
    chunks = KnowledgeChunk.objects.select_related("document").all()
    for chunk in chunks:
        chunk_vector = _coerce_vector(chunk.embedding)
        cosine = _cosine_similarity(query_vector, chunk_vector) if query_vector else None
        kw_score = keyword_score(chunk.content, query_terms, query_text)

        if cosine is None and kw_score <= 0:
            continue

        rows.append(
            {
                "chunk_id": chunk.id,
                "document_id": chunk.document_id,
                "document_title": chunk.document.title,
                "document_source_uri": chunk.document.source_uri,
                "chunk_index": chunk.chunk_index,
                "token_count": chunk.token_count,
                "score": cosine if cosine is not None else kw_score,
                "cosine_similarity": cosine,
                "keyword_score": kw_score,
                "match_type": "embedding" if cosine is not None else "keyword",
                "content": chunk.content,
            }
        )

    has_embedding_hits = any(row["cosine_similarity"] is not None for row in rows)
    if has_embedding_hits:
        rows.sort(
            key=lambda row: (
                row["cosine_similarity"] is not None,
                row["cosine_similarity"] if row["cosine_similarity"] is not None else float("-inf"),
                row["keyword_score"],
                -row["chunk_index"],
            ),
            reverse=True,
        )
        mode = "embedding"
    else:
        rows = [row for row in rows if row["keyword_score"] > 0]
        rows.sort(key=lambda row: (-row["keyword_score"], row["chunk_index"]))
        mode = "keyword"

    results = rows[:limit]
    if return_meta:
        return {
            "results": results,
            "mode": mode,
            "embedding_source": embedding_source,
        }
    return results
