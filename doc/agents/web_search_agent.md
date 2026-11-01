### 3. Web Search Agent

**Purpose**: Access real-time external information from the internet, extract the content of the relevant pages, and have an LLM analyze each source and produce a cited synthesis. Useful to verify facts, gather up-to-date data points, and feed analysis or decision-making.

**Workflow**:
1. Receive a query (`query` is required).
2. Search with DuckDuckGo (`ddgs`, no API key required), filtered by language and safe-search level.
3. Extract the main content of each result page with `trafilatura` (falls back to the search snippet if the page cannot be fetched).
4. **LLM analysis** (optional): the top `analyze_top_n` results are analyzed one by one through `llm_service` (summary, key points, relevance) with a JSON output and a plain-text fallback.
5. **Synthesis** (optional): a final LLM call produces a global answer citing the analyzed sources.
6. Return a structured result with the sources, per-source analysis, synthesis and execution metadata.

Each step is streamed over SSE (`/api/agents/{id}/execute/stream`) as `log`, `progress` (`analyze`, `synthesize`), `result` and `error` events.

**Configuration**:
```json
{
  "llm_provider": "ollama",        // LLM provider used for analysis and synthesis
  "llm_model": "mistral",          // Model name (prefer a model that reliably outputs JSON, e.g. gpt-oss-20b, qwen)
  "llm_temperature": 0.3,
  "search_config": {
    "max_results": 10,             // Number of search results to fetch
    "language": "en",              // Search region/language
    "safe_search": "moderate",     // Safe-search level
    "extract_content": true,       // Fetch and extract page content (trafilatura)
    "llm_analysis": true,          // Per-result LLM analysis
    "analyze_top_n": 5,            // Number of results sent to the LLM
    "max_content_chars": 6000,     // Content truncation before the LLM call
    "synthesize": true,            // Final synthesis across analyzed sources
    "cleanup_conversations": true  // Delete the temporary conversations created for LLM calls
  }
}
```

**Input (per execution)**:
```json
{
  "query": "latest changes to French VAT rules",
  "max_results": 5,           // optional, overrides search_config
  "language": "fr",           // optional
  "extract_content": true,    // optional
  "llm_analysis": true,       // optional
  "synthesize": true          // optional
}
```
Setting `llm_analysis` to `false` gives a plain search + extraction run (no LLM call, faster, no provider required).

**Output**:
```json
{
  "query": "...",
  "results_count": 5,
  "results": [ { "title": "...", "url": "...", "snippet": "...", "content": "...", "analysis": { ... } } ],
  "synthesis": "...",
  "metadata": {
    "language": "en",
    "safe_search": "moderate",
    "content_extracted": true,
    "llm_analysis": true,
    "llm_analyzed_count": 5,
    "llm_provider": "ollama",
    "llm_model": "mistral",
    "timestamp": "..."
  }
}
```
LLM analysis is best-effort: if a call fails or the JSON cannot be parsed, the result is kept with a fallback analysis (`parsed: false`) and the run continues.

**Use Cases**:
- Verification of current market trends or prices.
- Latest policy or regulation changes (tax laws, compliance).
- Comparing product features and reviews across several sources.
- Answering questions that need recent news or context, with sources.
