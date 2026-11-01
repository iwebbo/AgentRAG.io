<img width="600" height="600" alt="agentragio" src="https://github.com/user-attachments/assets/93dfaf79-24a1-439b-9c63-724917a30554" />

# AgentRAG.io
**AgentRAG.io is a self-hosted, a RAG-Powered Intelligence, a MCP Integration, multi-provider platform featuring SSH & WinRM remote execution. It allows you to modularize your infrastructure and operational workflows by instantiating complex autonomous agents using a single file, scheduling basic task or Agent - with LLMJudge**

![License](https://img.shields.io/badge/MIT-00599C?style=for-the-badge&logo=MIT&logoColor=black)
![Python](https://img.shields.io/badge/Python-4EAA25?style=for-the-badge&logo=Python&logoColor=black)
![FastAPI](https://img.shields.io/badge/FastAPI-4EAA25?style=for-the-badge&logo=FastAPI&logoColor=black)
![React](https://img.shields.io/badge/React-4EAA25?style=for-the-badge&logo=React&logoColor=black)
![Docker](https://img.shields.io/badge/Docker-0078D6?style=for-the-badge&logo=Docker&logoColor=black)
![Opensearch](https://img.shields.io/badge/Opensearch-0078D6?style=for-the-badge&logo=Opensearch&logoColor=black)
![ChromaDB](https://img.shields.io/badge/ChromaDB-0078D6?style=for-the-badge&logo=ChromaDB&logoColor=black)
![RAG](https://img.shields.io/badge/RAG-4A69BD?style=for-the-badge&logo=ChromaDB&logoColor=black)
![Agents](https://img.shields.io/badge/Agents-2ECC71?style=for-the-badge&logo=ChromaDB&logoColor=black)
![Scheduler](https://img.shields.io/badge/Scheduler-F39C12?style=for-the-badge&logo=ChromaDB&logoColor=black)
![LLMJudge](https://img.shields.io/badge/LLMJudge-v0.0.1-0078D6?style=for-the-badge&logo=ChromaDB&logoColor=black)
---
[![Version](https://img.shields.io/badge/Version-v1.1.90-green?style=for-the-badge&logo=github)](http://gitea.aecoding.local:3000/kiki/AgentRAG.io/releases/tag/v1.1.90)
---

## Overview

AgentRAG.io extends RAG.io with autonomous MCP agents that combine RAG intelligence with external tool execution. Built for enterprises and developers who need AI that acts, not just answers.

- **Answer verification (LLM judge)**: Every chat and RAG chat answer is checked before or after delivery: deterministic checks first (empty/truncated/looping output, `[SOURCE n]` citations, retrieval relevance, code via `ast` and `ruff`, JSON/YAML, expected schema), then an optional LLM judge that gets the sources and earlier findings as evidence and only blocks when confident. Three delivery modes: `off`, `annotate` (default: stream first, verdict after) and `gate` (buffer, verify, regenerate up to `VERIFY_MAX_ROUNDS` times, then deliver the best version). The verdict is returned as an SSE event and stored with the message.
- **Scheduler**: Schedule existing agents (deterministic, fixed arguments) or simple LLM prompts on a cron-based frequency, with per-task approval modes (manual / auto / skip-all) and result delivery by in-app notification or email.
- **Skill-Based Agents**: Instantiate any agent from a single .md file — define purpose, MCP servers, and RAG context in frontmatter YAML, register via API, run immediately.
- **Remote Execution**: Operate Linux servers over SSH (Nginx, Apache, Docker, Kubernetes, PostgreSQL, MySQL) and Windows servers over WinRM (IIS, SQL Server, PowerShell) — credentials resolved securely from DB, never in plain config.
- **Built-in Agent Library**: Code generation, branch code review, legal advisory, accounting automation, travel planning, email management, web search — ready out of the box.
- **RAG-Powered Intelligence**: Every agent leverages your document knowledge base for context-aware decisions — architecture docs, runbooks, contracts, standards, or any indexed content.
- **MCP Integration**: Seamless connection to GitHub, Jira, Slack, testing frameworks, linters, WinRM, SSH ...
- **Vector DB**: ChromaDB, Opensearch
- **Real-Time Streaming**: Progressive agent execution with live logs and status updates
- **Fine-Grained Control**: Configure agent behavior, timeouts, retries, and MCP server access
- **Project-Based Organization**: Isolate documents, conversations, and agent workflows by project

## Core AgentRAG Features (from RAG.io)

All the RAG.io features remain unchanged:

#### **Document Processing**
- **Supported Formats**: PDF, DOCX, TXT, MD, HTML, CSV, JSON (50+ file types)
- **Smart Chunking**: Adaptive chunk size (100-2000 tokens) with configurable overlap
- **Metadata Extraction**: Automatic filename, page number, and document type tagging
- **Token Tracking**: Real-time token counting for cost estimation
- **Batch Processing**: Background async processing with progress tracking

#### **Semantic Search**
- **Vector Database**: ChromaDB with HNSW indexing, Opensearch
- **Embedding Models**: sentence-transformers/all-MiniLM-L6-v2 (default), OpenAI embeddings
- **Adjustable top-k**: Dynamic retrieval (1-20 chunks) based on model context
- **Distance Scoring**: Cosine similarity with configurable threshold
- **Metadata Filtering**: Filter by document type, date, or custom tags

### **Multi-Provider & Smart Chunking**

- **Multi-Provider LLM Support**: OpenAI, Claude, Gemini, Ollama, vLLM, Ollama, LMStudio, SGLang and 10+ providers
- **Intelligent Document Search**: ChromaDB-powered semantic search
- **Smart Chunking & Embeddings**: Adaptive chunk size with overlap optimization
- **Enterprise Security**: JWT authentication, AES-256 encryption, GDPR compliance

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
| **vLLM** | Custom models | Varies | ✅ | 0.0-2.0 |
| **LMStudio** | Custom models | Varies | ✅ | 0.0-2.0 |
| **Ollama** | Custom models | Varies | ✅ | 0.0-2.0 |
| **SGLang** | Custom models | Varies | ✅ | 0.0-2.0 |

---

## Demo

[![Demo Badge](https://img.shields.io/badge/Screenshot-AgentRAG.io-blue?style=for-the-badge&logo=markdown)](doc/screenshot/guide_image.md)


## MCP Servers

MCP (Model Context Protocol) servers extend agent capabilities by providing structured tool access to external services. Declare servers in your agent config or `.md` frontmatter — the backend resolves credentials and routes tool calls automatically.

> **Documenatation of MCP Guide** :

[![MCP Badge](https://img.shields.io/badge/Documentation-MCP-red?style=for-the-badge&logo=markdown)](doc/mcp/mcp_guide.md)
 
## Agentic - Agent

#### **Agent Capabilities**
- **RAG-Powered Context**: Agents automatically retrieve relevant context from your document knowledge base
- **LLM Integration**: Agents can call LLMs with intelligent prompts and context management
- **MCP Tool Access**: Connect to external services (GitHub, Jira, Slack, linters, test runners, etc.)
- **Multi-Step Workflows**: Orchestrate complex tasks (fetch repo → generate code → test → lint → commit → PR)
- **Real-Time Streaming**: Live execution logs and progress updates via Server-Sent Events
- **Error Handling**: Automatic retries, timeouts, and graceful degradation
- **Token Tracking**: Monitor LLM usage and MCP call counts

> **Documenatation of Guide Agent** :

[![Agent Guide](https://img.shields.io/badge/Documentation-Agents-blue?style=for-the-badge&logo=markdown)](doc/agents/agent_guide.md)

> **Documenatation of Skill Agent** :

[![Agent Skill](https://img.shields.io/badge/Documentation-Example_of_skill_md-blue?style=for-the-badge&logo=markdown)](doc/agents/skill_agent.md)

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

[![.MD](https://img.shields.io/badge/Documentation-Kubernetes-blue?style=for-the-badge&logo=markdown)](https://iwebbo.github.io/AgentRAG.io/)

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
  -e APP_BASE_URL="" \
  -e SMTP_HOST="smtp.gmail.com" \
  -e SMTP_PORT="587" \
  -e SMTP_USER="your_smtp_username@example.com" \
  -e SMTP_PASSWORD="YOUR_SMTP_ACCESS_TOKEN" \
  -e SMTP_FROM="agentragio@aecoding.local" \
  -e SMTP_STARTTLS="true" \
  -e SMTP_USE_SSL="false" \
  -e SMTP_VERIFY_CERT="true" \
  -e VERIFY_MODE="gate" \
  -e VERIFY_JUDGE="auto" \
  -e VERIFY_MAX_ROUNDS="2" \
  -e RAG_MIN_SCORE="0.25" \
  ghcr.io/iwebbo/agentrag.io/backend:latest
```

### Run Frontend
```bash
docker run -d \
  --name agentrag-frontend \
  --network agentrag-network \
  -p 80:80 \
  ghcr.io/iwebbo/agentrag.io/frontend:latest
```

---

## License

This project is licensed under the **MIT License**. See [LICENSE](LICENSE) file for details.

**Built with ❤️ for Community**

⭐ Star us on GitHub if you find this useful!
