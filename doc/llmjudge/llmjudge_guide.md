# AgentRAG answer verification

Every chat and RAG chat answer goes through deterministic checks, then optionally through an LLM judge, before or after it is delivered depending on the mode.

## 1. From prompt to delivered answer

```mermaid
flowchart TD
    Q["Question + context<br/>RAG: chunks [SOURCE n]"] --> G["The LLM generates"]
    G --> M{"VERIFY_MODE ?"}

    M -- off --> O1["Streamed tokens<br/>as before"]
    O1 --> O2["Delivered, no verdict"]

    M -- "annotate (default)" --> A1["Streamed tokens<br/>as they come"]
    A1 --> A2["Answer saved<br/>before verification"]
    A2 --> A3["Check pipeline<br/>(figure 2)"]
    A3 --> A4["Verdict event + JSON column<br/>no regeneration"]

    M -- gate --> B1["Buffered generation<br/>status events"]
    B1 --> B2["Check pipeline<br/>(figure 2)"]
    B2 --> B3{"error or<br/>score #lt; 0.7 ?"}
    B3 -- "yes: regenerates with the findings" --> B1
    B3 -- no --> B4["Best version delivered<br/>+ verdict, even on failure<br/>after VERIFY_MAX_ROUNDS"]

    classDef good fill:#dcefe0,stroke:#2d7a3e,color:#1d2328;
    classDef acc fill:#dcecee,stroke:#1f6f78,color:#1d2328;
    class O2,A4,B4 good;
    class G,A3,B2 acc;
```

In `annotate`, the text does not wait for verification. In `gate`, nothing is shown before the checks finish, and each repair round gives the model its previous answer back with the concrete list of problems.

## 2. The checks, in order

```mermaid
flowchart LR
    subgraph det["deterministic: fast, no LLM"]
        direction LR
        C1["sanity<br/>empty, truncated, repetition loop<br/>always"]
        C2["citations<br/>[SOURCE n] does it exist? were any given?<br/>RAG"]
        C3["retrieval<br/>chunks below RAG_MIN_SCORE or no chunk<br/>RAG"]
        C4["code<br/>ast, ruff, JSON, YAML, 'the rest of the code…'<br/>if code block"]
        C5["schema<br/>JSON or YAML matching the expected schema<br/>if expected"]
        C1 --> C2 --> C3 --> C4 --> C5
    end

    J["LLM judge (one LLM call)<br/>rereads the answer with the sources and the findings<br/>VERIFY_JUDGE"]
    C5 --> J
    det -. "findings already found are given to the judge as evidence" .-> J

    J --> S["Score = 1 − (0.35 × errors + 0.10 × warnings)<br/>an info removes nothing · a check that crashes is isolated and never breaks the answer"]

    S --> V1["verified<br/>no findings"]
    S --> V2["warnings<br/>warnings only"]
    S --> V3["failed<br/>at least one error"]
    S --> V4["unverified<br/>nothing could be verified"]

    classDef good fill:#dcefe0,stroke:#2d7a3e,color:#1d2328;
    classDef warn fill:#f8ecd2,stroke:#9a6200,color:#1d2328;
    classDef bad fill:#f6dcd9,stroke:#b3342b,color:#1d2328;
    classDef acc fill:#dcecee,stroke:#1f6f78,color:#1d2328;
    class V1 good;
    class V2 warn;
    class V3 bad;
    class J acc;
```

The cheap checks run first. The judge comes last, because it can rely on what they already found (for example "the syntax is invalid on line 3") instead of rediscovering it.

## 3. The LLM judge: when it speaks, when it blocks

```mermaid
flowchart TD
    A{"judge applicable?<br/>VERIFY_JUDGE"} -- off --> I["ignored<br/>no judge"]
    A -- "auto: RAG with chunks, or code block · always" --> P["Judge prompt<br/>numbered sources · answer without #lt;think#gt;<br/>automatic findings · text treated as data"]
    P --> L["LLM call, temperature 0<br/>request model or VERIFIER_MODEL"]
    L --> R{"JSON answer<br/>readable?"}
    R -- no --> E["errored<br/>never blocks the answer"]
    R -- yes --> F{"the judge flags<br/>a problem?"}
    F -- no --> PA["passed<br/>answer supported"]
    F -- yes --> C{"confidence ≥ 0.6 ?"}
    C -- yes --> ER["ERROR<br/>triggers repair in gate"]
    C -- no --> W["WARNING<br/>−0.10 on the score, nothing more"]

    classDef good fill:#dcefe0,stroke:#2d7a3e,color:#1d2328;
    classDef warn fill:#f8ecd2,stroke:#9a6200,color:#1d2328;
    classDef bad fill:#f6dcd9,stroke:#b3342b,color:#1d2328;
    classDef acc fill:#dcecee,stroke:#1f6f78,color:#1d2328;
    class PA good;
    class E,W warn;
    class ER bad;
    class P acc;
```

The judge can only block an answer when it is sure of itself. If it gets the format wrong, if it goes down or if it hesitates, the answer is delivered and the doubt shows up only in the verdict.

## What each setting changes

| Variable | Effect on verification |
|---|---|
| `VERIFY_MODE` | `off`: nothing. `annotate`: immediate text, verdict afterwards. `gate`: delayed text, but repaired before delivery. |
| `VERIFY_JUDGE` | `off`: deterministic checks only. `auto`: judge if RAG with chunks or code. `always`: judge on everything. |
| `VERIFY_MAX_ROUNDS` | In `gate` only: maximum number of regenerations. `0` verifies without repairing. |
| `RAG_MIN_SCORE` | Relevance threshold for chunks. Below it, a weak-retrieval warning. |