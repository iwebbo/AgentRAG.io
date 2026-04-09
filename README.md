<img width="600" height="600" alt="agentragio" src="https://github.com/user-attachments/assets/93dfaf79-24a1-439b-9c63-724917a30554" />

# AgentRAG.io - Intelligent RAG with Autonomous Agents

**Enterprise RAG platform with MCP-powered autonomous agents for code generation, legal advisory, accounting, and more**

![License](https://img.shields.io/badge/MIT-00599C?style=for-the-badge&logo=MIT&logoColor=black)
![Python](https://img.shields.io/badge/Python-4EAA25?style=for-the-badge&logo=Python&logoColor=black)
![FastAPI](https://img.shields.io/badge/FastAPI-4EAA25?style=for-the-badge&logo=FastAPI&logoColor=black)
![React](https://img.shields.io/badge/React-4EAA25?style=for-the-badge&logo=React&logoColor=black)
![Docker](https://img.shields.io/badge/Docker-0078D6?style=for-the-badge&logo=Docker&logoColor=black)
![Opensearch](https://img.shields.io/badge/Opensearch-0078D6?style=for-the-badge&logo=Opensearch&logoColor=black)
![ChromaDB](https://img.shields.io/badge/ChromaDB-0078D6?style=for-the-badge&logo=ChromaDB&logoColor=black)

## Table of Contents

- [Overview](#-overview)
- [What's New: MCP Agents](#-whats-new-mcp-agents)
- [Demo](#-demo)
- [Features](#-features)
- [Agent Architecture](#-agent-architecture)
- [Available Agents](#-available-agents)
- [Tech Stack](#-tech-stack)
- [Installation](#-installation)
- [Configuration](#-configuration)
- [API Documentation](#-api-documentation)
- [Usage Guide](#-usage-guide)
- [Development](#-development)
- [Contributing](#-contributing)
- [License](#-license)

---

## Overview

AgentRAG.io extends RAG.io with **autonomous MCP agents** that combine RAG intelligence with external tool execution. Built for enterprises and developers who need:

- **Autonomous Agents**: Code generation, branch review, legal advisory, accounting automation, Email management
- **RAG-Powered Intelligence**: Agents leverage your document knowledge base for context-aware decisions
- **MCP Integration**: Seamless connection to GitHub, Jira, Slack, testing frameworks, linters, and more
- **Real-Time Streaming**: Progressive agent execution with live logs and status updates
- **Fine-Grained Control**: Configure agent behavior, timeouts, retries, and MCP server access
- **Project-Based Organization**: Isolate documents, conversations, and agent workflows by project

### Core Platform Features (from RAG.io)

All the powerful RAG features you know and love:

- **Multi-Provider LLM Support**: OpenAI, Claude, Gemini, Ollama, and 10+ providers
- **Intelligent Document Search**: ChromaDB-powered semantic search
- **Smart Chunking & Embeddings**: Adaptive chunk size with overlap optimization
- **Enterprise Security**: JWT authentication, AES-256 encryption, GDPR compliance

---

## What's New: MCP Agents

AgentRAG.io adds a powerful **agent layer** on top of RAG.io's document intelligence:

### Agent Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                       Agent Layer                           │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐             │
│  │    Code    │  │   Legal    │  │ Accounting │  + More     │
│  │ Generator  │  │  Advisor   │  │  Advisor   │             │
│  └─────┬──────┘  └─────┬──────┘  └─────┬──────┘             │
│        │                │                │                  │
│  ┌─────▼────────────────▼────────────────▼──────┐          │
│  │          MCP Client (Protocol Layer)          │          │
│  └─────┬────────────────┬────────────────┬───────┘          │
│        │                │                │                  │
│  ┌─────▼─────┐   ┌─────▼─────┐   ┌─────▼─────┐              │
│  │   GitHub  │   │   Linter  │   │ Test Runner│  + More     │
│  │   Server  │   │   Server  │   │   Server  │              │
│  └───────────┘   └───────────┘   └───────────┘              │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                        RAG Layer                            │
│  ┌───────────────────────────────────────────────────────┐  │
│  │                 Context & LLM Manager                 │  │
│  │  • Semantic Search Orchestration   • Multi-LLM Prov.  │  │
│  └───────────────┬───────────────────────┬───────────────┘  │
│                  │                       │                  │
│        ┌─────────▼─────────┐   ┌─────────▼─────────┐        │
│        │     ChromaDB      │   │    OpenSearch     │        │
│        │  (Local/Testing)  │   │   (Prod/Scale)    │        │
│        └───────────────────┘   └───────────────────┘        │
└─────────────────────────────────────────────────────────────┘
```

---

## Demo

### 1. Agent Dashboard
<img width="1899" height="905" alt="image" src="https://github.com/user-attachments/assets/f51b43b5-cb34-4273-a60b-f2c8cb33592f" />

### 2. Code Generator Agent in Action
<img width="1901" height="905" alt="image" src="https://github.com/user-attachments/assets/75aa902e-be76-4fab-84dc-224215ac045c" />

### 3. Code Generator Agent in Action Commit & Create new Branch.
<img width="1896" height="906" alt="image" src="https://github.com/user-attachments/assets/22d89d1f-7a1f-41f8-9713-59c8e0b94bf3" />

### 4. Code Review Agent in Action Pull request of Review.
<img width="1918" height="850" alt="image" src="https://github.com/user-attachments/assets/1a7d26ea-8fa4-4bcb-af5d-36b19dc2a79b" />

### 5. RAG Chat Interface (Original RAG.io)
<img width="1719" height="911" alt="Capture d&#39;écran 2025-12-05 235210" src="https://github.com/user-attachments/assets/01661270-926b-4409-8c18-757d0210c835" />

### 6. Document Upload & Processing
<img width="1702" height="905" alt="Capture d&#39;écran 2025-12-05 235411" src="https://github.com/user-attachments/assets/20666ce0-59f0-4a94-aab9-1b9b0448c7d1" />

---

## Features

### Autonomous Agents (NEW)

#### **Agent Capabilities**
- **RAG-Powered Context**: Agents automatically retrieve relevant context from your document knowledge base
- **LLM Integration**: Agents can call LLMs with intelligent prompts and context management
- **MCP Tool Access**: Connect to external services (GitHub, Jira, Slack, linters, test runners, etc.)
- **Multi-Step Workflows**: Orchestrate complex tasks (fetch repo → generate code → test → lint → commit → PR)
- **Real-Time Streaming**: Live execution logs and progress updates via Server-Sent Events
- **Error Handling**: Automatic retries, timeouts, and graceful degradation
- **Token Tracking**: Monitor LLM usage and MCP call counts

#### **Agent Types Available**

| Agent | Use Case | MCP Servers | RAG Context |
|-------|----------|-------------|-------------|
| **Code Generator** | Generate code from natural language | GitHub, Linter, Test Runner | Repository docs |
| **Branch Code Review** | Automated PR review with suggestions | GitHub | Coding standards |
| **Legal Advisor** | Contract analysis, compliance checks | Document storage | Legal database |
| **Accounting Advisor** | Financial analysis, invoice processing | ERP systems | Accounting rules |
| **Web Search** | A sample Agent of Web Search
| **Travel Epert** | Managemenent, analysis, planned your Travel 
| **Email Epert** | analysis, send email with LLM
| *(Custom)* | Build your own specialized agent | Any MCP server | Any project |

### Core RAG Features (from RAG.io)

All the RAG.io features remain unchanged:

#### **Document Processing**
- **Supported Formats**: PDF, DOCX, TXT, MD, HTML, CSV, JSON (50+ file types)
- **Smart Chunking**: Adaptive chunk size (100-2000 tokens) with configurable overlap
- **Metadata Extraction**: Automatic filename, page number, and document type tagging
- **Token Tracking**: Real-time token counting for cost estimation
- **Batch Processing**: Background async processing with progress tracking

#### **Semantic Search**
- **Vector Database**: ChromaDB with HNSW indexing
- **Embedding Models**: sentence-transformers/all-MiniLM-L6-v2 (default), OpenAI embeddings
- **Adjustable top-k**: Dynamic retrieval (1-20 chunks) based on model context
- **Distance Scoring**: Cosine similarity with configurable threshold
- **Metadata Filtering**: Filter by document type, date, or custom tags

#### **Multi-Provider LLM Support**

| Provider | Models | Context Window | Streaming | Temperature |
|----------|--------|----------------|-----------|-------------|
| **OpenAI** | GPT-4, GPT-4-turbo, o1-preview | 8K-128K | ✅ | 0.0-2.0 |
| **Anthropic** | Claude 3.5 Sonnet, Opus, Haiku | 200K | ✅ | 0.0-1.0 |
| **Google** | Gemini 1.5 Pro/Flash, 2.0 | 2M | ✅ | 0.0-2.0 |
| **Ollama** | Llama 3.1, Mistral, Phi-3 | 8K-128K | ✅ | 0.0-2.0 |
| **Groq** | Llama 3, Mixtral | 32K | ✅ | 0.0-2.0 |
| **OpenRouter** | 200+ models | Varies | ✅ | 0.0-2.0 |
| **HuggingFace** | Custom models | Varies | ✅ | 0.0-2.0 |

---

## Installation

### Prerequisites

```bash
# Kubernetes / Helm (production)
- 4 vCPU minimum namespace
- 8GB RAM node minimum (6GB can be usable)
- 12GB RAM for Agent Usage (Legal/Accounting - simultaneous launch )
- 80GB stockage PVC (20Gi Chroma + 10Gi Postgres + 50Gi Documents)

# Docker Compose (dev local)
- Docker 24.0+
- Docker Compose 2.20+
- 6GB RAM minimum (8GB recommended)
- 10GB disk space

# Optionnel (dev mode)
- Python 3.11+
- Node.js 18+
- PostgreSQL 15+
```

### ☸️ **Quick start with Kubernetes** *(Production-ready)*

> **Helm Chart + Documentation**

[ **Documentation Kubernetes officiel** →](https://iwebbo.github.io/AgentRAG.io/)

### ☸️ **Quick Start with Docker**

### Clone the repository
```bash
git clone https://github.com/iwebbo/AgentRAG.io.git
cd agentrag.io
```

### Prepare the Network
```bash
docker network create agentrag-network
```

### Run DB
```bash
docker run -d \
  --name agentrag-db \
  --network agentrag-network \
  -e POSTGRES_USER=myuser \
  -e POSTGRES_PASSWORD=mypassword \
  -e POSTGRES_DB=agentrag_db \
  postgres:15-alpine
```
### Run Backend
```bash
# 2. Generate secrets
python3 -c "import secrets; print(secrets.token_hex(32))"  # SECRET_KEY
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"  # ENCRYPTION_KEY

docker run -d \
  --name agentrag-backend \
  --network agentrag-network \
  --network-alias backend \
  -p 8000:8000 \
  -e SECRET_KEY="SECRET_KEY" \
  -e ALGORITHM="HS256" \
  -e ACCESS_TOKEN_EXPIRE_MINUTES=30 \
  -e REFRESH_TOKEN_EXPIRE_DAYS=7 \
  -e DEBUG="False" \
  -e CORS_ORIGINS="http://192.168.1.110:5173,http://192.168.1.110:3000,http://192.168.1.110,http://192.168.1.110:80" \
  -e ENCRYPTION_KEY="ENCRYPTION_KEY=" \
  -e DATABASE_URL="postgresql://myuser:mypassword@agentrag-db:5432/agentrag_db" \
  -e OPENSEARCH_HOST="opensearch.domain.local" \
  -e OPENSEARCH_PORT="9200" \
  -e OPENSEARCH_USER="admin" \
  -e OPENSEARCH_PASSWORD="passwordtochange" \
  -e OPENSEARCH_USE_SSL="true" \
  -e OPENSEARCH_VERIFY_CERTS="false" \
  -e OPENSEARCH_EMBEDDING_DIM="384" \
  ghcr.io/iwebbo/agentrag.io/backend:sha-fadc6a0
```

### Run Frontend
```bash
docker run -d \
  --name agentrag-frontend \
  --network agentrag-network \
  -p 80:80 \
  ghcr.io/iwebbo/agentrag.io/frontend:sha-fadc6a0
```

---

## Available Agents

### 1. Code Generator Agent

**Purpose**: Generate production-ready code from natural language prompts with automatic testing and quality checks.

**Workflow**:
1. Fetch entire repository via GitHub MCP
2. Embed code files into RAG project (if not already done)
3. Retrieve relevant code context via semantic search
4. Generate code using LLM with context
5. Run tests automatically (pytest, jest, junit)
6. Lint and format code (flake8, eslint, prettier)
7. Commit changes to new branch
8. Optionally create Pull Request

**Configuration**:
```json
{
  "project_id": "uuid",
  "mcp_servers": ["github", "test_runner", "linter"],
  "repo": "owner/repo",
  "target_branch": "ai-feature",
  "base_branch": "main",
  "auto_test": true,
  "auto_lint": true,
  "auto_commit": true,
  "auto_create_pr": false,
  "test_framework": "auto",  // pytest|jest|junit|auto
  "language": "auto"  // python|javascript|typescript|auto
}
```

**Input**:
```json
{
  "prompt": "Add OAuth2 authentication with JWT tokens",
  "target_files": ["backend/auth.py", "backend/middleware.py"],
  "create_new_files": true,
  "test_mode": true,
  "commit_message": "feat: add OAuth2 authentication"
}
```

**Output** (streaming):
```json
{"type": "log", "data": {"message": "Fetching repository...", "level": "info"}}
{"type": "log", "data": {"message": "Retrieved 12 relevant code files from RAG", "level": "info"}}
{"type": "progress", "data": {"step": "generating_code", "percent": 30}}
{"type": "log", "data": {"message": "Generated 234 lines of code", "level": "info"}}
{"type": "log", "data": {"message": "Running tests...", "level": "info"}}
{"type": "log", "data": {"message": "✅ All 15 tests passed", "level": "success"}}
{"type": "result", "data": {"files_created": ["backend/auth.py"], "tests_passed": 15}}
```

**Use Cases**:
- Feature development from natural language specs
- Refactoring large codebases with context awareness
- Automated bug fixes with test coverage
- API endpoint generation with documentation

---

### 2. Branch Code Review Agent

**Purpose**: Automated PR review with intelligent suggestions based on coding standards and best practices.

**Workflow**:
1. Fetch PR details via GitHub MCP
2. Retrieve coding standards from RAG project
3. Analyze changed files with LLM + context
4. Generate review comments
5. Post comments to PR via GitHub MCP
6. Optionally approve/request changes

**Configuration**:
```json
{
  "project_id": "uuid",  // Project with coding standards docs
  "mcp_servers": ["github"],
  "repo": "owner/repo",
  "review_style": "constructive",  // constructive|strict|minimal
  "auto_approve": false,
  "check_tests": true,
  "check_coverage": true
}
```

**Input**:
```json
{
  "pr_number": 123,
  "focus_areas": ["security", "performance", "testing"]
}
```

**Use Cases**:
- Automated first-pass PR reviews
- Enforce coding standards consistently
- Catch security vulnerabilities early
- Reduce manual review load

---

### 3. Legal Advisor Agent

**Purpose**: Contract analysis, compliance checks, and legal document generation.

**Workflow**:
1. Retrieve contract templates and legal precedents from RAG
2. Analyze uploaded contracts via LLM
3. Identify compliance issues
4. Generate redlined versions
5. Suggest improvements

**Configuration**:
```json
{
  "project_id": "uuid",  // Project with legal docs
  "mcp_servers": ["document_storage"],
  "jurisdiction": "US",
  "focus_areas": ["gdpr", "data_privacy", "intellectual_property"]
}
```

**Use Cases**:
- NDA review and generation
- GDPR compliance audits
- Contract risk assessment
- Legal clause recommendations

---

### 4. Accounting Advisor Agent

**Purpose**: Financial analysis, invoice processing, and regulatory compliance.

**Workflow**:
1. Retrieve accounting rules and regulations from RAG
2. Process financial documents via LLM
3. Generate reports and insights
4. Flag compliance issues
5. Suggest corrective actions

**Configuration**:
```json
{
  "project_id": "uuid",  // Project with accounting docs
  "mcp_servers": ["erp_integration"],
  "accounting_standard": "GAAP",  // GAAP|IFRS
  "tax_jurisdiction": "US"
}
```

**Use Cases**:
- Invoice validation and processing
- Financial statement analysis
- Tax compliance checks
- Expense categorization

---

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

---

## API Documentation
```bash
API Docs: http://localhost:8000/docs
```

### Agent API (NEW)

#### Create Agent

```bash
POST /api/agents/
Authorization: Bearer {token}
Content-Type: application/json

{
  "name": "My Code Generator",
  "type": "code_generator",
  "description": "Generates Python code with tests",
  "project_id": "uuid",
  "config": {
    "repo": "myorg/myrepo",
    "auto_test": true
  },
  "mcp_config": {
    "github": {"token": "ghp_..."}
  }
}

Response:
{
  "id": "uuid",
  "name": "My Code Generator",
  "type": "code_generator",
  "status": "idle",
  "created_at": "2024-01-15T10:00:00Z"
}
```

#### Execute Agent (Streaming)

```bash
POST /api/agents/{agent_id}/execute/stream
Authorization: Bearer {token}
Content-Type: application/json

{
  "input_data": {
    "prompt": "Add OAuth2 authentication",
    "target_files": ["backend/auth.py"]
  }
}

Response (Server-Sent Events):
event: log
data: {"level": "info", "message": "Starting code generation..."}

event: progress
data: {"step": "generating_code", "percent": 30}

event: log
data: {"level": "success", "message": "✅ All tests passed"}

event: result
data: {"files_created": ["backend/auth.py"], "tests_passed": 15}

event: done
data: {"execution_id": "uuid", "status": "completed", "tokens_used": 2345}
```

#### List Agents

```bash
GET /api/agents/
Authorization: Bearer {token}

Response:
[
  {
    "id": "uuid",
    "name": "My Code Generator",
    "type": "code_generator",
    "status": "idle",
    "executions_count": 12,
    "last_execution": "2024-01-15T14:30:00Z"
  },
  ...
]
```

#### Get Agent Execution

```bash
GET /api/agents/executions/{execution_id}
Authorization: Bearer {token}

Response:
{
  "id": "uuid",
  "agent_id": "uuid",
  "status": "completed",
  "input_data": {...},
  "result": {...},
  "logs": [...],
  "tokens_used": 2345,
  "mcp_calls": {"github": 5, "test_runner": 3},
  "started_at": "2024-01-15T14:30:00Z",
  "completed_at": "2024-01-15T14:35:00Z"
}
```
---

## Usage Guide

### Create Your First Agent

```bash
# Via UI: Agents → New Agent → Code Generator
# Or via API:
curl -X POST http://localhost:8000/api/agents/ \
  -H "Authorization: Bearer {token}" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "My Code Generator",
    "type": "code_generator",
    "project_id": "uuid",
    "config": {"repo": "myorg/myrepo", "auto_test": true},
    "mcp_config": {"github": {"token": "ghp_..."}}
  }'
```

### Monitor Agent Execution

Check **Agents → Executions** for:
- Real-time execution logs
- Token usage and costs
- MCP call counts
- Success/failure status
- Generated outputs

---

## 📄 License

This project is licensed under the **MIT License**. See [LICENSE](LICENSE) file for details.

**Built with ❤️ for Community**

⭐ Star us on GitHub if you find this useful!
