# Workflows — User Guide

A workflow chains existing agents into a graph. Each node runs one of your agents; the output of one node can feed the next. The backend executes the graph and streams progress live.

## Concepts

| Term | Meaning |
|---|---|
| **Node** | One agent execution. Its form is the same as the agent's *Execute* form. |
| **Edge** | An arrow from node A to node B: B runs after A and may use A's output. |
| **Trigger inputs** | Values you provide when you click **Run**. Referenced as `{{trigger.<key>}}`. |
| **Output reference** | The result of an upstream node. Referenced as `{{nodes.<id>.output}}`. |

Agents never talk to each other directly. **All data flows through references placed in the fields of the next node.**

## Build a workflow

1. **Workflows → New workflow**, give it a name.
2. Add agents from the left palette (click or drag onto the canvas). Nodes are named `n1`, `n2`, …
3. Connect nodes by dragging from the right handle of one node to the left handle of the next.
4. Select a node to configure it in the right panel: choose the agent, then fill the fields.
5. **Save**, then **Run**.

Only active agents appear in the palette. A workflow must be a graph without cycles; loops and conditions are not supported.

## References

Any **text** field of a node accepts references. Checkboxes (for example `auto_send`) do not.

| Syntax | Source | Example |
|---|---|---|
| `{{trigger.<key>}}` | Run inputs entered at launch | `{{trigger.query}}` |
| `{{nodes.<id>.output}}` | Whole result of an upstream node | `{{nodes.n1.output}}` |
| `{{nodes.<id>.output.<path>}}` | A field inside the result | `{{nodes.n1.output.summary}}` |

Rules:

- You can only reference nodes **upstream** of the current node (connected before it). The node panel lists the references available.
- A field that contains **only** a reference keeps the original value type. A reference inside a longer text is converted to text.
- `{{nodes.<id>.output}}` without a path always works. Use a path only after you have seen the real result structure of that agent in a previous run.
- Fields containing a reference are not checked by the editor; the backend validates them at run time.

## Trigger inputs

The **Run workflow** dialog asks for a JSON object. It is available to every node as `{{trigger.<key>}}`.

- **Leave it empty** if no field of the workflow contains `{{trigger.…}}`. Values typed directly in the nodes are used as-is.
- **Use it** to make a workflow reusable with values that change at each run.
- If a field references a key you did not provide (for example `{{trigger.to}}` without `to`), that node fails with `Unresolved reference…`.

Example. Node `n1` has *Query* = `{{trigger.query}}`, node `n2` has *To* = `{{trigger.to}}`. At launch:

```json
{ "query": "Critical Apache CVEs this week", "to": "team@example.com" }
```

The same workflow now works for any topic and any recipient.

## Examples

### 1. Web Search → Email (CVE watch)

| Node | Agent | Configuration |
|---|---|---|
| `n1` | Web Search | *Query*: `{{trigger.query}}` |
| `n2` | Email Expert | *Mode*: `send_email_llm` · *To*: `{{trigger.to}}` · *Subject*: `Watch: {{trigger.query}}` · *Instructions*: `Write a professional email summarizing the analysis below and listing the key points.` · *Context*: `{{nodes.n1.output}}` · *Auto send*: checked |

Edge: `n1 → n2`. Trigger inputs: `{"query": "...", "to": "..."}`.

`n1` searches and synthesizes; `n2` receives that result in *Context*, writes the email with the LLM and sends it.

To send the text unchanged instead of having the LLM rewrite it, use mode `send_email` with *Body* = `{{nodes.n1.output}}`.

### 2. SonarQube → Email (weekly quality report)

| Node | Agent | Configuration |
|---|---|---|
| `n1` | SonarQube | Read mode matching what you want to analyze (projects, issues, …) |
| `n2` | Email Expert | *Mode*: `send_email_llm` · *To*: your team · *Subject*: `Code quality summary` · *Instructions*: `Write a summary for developers: blocking issues first, then the rest.` · *Context*: `{{nodes.n1.output}}` · *Auto send*: checked |

SonarQube access is read-only. Nothing is written until the email node sends.

### 3. Web Search → Wiki.js (publish a watch page)

| Node | Agent | Configuration |
|---|---|---|
| `n1` | Web Search | *Query*: `{{trigger.query}}` |
| `n2` | Wiki.js | *Mode*: create · *Path*: `{{trigger.path}}` · content field: `{{nodes.n1.output}}` |

Trigger inputs: `{"query": "...", "path": "watch/cve-november"}`.

> Check the exact name of the content field in the Wiki.js node form before using this example.

## Running and results

- Node colors during a run: grey = not run, orange = running, green = done, red = failed.
- Click a node to see its output, error and logs (live runs) in the right panel.
- **Stop** detaches your browser from the live stream. It does not cancel an agent already running on the server.
- With no node selected, the right panel shows the run summary and the **History**.

### Failures

- If a node fails, every node that depends on it is **skipped**. Independent branches keep running.
- The run is marked **Failed** if at least one node did not complete.
- Before streaming starts, the backend validates the whole workflow: agents must exist and be active, there must be no cycle, and every `{{nodes.…}}` reference must point to an upstream node. A violation is shown as an error and nothing is executed.

### History

Every run is stored. Click a run in **History** to load it back on the canvas: node colors and outputs are restored.

- Logs are not stored, only statuses, outputs and errors.
- The definition is not versioned: an old run is displayed on the current graph. Nodes deleted since then are ignored; new nodes appear as not run.
- Outputs larger than 1 MB are replaced by `Output too large to store`.
- History is available once the workflow has been saved.
- Use **← Back** in a node panel to return to the run summary and history.

## Good practice

1. Test any workflow that sends emails or writes somewhere with *Auto send* unchecked, or with your own address as recipient.
2. Run once, look at the real output of each node, then refine references (`output.<path>`) if needed.
3. Prefer `{{trigger.*}}` for values that change between runs, and fixed values for the rest.
4. Keep one purpose per workflow: *collect*, then *transform/write*, then *publish/send*.

## Limits (v1)

- No conditions or loops. Nodes run one at a time, in dependency order.
- No scheduling from the Workflows page.
- A run cannot be cancelled server-side.