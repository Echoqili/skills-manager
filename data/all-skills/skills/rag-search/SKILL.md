---
name: Rag Search
slug: rag-search
description: 基于向量检索的本地知识库搜索技能，支持文档嵌入、语义搜索、混合检索和答案生成。
category: ai-product
source: clawhub
---

# RAG Search

Local knowledge base search via RAG (Retrieval-Augmented Generation). Use to **search and query your own documents** with semantic understanding.

## When to Use

- Q&A over internal documentation
- Search across large codebases or wikis
- Customer support from knowledge base
- Private data that can't go to cloud APIs

## Architecture

```
Documents → Chunking → Embedding → Vector Store
                                       ↓
Query → Embedding → Similarity Search → Context → LLM → Answer
```

## Setup

```python
# 1. Install dependencies
pip install langchain chromadb sentence-transformers

# 2. Index documents
from langchain.document_loaders import DirectoryLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.embeddings import HuggingFaceEmbeddings
from langchain.vectorstores import Chroma

loader = DirectoryLoader('./docs', glob="**/*.md")
docs = loader.load()

splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
chunks = splitter.split_documents(docs)

embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
vectorstore = Chroma.from_documents(chunks, embeddings, persist_directory="./chroma_db")
```

## Hybrid Search

```python
# Combine semantic + keyword search
from langchain.retrievers import EnsembleRetriever
from langchain.retrievers import BM25Retriever

bm25 = BM25Retriever.from_documents(chunks)
semantic = vectorstore.as_retriever(search_kwargs={"k": 5})

hybrid = EnsembleRetriever(
    retrievers=[bm25, semantic],
    weights=[0.3, 0.7]
)
```

## Best Practices

1. Chunk size: 200-500 tokens for factual Q&A, 500-1000 for synthesis
2. Overlap: 10-20% to avoid cutting mid-sentence
3. Metadata filtering: tag docs by type, date, source
4. Reranking: use cross-encoder to rerank top-20 → top-5
