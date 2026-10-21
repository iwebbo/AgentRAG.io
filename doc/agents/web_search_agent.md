### 3. Web Search Agent

**Purpose**: Access real-time, external information from the internet to provide up-to-date context, verify facts, and gather data points for analysis or decision-making.

**Workflow**:
1. Receive a complex query requiring current knowledge.
2. Execute optimized search queries against configured search engines (e.g., Google, Bing).
3. Retrieve snippets, source URLs, and metadata from the results.
4. Filter and synthesize the most relevant information based on the user's intent.
5. Present structured summaries with clear citations to external sources.

**Configuration**:
```json
{
  "api_key": "uuid", // API key for search service access
  "search_engines": ["google", "bing"], // List of preferred search providers
  "max_results": 5, // Maximum number of results to fetch per query
  "query_limit": 100 // Character limit for complex queries
}
```

**Use Cases**:
- Verification of current market trends or stock prices.
- Obtaining the latest policy changes (e.g., tax laws, regulations).
- Comparing product features and reviews from multiple sources.
- Answering questions requiring recent news or historical context.