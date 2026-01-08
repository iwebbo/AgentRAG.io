<img width="600" height="600" alt="agentragio" src="https://github.com/user-attachments/assets/93dfaf79-24a1-439b-9c63-724917a30554" />

# AgentRAG.io - Intelligent RAG with Autonomous Agents

**Enterprise RAG platform with MCP-powered autonomous agents for code generation, legal advisory, accounting, and more**

![License](https://img.shields.io/badge/MIT-00599C?style=for-the-badge&logo=MIT&logoColor=black)
![Python](https://img.shields.io/badge/Python-4EAA25?style=for-the-badge&logo=Python&logoColor=black)
![FastAPI](https://img.shields.io/badge/FastAPI-4EAA25?style=for-the-badge&logo=FastAPI&logoColor=black)
![React](https://img.shields.io/badge/React-4EAA25?style=for-the-badge&logo=React&logoColor=black)
![Docker](https://img.shields.io/badge/Docker-0078D6?style=for-the-badge&logo=Docker&logoColor=black)

## 📋 Table of Contents

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

## 🎯 Overview

AgentRAG.io extends RAG.io with **autonomous MCP agents** that combine RAG intelligence with external tool execution. Built for enterprises and developers who need:

- **🤖 Autonomous Agents**: Code generation, branch review, legal advisory, accounting automation, Email management
- **🔍 RAG-Powered Intelligence**: Agents leverage your document knowledge base for context-aware decisions
- **🔌 MCP Integration**: Seamless connection to GitHub, Jira, Slack, testing frameworks, linters, and more
- **⚡ Real-Time Streaming**: Progressive agent execution with live logs and status updates
- **🎛️ Fine-Grained Control**: Configure agent behavior, timeouts, retries, and MCP server access
- **📚 Project-Based Organization**: Isolate documents, conversations, and agent workflows by project

### Core Platform Features (from RAG.io)

All the powerful RAG features you know and love:

- **Multi-Provider LLM Support**: OpenAI, Claude, Gemini, Ollama, and 10+ providers
- **Intelligent Document Search**: ChromaDB-powered semantic search
- **Smart Chunking & Embeddings**: Adaptive chunk size with overlap optimization
- **Enterprise Security**: JWT authentication, AES-256 encryption, GDPR compliance

---

## 🆕 What's New: MCP Agents

AgentRAG.io adds a powerful **agent layer** on top of RAG.io's document intelligence:

### 🤖 Agent Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                       Agent Layer                           │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐           │
│  │   Code     │  │   Legal    │  │ Accounting │  + More   │
│  │ Generator  │  │  Advisor   │  │  Advisor   │           │
│  └─────┬──────┘  └─────┬──────┘  └─────┬──────┘           │
│        │                │                │                   │
│  ┌─────▼────────────────▼────────────────▼──────┐          │
│  │           MCP Client (Protocol Layer)         │          │
│  └─────┬────────────────┬────────────────┬───────┘          │
│        │                │                │                   │
│  ┌─────▼─────┐   ┌─────▼─────┐   ┌─────▼─────┐            │
│  │  GitHub   │   │   Linter  │   │ Test Runner│  + More   │
│  │  Server   │   │   Server  │   │   Server   │            │
│  └───────────┘   └───────────┘   └───────────┘            │
└─────────────────────────────────────────────────────────────┘
                            ▲
                            │
┌───────────────────────────┼─────────────────────────────────┐
│                     RAG Layer                               │
│  ┌────────────────────────▼──────────────────────────┐     │
│  │  Vector Store (ChromaDB) + LLM Service           │     │
│  │  • Semantic Search                                │     │
│  │  • Context Building                               │     │
│  │  • Multi-Provider LLM                             │     │
│  └───────────────────────────────────────────────────┘     │
└─────────────────────────────────────────────────────────────┘
```

### 🎯 Key Differentiators

| Feature | Traditional RAG | AgentRAG.io |
|---------|----------------|--------------|
| **Document Q&A** | ✅ Semantic search + LLM | ✅ Same |
| **Code Generation** | ❌ Manual copy/paste | ✅ Auto-generate with tests |
| **External Actions** | ❌ No tool access | ✅ GitHub, Jira, Slack, etc. |
| **Autonomous Workflows** | ❌ Single-shot responses | ✅ Multi-step agent execution |
| **Context Awareness** | ✅ RAG context | ✅ RAG + real-time data from MCP |
| **Testing & QA** | ❌ Manual | ✅ Auto-run tests via MCP |

---

## 🖼️ Demo

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

## ✨ Features

### 🤖 Autonomous Agents (NEW)

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

#### 📄 **Document Processing**
- **Supported Formats**: PDF, DOCX, TXT, MD, HTML, CSV, JSON (50+ file types)
- **Smart Chunking**: Adaptive chunk size (100-2000 tokens) with configurable overlap
- **Metadata Extraction**: Automatic filename, page number, and document type tagging
- **Token Tracking**: Real-time token counting for cost estimation
- **Batch Processing**: Background async processing with progress tracking

#### 🔍 **Semantic Search**
- **Vector Database**: ChromaDB with HNSW indexing
- **Embedding Models**: sentence-transformers/all-MiniLM-L6-v2 (default), OpenAI embeddings
- **Adjustable top-k**: Dynamic retrieval (1-20 chunks) based on model context
- **Distance Scoring**: Cosine similarity with configurable threshold
- **Metadata Filtering**: Filter by document type, date, or custom tags

#### 🤖 **Multi-Provider LLM Support**

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


## 🤖 Available Agents

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

## 🛠️ Tech Stack

### Backend (unchanged from RAG.io)
- **Framework**: FastAPI 0.104+ (async, type-safe)
- **Vector DB**: ChromaDB 0.4+ (persistent, HNSW indexing)
- **Database**: PostgreSQL 15+ (production) / SQLite (dev)
- **ORM**: SQLAlchemy 2.0+ (async support)
- **Embeddings**: sentence-transformers (all-MiniLM-L6-v2)
- **Document Processing**: PyPDF2, python-docx, beautifulsoup4
- **Auth**: JWT (PyJWT), AES-256 (cryptography)
- **Streaming**: SSE (Server-Sent Events)

### Agent Layer (NEW)
- **MCP Protocol**: Custom async client for external tool integration
- **Agent Orchestration**: BaseAgent with async generators for streaming
- **Tool Servers**: GitHub, Linter, Test Runner, Document Storage, ERP
- **Workflow Management**: Multi-step execution with error handling and retries

### Frontend (unchanged from RAG.io)
- **Framework**: React 18.2 (Vite)
- **State Management**: Zustand
- **Routing**: React Router v6
- **UI**: Tailwind CSS 3.4
- **Icons**: Lucide React
- **HTTP**: Axios with interceptors
- **Markdown**: react-markdown, react-syntax-highlighter

### Infrastructure
- **Containerization**: Docker + Docker Compose
- **Reverse Proxy**: Nginx (production)
- **Deployment**: Single `docker-compose up`

---

## 📦 Installation

### Prerequisites

```bash
# Required
- Docker 24.0+
- Docker Compose 2.20+
- 8GB RAM minimum (16GB recommended)
- 10GB disk space

# Optional (for local development)
- Python 3.11+
- Node.js 18+
- PostgreSQL 15+
```

### Quick Start (Docker)

```bash
# 1. Clone repository
git clone https://github.com/iwebbo/agentrag.io.git
cd agentrag.io

# 2. Generate secrets
python3 -c "import secrets; print(secrets.token_hex(32))"  # SECRET_KEY
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"  # ENCRYPTION_KEY

# 3. Edit backend/.env with your secrets

# 3.1 Edit backend/.env if (need to be run from VM/PROD Server)
# Change by your hostname.fqdn or IP
CORS_ORIGINS=http://localhost:5173,http://localhost:3000,http://localhost,http://localhost:80

# 3.1 Edit frontend/.env if (need to be run from VM/PROD Server)
# Change by your hostname.fqdn or IP
VITE_API_URL=http://localhost:8000 

# Will be solve in 1.1.0
cd backend/
mkdir -p /app/data/chromadb
chmod -R 777 /app/data

# 4. Start application
docker-compose up -d

# 5. Check status
docker-compose ps

# 6. Access application
# Frontend: http://localhost:3000
# Backend: http://localhost:8000
# API Docs: http://localhost:8000/docs
```

**First-time setup:**
```bash
# Create first user
curl -X POST http://localhost:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","email":"admin@example.com","password":"SecurePass123!"}'

# Login
curl -X POST http://localhost:8000/api/auth/login \
  -d "username=admin&password=SecurePass123!"
```
### Manual Installation (Development)

#### Backend
```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Setup database
python -c "from app.database import init_db; init_db()"

# Run development server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

#### Frontend
```bash
cd frontend

# Install dependencies
npm install

# Configure API URL
echo "VITE_API_URL=http://localhost:8000" > .env.local

# Run development server
npm run dev
```

---

## ⚙️ Configuration

### Agent Configuration (UI)

Navigate to **Agents → Create Agent** to configure:

**Code Generator Agent**:
```json
{
  "name": "Code Generator",
  "type": "code_generator",
  "project_id": "uuid",
  "mcp_servers": ["github", "test_runner", "linter"],
  "config": {
    "repo": "myorg/myrepo",
    "auto_test": true,
    "auto_lint": true,
    "auto_commit": true
  },
  "mcp_config": {
    "github": {
      "token": "ghp_...",
      "repo": "myorg/myrepo"
    }
  }
}
```

**Branch Review Agent**:
```json
{
  "name": "PR Reviewer",
  "type": "branch_code_review",
  "project_id": "uuid",
  "mcp_servers": ["github"],
  "config": {
    "repo": "myorg/myrepo",
    "review_style": "constructive",
    "auto_approve": false
  }
}
```

---

## 📚 API Documentation

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

### RAG & Project APIs (unchanged)

All existing RAG.io APIs remain unchanged:
- `/api/rag/chat/stream` - RAG chat with streaming
- `/api/projects/` - Project management
- `/api/documents/` - Document upload and management
- `/api/providers/` - LLM provider configuration

See full API documentation at `http://localhost:8000/docs`

---

## 💡 Usage Guide

### 1. Create Your First Agent

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

### 2. Execute Agent

```javascript
// Frontend example (React)
const executeAgent = async (agentId, inputData) => {
  const response = await fetch(`/api/agents/${agentId}/execute/stream`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({ input_data: inputData })
  });

  const reader = response.body.getReader();
  const decoder = new TextDecoder();

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    const chunk = decoder.decode(value);
    const lines = chunk.split('\n');

    for (const line of lines) {
      if (line.startsWith('event:')) {
        const eventType = line.substring(6).trim();
        const dataLine = lines[lines.indexOf(line) + 1];
        const data = JSON.parse(dataLine.substring(6));
        
        console.log(`[${eventType}]`, data);
        // Update UI with live logs/progress
      }
    }
  }
};

// Execute code generator
await executeAgent('agent-uuid', {
  prompt: 'Add OAuth2 authentication',
  target_files: ['backend/auth.py']
});
```

### 3. Monitor Agent Execution

Check **Agents → Executions** for:
- Real-time execution logs
- Token usage and costs
- MCP call counts
- Success/failure status
- Generated outputs

---

## 🔧 Development

### Adding a Custom Agent

```python
# backend/app/agents/my_custom_agent.py
from app.agents.base_agent import BaseAgent
from typing import Dict, Any, AsyncGenerator

class MyCustomAgent(BaseAgent):
    """Custom agent for specialized workflow"""
    
    async def execute(self, input_data: Dict[str, Any]) -> AsyncGenerator[Dict[str, Any], None]:
        # 1. Log start
        yield self.log("info", "Starting custom workflow")
        
        # 2. Get RAG context
        context = await self.get_rag_context(
            query=input_data.get("prompt"),
            top_k=5
        )
        yield self.log("info", f"Retrieved {len(context)} context chunks")
        
        # 3. Call MCP tool
        result = await self.call_mcp(
            server="github",
            method="get_pr",
            params={"pr_number": input_data["pr_number"]}
        )
        yield self.log("info", f"Fetched PR #{input_data['pr_number']}")
        
        # 4. Call LLM
        response = await self.call_llm(
            messages=[
                {"role": "system", "content": "You are a helpful assistant"},
                {"role": "user", "content": input_data["prompt"]}
            ],
            temperature=0.7
        )
        yield self.log("info", "LLM response generated")
        
        # 5. Return final result
        yield {
            "type": "result",
            "data": {
                "output": response,
                "context_used": len(context),
                "pr_analyzed": result
            }
        }
```

### Adding a Custom MCP Server

```python
# backend/app/mcp_servers/my_custom_server.py
import httpx
from typing import Dict, Any

class MyCustomMCPServer:
    """MCP Server for custom integration"""
    
    def __init__(self, api_key: str, base_url: str):
        self.api_key = api_key
        self.base_url = base_url
    
    async def my_method(self, param1: str, param2: int) -> Dict[str, Any]:
        """Custom method implementation"""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/endpoint",
                headers={"Authorization": f"Bearer {self.api_key}"},
                params={"param1": param1, "param2": param2}
            )
            response.raise_for_status()
            return response.json()
```

---

## 🤝 Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

**Areas for contribution:**
- New agent types (HR, DevOps, Marketing, etc.)
- Additional MCP servers (GitLab, Bitbucket, Confluence, etc.)
- UI improvements for agent management
- Performance optimizations
- Documentation and examples

---

## 📄 License

This project is licensed under the **MIT License**. See [LICENSE](LICENSE) file for details.

**Built with ❤️ for Community**

⭐ Star us on GitHub if you find this useful!
