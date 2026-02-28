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

## Values.yaml - StorageClass Auto Provisioning
```yaml
# Default values for RAG Multi-Expert Helm chart
nameOverride: ""
fullnameOverride: ""

replicaCount: 1

# Container Registry
registry: ghcr.io
imagePullSecrets: []

# Backend FastAPI configuration
backend:
  enabled: true
  name: backend
  image:
    repository: ghcr.io/iwebbo/AgentRAG.io/backend
    tag: "latest"
    pullPolicy: IfNotPresent
  
  replicas: 2
  
  service:
    type: ClusterIP
    port: 8000
    targetPort: 8000
  
  resources:
    requests:
      memory: "512Mi"
      cpu: "250m"
    limits:
      memory: "2Gi"
      cpu: "1000m"
  
  env:
    - name: LOG_LEVEL
      value: "INFO"
    - name: WORKERS
      value: "4"

# Frontend Vue 3 configuration
frontend:
  enabled: true
  name: frontend
  image:
    repository: ghcr.io/iwebbo/AgentRAG.io/frontend
    tag: "latest"
    pullPolicy: IfNotPresent
  
  replicas: 2
  
  service:
    type: ClusterIP
    port: 80
    targetPort: 80
  
  resources:
    requests:
      memory: "128Mi"
      cpu: "50m"
    limits:
      memory: "256Mi"
      cpu: "250m"

# PostgreSQL configuration
postgres:
  enabled: true
  name: postgres
  image:
    repository: postgres
    tag: "15-alpine"
    pullPolicy: IfNotPresent
  
  service:
    type: ClusterIP
    port: 5432
    targetPort: 5432
  
  storage:
    enabled: true
    size: 10Gi
    className: local-path
    mountPath: /var/lib/postgresql/data
    subPath: postgres
  
  resources:
    requests:
      memory: "512Mi"
      cpu: "250m"
    limits:
      memory: "1Gi"
      cpu: "500m"
  
  database: rag_db
  user: raguser
  password: "changeMeRag123!"

# ChromaDB Vector Store configuration
chroma:
  enabled: true
  name: chroma
  image:
    repository: chromadb/chroma
    tag: "latest"
    pullPolicy: IfNotPresent
  
  service:
    type: ClusterIP
    port: 8001
    targetPort: 8000
  
  storage:
    enabled: true
    className: local-path
    size: 20Gi
    mountPath: /chroma/chroma
  
  resources:
    requests:
      memory: "1Gi"
      cpu: "500m"
    limits:
      memory: "4Gi"
      cpu: "2000m"

# Shared document storage
documents:
  storage:
    enabled: true
    className: local-path
    size: 50Gi
    mountPath: /app/data/documents

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

# Ingress configuration
ingress:
  enabled: true
  className: "nginx"
  annotations:
    nginx.ingress.kubernetes.io/rewrite-target: /
    nginx.ingress.kubernetes.io/proxy-body-size: "100m"
    nginx.ingress.kubernetes.io/proxy-read-timeout: "600"
    nginx.ingress.kubernetes.io/proxy-send-timeout: "600"
  
  hosts:
    - host: rag.local
      paths:
        - path: /
          pathType: Prefix
          service: frontend
          port: 80
        - path: /api
          pathType: Prefix
          service: backend
          port: 8000
  
  tls:
    enabled: false

# Service Account
serviceAccount:
  create: true
  name: "rag-sa"

# Pod Security
podAnnotations: {}
podSecurityContext:
  runAsNonRoot: true
  runAsUser: 1000
  fsGroup: 1000

securityContext:
  allowPrivilegeEscalation: false
  capabilities:
    drop:
      - ALL

# Node selection
nodeSelector: {}
tolerations: []
affinity: {}
```

## Values to be changed with StorageClass manual + PVs
```yaml
postgres:
  storage:
    enabled: true
    size: 10Gi
    className: local-storage  # Manual StorageClass

chroma:
  storage:
    enabled: true
    size: 20Gi
    className: local-storage  # Manual StorageClass

documents:
  storage:
    enabled: true
    size: 50Gi
    className: local-storage  # Manual StorageClass
```

## pv-postgres.yaml
```yaml
apiVersion: v1
kind: PersistentVolume
metadata:
  name: rag-postgres-pv
spec:
  storageClassName: local-storage
  capacity:
    storage: 10Gi
  accessModes:
    - ReadWriteOnce
  persistentVolumeReclaimPolicy: Retain
  hostPath:
    path: "/mnt/data/rag-postgres"
    type: DirectoryOrCreate
  nodeAffinity:
    required:
      nodeSelectorTerms:
      - matchExpressions:
        - key: kubernetes.io/hostname
          operator: In
          values:
          - k8s-prod-worker-01
  ```

## pv-chroma.yaml
```yaml
apiVersion: v1
kind: PersistentVolume
metadata:
  name: rag-chroma-pv
spec:
  storageClassName: local-storage
  capacity:
    storage: 20Gi
  accessModes:
    - ReadWriteOnce
  persistentVolumeReclaimPolicy: Retain
  hostPath:
    path: "/mnt/data/rag-chroma"
    type: DirectoryOrCreate
  nodeAffinity:
    required:
      nodeSelectorTerms:
      - matchExpressions:
        - key: kubernetes.io/hostname
          operator: In
          values:
          - k8s-prod-worker-01
```

## pv-documents.yaml
```yaml
apiVersion: v1
kind: PersistentVolume
metadata:
  name: rag-documents-pv
spec:
  storageClassName: local-storage
  capacity:
    storage: 50Gi
  accessModes:
    - ReadWriteMany
  persistentVolumeReclaimPolicy: Retain
  hostPath:
    path: "/mnt/data/rag-documents"
    type: DirectoryOrCreate
  nodeAffinity:
    required:
      nodeSelectorTerms:
      - matchExpressions:
        - key: kubernetes.io/hostname
          operator: In
          values:
          - k8s-prod-worker-01
```

## Apply PVs
```shell
kubectl apply -f pv-postgres.yaml
kubectl apply -f pv-chroma.yaml
kubectl apply -f pv-documents.yaml
# AVANT HELM UPGRADE/INSTALL (créer PVCs pour héberger DB/Vector Store/Documents)
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

## Chart Values

| Parameter | Description | Default |
|-----------|-------------|---------|
| `backend.replicas` | Backend replicas | 2 |
| `frontend.replicas` | Frontend replicas | 2 |
| `backend.image.tag` | Backend image tag | latest |
| `frontend.image.tag` | Frontend image tag | latest |
| `postgres.storage.size` | PostgreSQL volume size | 10Gi |
| `chroma.storage.size` | ChromaDB volume size | 20Gi |
| `documents.storage.size` | Documents volume size | 50Gi |
| `ingress.enabled` | Enable Ingress | true |

## Architecture
```
┌─────────────────────────────────────────────────┐
│              Ingress (Nginx)                    │
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

## Build & Push Flow

1. Push to `backend/**` → GitHub Actions builds and pushes to `ghcr.io`
2. Push to `frontend/**` → GitHub Actions builds and pushes to `ghcr.io`
3. Push to `charts/**` → GitHub Actions packages and publishes chart

## Verification
```bash
# List charts
helm search repo agentragio

# Get values
helm show values agentragio/agentragio

# Dry run
helm install agentragio agentragio/agentragio --dry-run --debug

# Check deployments
kubectl get pods -n agentragio
kubectl get svc -n agentragio
kubectl get pvc -n agentragio
kubectl get ingress -n agentragio
```

## LLM Configuration

LLM providers are configured via the UI after deployment. The application supports:
- Ollama (local)
- OpenAI API
- Anthropic Claude API

Documents for each domain should be uploaded via the web interface.
