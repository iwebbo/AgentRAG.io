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