# RAG Multi-Expert Helm Charts

Kubernetes deployment chart for AgentRAG.io - Intelligent RAG with Autonomous Agents.

## Add Repository
```bash
helm repo add rag https://iwebbo.github.io/AgentRAG.io/
helm repo update
```

## Install Chart
```bash
helm upgrade --install agentragio agentragio/agentragio \
  --namespace agentragio \
  --create-namespace \
  -f values.yml
  ```

## Values.yaml
```yaml

secrets:
  create: true
  name: rag-secrets
  data:
    DATABASE_URL: "postgresql://raguser:changeMeRag123!@rag-multi-expert-postgres:5432/rag_db"
    POSTGRES_SERVER: "rag-multi-expert-postgres"
    POSTGRES_PORT: "5432"
    POSTGRES_DB: "rag_db"
    POSTGRES_USER: "raguser"
    POSTGRES_PASSWORD: "changeMeRag123!"
    CHROMA_HOST: "rag-multi-expert-chroma"
    CHROMA_PORT: "8001"
    SECRET_KEY: "changeMeSecretKeyForJWT123"
    ENCRYPTION_KEY: "changeMeEncryptionKey123="
    OLLAMA_URL: "http://ollama.default.svc.cluster.local:11434"
    OPENAI_API_KEY: ""
    ANTHROPIC_API_KEY: ""
    # Feature/opeansearchadd
    OPENSEARCH_HOST: "opensearch.domain.local"
    OPENSEARCH_PORT: "9200"
    OPENSEARCH_USER: "admin"
    OPENSEARCH_PASSWORD: "admin"
    OPENSEARCH_USE_SSL: "true"
    OPENSEARCH_VERIFY_CERTS: "false"
    OPENSEARCH_EMBEDDING_DIM: "384"

```

## Prerequisites

- Kubernetes 1.20+
- Helm 3.0+
- Ingress Controller (nginx-ingress)
- StorageClass configured (local-path or local-storage)

## Configuration Files (at repo root)

- `values.yml` - Helm values (mandatory)
- `ingress.yml` - Ingress configuration (optional)

## Deploy with Generic Ansible Pipeline
```bash
ansible-playbook deploy_helm_generic.yml 

use: https://github.com/iwebbo/Ansible/tree/main/roles/deploy_helmchart_stack_standalone
```


## Architecture
```
┌─────────────────────────────────────────────────┐
│              Ingress (Traefik)                    │
│  rag.local → Frontend (/) + Backend (/api)      │
└─────────────────────────────────────────────────┘
             │                    │
┌────────────▼──────────┐  ┌─────▼──────────────┐
│   Frontend (Vue 3)    │  │  Backend (FastAPI) │
│   Port: 80            │  │  Port: 8000        │
└───────────────────────┘  └────────────────────┘
                                   │
            ┌──────────────────────┼──────────────────────┐
            │                      │                      │
┌───────────▼─────────┐ ┌─────────▼────────┐ ┌──────────▼─────────┐
│  PostgreSQL         │ │  ChromaDB         │ │  Documents (PVC)   │
│  Port: 5432         │ │  Port: 8001       │ │  Shared Storage    │
│  PVC: 10Gi          │ │  PVC: 20Gi        │ │  PVC: 50Gi         │
└─────────────────────┘ └───────────────────┘ └────────────────────┘
```

## LLM Configuration

LLM providers are configured via the UI after deployment. The application supports:
- Ollama (local)
- OpenAI API
- Anthropic Claude API

Documents for each domain should be uploaded via the web interface.
