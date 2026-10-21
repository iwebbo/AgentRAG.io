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