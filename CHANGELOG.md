# AgentRAG.io Changelog

## Version v1.1.78 - [16/10/2026]

Generated DevOps deliverables can now be downloaded in their native format straight from the chat, with no backend change.

---

### New Features & Enhancements

#### Detected File Export
The frontend now detects the deliverables contained in an LLM answer (code blocks) and offers them for download as real files.

*   **Native formats:** `Jenkinsfile`, `.groovy`, `Dockerfile`, `values.yaml`, `Chart.yaml`, `docker-compose.yml`, Kubernetes / Helm templates, `.sh`, `.tf`, `README.md` and more. The file name is detected from the fence meta, a first-line comment, the text above the block, the content itself, or the language.
*   **Per-block download:** a *Download* button next to *Copy* on every detected file block, shown once the message is complete.
*   **ZIP of all files:** one click to download every detected file, folder tree preserved (e.g. `templates/deployment.yaml`).
*   **Markdown export:** full message as `.md`, generated locally.
*   **Export history:** local exports are listed in the existing history drawer.

**Fixes & Bug Resolutions**
### WebSearch Agent Fixes
- **ddgs>=1.36**: Updated DeepDive Graph Search engine to version 1.36+ for improved search accuracy and performance
- **Backend correction**: Fixed critical backend issue affecting websearch agent functionality

---