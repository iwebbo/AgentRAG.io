# Agent Email Pro — Communication & Automation

**Purpose**: Complete management of electronic communications via IMAP/SMTP. Allows reading and sending messages, automatic sorting by categories, configurable automated replies, email tracking (trackers), contact management, and campaign performance reporting.

**Workflow**:
1. Configure the email account via Agent API
2. Initialize IMAP sorting rules
3. Execute scheduled or manual tasks
4. Retrieve statistics
5. Generate reports

---

## Email Account Configuration

### Create Agent Email Pro

**API Endpoint**: `POST /api/agents/`

```bash
curl -X POST http://IP:8000/api/agents/ \
-H "Authorization: Bearer YOUR_TOKEN" \
-H "Content-Type: application/json" \
-d '{
  "name": "[AGENT_NAME]",
  "agent_type": "email_expert",
  "config": {
    "llm_provider": "ollama",
    "llm_model": "mistralai/mistral-nemo:latest",
    "llm_temperature": 0.6,
    "email_config": {
      "email": "[EMAIL]",
      "password": "[PASSWORD]",
      "imap_host": "[IMAP_HOST]",
      "imap_port": 993,
      "smtp_host": "[SMTP_HOST]",
      "smtp_port": 587,
      "auto_categorize": true,
      "auto_reply_enabled": false,
      "signature": "[SIGNATURE]",
      "default_tone": "[TONE]",
      "language": "[LANGUAGE]"
    }
  }
}'
```

---

## Detailed Configuration

### LLM Parameters (Large Language Model)

| Parameter | Default Value | Description |
|------------|---------------|-------------|
| `llm_provider` | `ollama` | LLM Provider |
| `llm_model` | `mistralai/mistral-nemo:latest` | Model used |
| `llm_temperature` | `0.6` | Creativity (0 = deterministic, 1 = random) |

### IMAP/SMTP Parameters

```json
{
  "email": "[EMAIL]",              // Complete email address
  "password": "[PASSWORD]",       // Password or authentication token
  "imap_host": "[IMAP_HOST]",     // IMAP server (e.g., imap.gmail.com)
  "imap_port": 993,               // Secure IMAPS port
  "smtp_host": "[SMTP_HOST]",     // SMTP server (e.g., smtp.gmail.com)
  "smtp_port": 587,              // SMTP TLS/STARTTLS port
}
```

### Feature Parameters

| Parameter | Possible Values | Description |
|------------|-----------------|-------------|
| `auto_categorize` | `true` / `false` | Automatic email sorting by categories |
| `auto_reply_enabled` | `true` / `false` | Automated replies enabled |
| `language` | `"fr"` / `"en"` / etc. | Default communication language |
| `default_tone` | `"professional"`, `"friendly"`, `"casual"` | Tone of generated emails |
