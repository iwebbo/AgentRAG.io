## Opensearch Guide

IMPORTANT : AgentRAG.io need to have some prerequesite to use it. 

**Documentation**:
- Example of create index with mandatory field 
- Example of workflow add data into Opensearch index using DocVector and ask with AgentRAG.IO
- Example of workflow add data into Openserach index using an external API and upload with DocVector and ask to AgentRAG.io 

### 1. Opensearch Mandatory Field Create index

- "embedding": ## Mandatory field to have

```bash
curl -k -X PUT "https://opensearch.local:9200/index-example" \
-u 'user:pwd' \
-H 'Content-Type: application/json' \
-d '{
  "settings": {
    "index": {
      "knn": true,
      "knn.algo_param.ef_search": 100
    }
  },
  "mappings": {
    "properties": {
      "embedding": {
        "type": "knn_vector",
        "dimension": 384,
        "method": {
          "name": "hnsw",
          "space_type": "cosinesimil",
          "engine": "lucene"
        }
      },
      "text_content": { "type": "text" },
      "source_doc": { "type": "keyword" }
    }
  }
}'
```

- "metadata": ## Mandatory structure to have and field

```bash
#Syntax mandatory to have for AgentRAG.io ingestion Opensearch data/index.
#Example : 

    doc_id = f"{category}-{mac.replace(':', '')}"
    doc = {
        "chunk_id": doc_id,
        "content": content_text,
        "embedding": embedding,
        "title": f"Host: {name}",
        "metadata": {
            "source_type": "source_api",
            "ip": ip,
            "mac": mac,
            "is_active": is_active,
            "category": category,
            "created_at": datetime.utcnow().isoformat()
        }
    }
```

---

### 2. Workflow upload/add data for Opensearch index using DocVector.io 

DocVector.io : https://github.com/iwebbo/DocVector 

```bash
git clone https://github.com/iwebbo/DocVector.git

- Install it 
- Use it 

```

```text
Step1 : Upload fichiers      Step2 : Ingestion         Step3 : RAG Queries
        ↓                              ↓                          ↓
┌───────────────────┐       ┌───────────────────┐      ┌──────────────────┐
│  DocVector GUI    │       │  OpenSearch       │      │  AgentRAG.io     │
│                   │       │  Vector Index     │      │                  │
│  [Drop Files]     │──────▶│  knowledge_base   │◀─────│  [Ask Questions] │
│                   │       │                   │      │                  │
└───────────────────┘       └───────────────────┘      └──────────────────┘
```

---

### 3. Workflow upload/add data for Opensearch index using script example and upload/ingest from DocVector API

DocVector.io : https://github.com/iwebbo/DocVector 

```bash
git clone https://github.com/iwebbo/DocVector.git

- Install it 
- Use API to Upload/Ingest data to Opensearch Index. 

```

Extraction API to Markdown file 
```bash
curl -s https://api.local/inventory \
  -H "Authorization: Bearer TOKEN" | \
  jq -r '"# Infrastructure Inventory\n\n" + 
    (.servers[] | "## " + .name + "\n- IP: " + .ip + "\n- Status: " + .status + "\n\n")' \
  > infrastructure.md
```

Example of data 
```bash
# Infrastructure Inventory
## server-01
- IP: 10.0.1.10
- Status: active

## server-02
- IP: 10.0.1.11
- Status: active
```

Upload markdown file to DocVector API
```bash
curl -k -X POST https://docvector.local/api/upload \
  -F "files[]=@infrastructure.md"
```

Ingest into Opensearch with DocVector API
```bash
curl -k -X POST https://docvector.local/api/ingest \
  -H "Content-Type: application/json" \
  -d '{"recreate": false, "auto_cleanup": true}'
```