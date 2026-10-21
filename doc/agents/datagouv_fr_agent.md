### DataGouv Explorer Agent — Catalog & Discovery

**Purpose**: Comprehensive exploration of the data.gouv.fr catalog via MCP (Model Context Protocol). Enables searching datasets, fetching dataset details and resources, discovering organizations, and browsing thematic topics. Supports both raw data retrieval (`analyze: false`) and AI-powered summaries (`analyze: true`).

**Workflow**:
1. Authenticate to obtain API Token
2. Create the DataGouv Explorer Agent
3. Execute tasks via Search, Dataset, Organization, or Topic modes
4. Retrieve results (datasets, resources, topics)
5. Generate AI summaries (if LLM enabled)

---

## Agent Account Configuration

### Creating the DataGouv Explorer Agent

**API Endpoint**: `POST /api/agents/`

```bash
curl -s -X POST "$BASE/api/agents/" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "[AGENT_NAME]",
    "description": "[DESCRIPTION]",
    "agent_type": "datagouv_explorer",
    "is_active": true,
    "config": {
      "mcp_servers": ["datagouv"],
      "mode": "search",
      "analyze": false,
      "llm_provider": "ollama",
      "llm_model": "mistralai/mistral-nemo:latest",
      "llm_temperature": 0.6,
      "page_size": 10
    },
    "mcp_config": {}
  }' | jq '.id'
```

---

## Detailed Configuration

### LLM Parameters (Large Language Model)

| Parameter | Default Value | Description |
|------------|------------------|-------------|
| `llm_provider` | `ollama` / `lmstudio` | LLM model provider |
| `llm_model` | `mistralai/mistral-nemo:latest` | Model used for analysis |
| `llm_temperature` | `0.6` | Creativity (0 = deterministic, 1 = random) |

### MCP & Mode Parameters

```json
{
  "mcp_servers": ["datagouv"],     // Connected MCP Servers
  "mode": "search",                // Default search mode
  "analyze": false,                // false: raw results / true: AI summary
  "page_size": 10                  // Number of results per page
}
```

### Functionality Parameters

| Parameter | Possible Values | Description |
|------------|-------------------|-------------|
| `analyze` | `true` / `false` | Enable LLM mode for AI summaries |
| `page_size` | `10`, `20`, etc. | Size of the results page |
| `sort` | `title`, `created`, `-last_update` | Sorting results (prefix `-` for descending order) |

---

## Execution Modes

### MODE: `search` — Dataset Search

**Endpoint**: `POST /api/agents/{id}/execute`

#### 2.1 Simple Search

```bash
curl -s -X POST "$BASE/api/agents/$AGENT_ID/execute" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "input_data": {
      "mode": "search",
      "query": "population par commune"
    },
    "trigger": "manual"
  }' | jq '.output_data'
```

#### 2.2 Search with Pagination

```bash
curl -s -X POST "$BASE/api/agents/$AGENT_ID/execute" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "input_data": {
      "mode": "search",
      "query": "population par commune",
      "page": 2,
      "page_size": 5
    },
    "trigger": "manual"
  }' | jq '.output_data.datasets[].title'
```

#### 2.3 Organization-Filtered Search

```bash
curl -s -X POST "$BASE/api/agents/$AGENT_ID/execute" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "input_data": {
      "mode": "search",
      "query": "population",
      "organization": "institut-national-de-la-statistique-et-des-etudes-economiques-insee"
    },
    "trigger": "manual"
  }' | jq '.output_data'
```

#### 2.4 Tag-Filtered Search

```bash
curl -s -X POST "$BASE/api/agents/$AGENT_ID/execute" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "input_data": {
      "mode": "search",
      "query": "emploi",
      "tag": "emploi"
    },
    "trigger": "manual"
  }' | jq '.output_data'
```

#### 2.5 Sorted Search (valid values: `title` | `created` | `last_update` | `reuses` | `followers` | `views`, prefix `-` for descending order)

```bash
# Most recent first
curl -s -X POST "$BASE/api/agents/$AGENT_ID/execute" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "input_data": {
      "mode": "search",
      "query": "budget collectivites",
      "sort": "-created",
      "page_size": 5
    },
    "trigger": "manual"
  }' | jq '.output_data.datasets[] | {title, created_at, url}'
```

#### 2.6 Extracting only slugs (for chaining to mode=dataset)

```bash
curl -s -X POST "$BASE/api/agents/$AGENT_ID/execute" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "input_data": {
      "mode": "search",
      "query": "prix immobilier",
      "page_size": 5
    },
    "trigger": "manual"
  }' | jq '.output_data.datasets[] | {slug, title, resources_count, organization}'
```

---

### MODE: `dataset` — Dataset Detail + Resources

#### 3.1 Fetch by slug

```bash
# The slug comes from the .slug field of a search result
curl -s -X POST "$BASE/api/agents/$AGENT_ID/execute" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "input_data": {
      "mode": "dataset",
      "dataset_id": "5c34944606e3e73d4a551889"
    },
    "trigger": "manual"
  }' | jq '.output_data'
```

#### 3.2 List resource download URLs

```bash
curl -s -X POST "$BASE/api/agents/$AGENT_ID/execute" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "input_data": {
      "mode": "dataset",
      "dataset_id": "population-legale-2021"
    },
    "trigger": "manual"
  }' | jq '.output_data.resources[] | {title, format, url, filesize}'
```

#### 3.3 Filter for CSV resources only

```bash
curl -s -X POST "$BASE/api/agents/$AGENT_ID/execute" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "input_data": {
      "mode": "dataset",
      "dataset_id": "population-legale-2021"
    },
    "trigger": "manual"
  }' | jq '.output_data.resources[] | select(.format == "csv") | {title, url}'
```

#### 3.4 Complete Workflow search → dataset (bash pipeline)

```bash
# Step 1 — retrieve the first slug
SLUG=$(curl -s -X POST "$BASE/api/agents/$AGENT_ID/execute" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"input_data": {"mode": "search", "query": "elections presidentielles", "page_size": 1}, "trigger": "manual"}' \
  | jq -r '.output_data.datasets[0].slug')

echo "Dataset found : $SLUG"

# Step 2 — fetch the complete dataset
curl -s -X POST "$BASE/api/agents/$AGENT_ID/execute" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"input_data\": {\"mode\": \"dataset\", \"dataset_id\": \"$SLUG\"}, \"trigger\": \"manual\"}" \
  | jq '.output_data'
```

---

### MODE: `organization` — Producing Organizations

#### 4.1 Search for an organization

```bash
curl -s -X POST "$BASE/api/agents/$AGENT_ID/execute" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "input_data": {
      "mode": "organization",
      "query": "INSEE"
    },
    "trigger": "manual"
  }' | jq '.output_data.organizations[] | {name, slug, datasets_count, url}'
```

#### 4.2 Direct Fetch by slug

```bash
curl -s -X POST "$BASE/api/agents/$AGENT_ID/execute" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "input_data": {
      "mode": "organization",
      "org_id": "direction-interministerielle-du-numerique"
    },
    "trigger": "manual"
  }' | jq '.output_data.organization'
```

#### 4.3 Workflow: find an org → search its datasets

```bash
# Step 1 — organization slug
ORG_SLUG=$(curl -s -X POST "$BASE/api/agents/$AGENT_ID/execute" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"input_data": {"mode": "organization", "query": "Météo France"}, "trigger": "manual"}' \
  | jq -r '.output_data.organizations[0].slug')

echo "Organization : $ORG_SLUG"

# Step 2 — its datasets
curl -s -X POST "$BASE/api/agents/$AGENT_ID/execute" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"input_data\": {\"mode\": \"search\", \"query\": \"*\", \"organization\": \"$ORG_SLUG\", \"sort\": \"-last_update\"}, \"trigger\": \"manual\"}" \
  | jq '.output_data.datasets[] | {title, last_modified, url}'
```

---

### MODE: `topic` — Thematic Groupings (API v2)

> Data.gouv.fr topics are **groupings of public digital services** produced by DINUM/Simplifions-v2. Each topic exposes an `elements_href` field pointing to its related datasets/services.

#### 5.1 List all topics

```bash
curl -s -X POST "$BASE/api/agents/$AGENT_ID/execute" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "input_data": {
      "mode": "topic"
    },
    "trigger": "manual"
  }' | jq '.output_data.topics[] | {name, slug, organization, elements_total}'
```

#### 5.2 Topics with non-empty elements

```bash
curl -s -X POST "$BASE/api/agents/$AGENT_ID/execute" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "input_data": {
      "mode": "topic"
    },
    "trigger": "manual"
  }' | jq '.output_data.topics[] | select(.elements_total > 0) | {name, slug, elements_total}'
```

#### 5.3 Fetch a specific topic by slug

```bash
# Examples of available slugs: franceconnect-2, annuaire-des-entreprises,
# demarches-simplifiees, bouquet-api-particulier, data-subvention
curl -s -X POST "$BASE/api/agents/$AGENT_ID/execute" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "input_data": {
      "mode": "topic",
      "topic_id": "annuaire-des-entreprises"
    },
    "trigger": "manual"
  }' | jq '.output_data.topic'
```

#### 5.4 Retrieve a topic's elements URL (for direct REST call)

```bash
curl -s -X POST "$BASE/api/agents/$AGENT_ID/execute" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "input_data": {
      "mode": "topic"
    },
    "trigger": "manual"
  }' | jq '.output_data.topics[] | select(.name | contains("FranceConnect")) | .elements_href'
# → https://www.data.gouv.fr/api/2/topics/68da782b81f6385798345db0/elements/?page=1&page_size=20
```

---

## Activating LLM Mode (`analyze: true`)

Update the agent's configuration before executing:

```bash
# PATCH config to activate LLM
curl -s -X PATCH "$BASE/api/agents/$AGENT_ID" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "config": {
      "mcp_servers": ["datagouv"],
      "mode": "search",
      "analyze": true,
      "llm_provider": "ollama",
      "llm_model": "mistral",
      "page_size": 10
    }
  }'

# Execute — output_data.summary will contain the LLM summary
curl -s -X POST "$BASE/api/agents/$AGENT_ID/execute" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "input_data": {
      "mode": "search",
      "query": "accidents de la route"
    },
    "trigger": "manual"
  }' | jq '{total: .output_data.total, summary: .output_data.summary}'
```

---

## `output_data` Response Fields

### mode=search

```json
{
  "mode": "search",
  "query": "population par commune",
  "total": 33,
  "page": 1,
  "page_size": 10,
  "datasets": [
    {
      "id": "...",
      "slug": "population-legale-communes-2020",
      "title": "Population légale des communes",
      "description": "...",
      "url": "https://www.data.gouv.fr/datasets/...",
      "license": "fr-lo",
```
