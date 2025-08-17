# RAG on Azure — Production-style AI Knowledge API (FastAPI + LangChain + Azure AI Search)

## Summary

This is a small but realistic Retrieval-Augmented Generation (RAG) service. It ingests documents, splits them into chunks, creates embeddings, and stores both text and vectors in Azure AI Search. A secure FastAPI API retrieves the most relevant chunks and asks an LLM to answer using only those chunks as context. The service runs in a Docker container, images live in Azure Container Registry (ACR), and it’s deployed to Azure Container Apps for a public, autoscaling runtime.
All sensitive credentials (OpenAI keys, Azure Search keys, JWT secrets) are stored in Azure Key Vault, retrieved at runtime by the Container App via managed identity, and exposed to the app as environment variables.

---
## Live Demo

Swagger (API docs): [https://aca-rag.wittysand-46da5683.ukwest.azurecontainerapps.io/docs](https://aca-rag.wittysand-46da5683.ukwest.azurecontainerapps.io/docs)

### How to try in Swagger

1. Call POST /token with any non-empty username and password.
2. Click “Authorize” (top-right in Swagger).
3. In the popup, enter any non-empty values for username and password. Leave client\_id and client\_secret blank.
4. Click “Authorize”, then “Close”. Swagger will call /token and store the access token automatically.
5. Call POST /query with q set to your question. The response cites the ingested source files.

---

## What the App Does

### Ingest

Place files in the data/ folder. The ingestion script reads TXT, DOCX, and PDF, splits text into chunks, embeds the chunks, and uploads id, content, embedding, and source to Azure AI Search.

### Retrieve

At query time the API fetches the top-k chunks from Azure AI Search using vector plus keyword search.

### Generate

The LLM answers using only those chunks as grounded context.

### Secure Access

The API is protected with a short-lived Bearer token (JWT) obtained from POST /token. Swagger UI is built-in at /docs.

---

## Public API Surface

* GET /health — liveness probe returning { "status": "ok" }.
* POST /token — returns a demo JWT for testing.
* POST /query?q=… — returns an answer grounded in your docs (requires Authorization: Bearer <token>).
* Swagger/OpenAPI — available at /docs.

---

## Architecture at a Glance

* Client -> FastAPI (JWT auth, OpenAPI docs).
* Retrieval pipeline -> LangChain retriever backed by Azure AI Search (HNSW vectors + keyword).
* LLM and embeddings -> OpenAI API (can be swapped for Azure OpenAI later).
* Container image -> Docker; stored in Azure Container Registry.
* Runtime -> Azure Container Apps with external ingress, autoscaling, revisions, and rollbacks.
* Secrets -> Stored in Azure Key Vault; injected into Container Apps via managed identity and mounted as environment variables.
* Observability -> Container logs/metrics in Azure Monitor/Log Analytics; health endpoint for probes.

---

## Repo Contents (what each part does)

* app/api.py — FastAPI routes: /health, /token, /query (exposes Swagger).
* app/rag.py — RAG orchestration: builds the Search retriever, crafts the prompt, calls the LLM, returns sources.
* app/auth.py — Lightweight OAuth2/JWT for a realistic bearer-token flow.
* app/settings.py — Central configuration; reads environment variables that are populated at runtime from Key Vault.
* app/ingest/index\_schema.json — Azure AI Search index definition (fields and vector profile).
* app/ingest/readers.py — File readers for .txt, .pdf (PyPDF), .docx (python-docx).
* app/ingest/chunkers.py — Splits text into embedding-friendly chunks.
* app/ingest/load\_docs.py — Ensures the index exists, embeds chunks, and upserts documents to Search.
* app/ingest/delete\_docs.py — Deletes documents from the index (by filename, glob pattern, or all).
* data/ — Example input documents (about.txt, faq.txt).
* tests/api\_key\_test.py — Small sanity check for your OpenAI key.
* Dockerfile — Production image build for the API.
* requirements.txt — Python dependencies.
* .env — Local development variables (do not commit secrets to public repos).

---

## Local Development (quick start)

### Prerequisites

* Python 3.11
* OpenAI API key
* Azure AI Search credentials (if you want to ingest locally)

### Steps

1. Create and activate a virtual environment, then install dependencies.
2. Populate .env with: OPENAI\_API\_KEY, AZ\_SEARCH\_ENDPOINT, AZ\_SEARCH\_API\_KEY, AZ\_SEARCH\_INDEX, JWT\_SECRET, JWT\_ALG.
3. Run the API locally with Uvicorn (app.api\:app), reload enabled, on port 8000.
4. Open http://127.0.0.1:8000/docs to test.
5. Ingest local docs before querying by running the ingestion loader.

---

## Ingest, Update, and Delete Documents

* Add or update: place TXT/DOCX/PDF files in data/ and run the ingestion loader. Uses stable document IDs (filename + chunk index) so re-runs upsert and replace without duplicates.
* Remove by filename: run the delete script with a filename (e.g., about.txt).
* Remove by pattern: run the delete script with a glob (e.g., \*.pdf).
* Remove everything: run the delete script with the “all” option.

---

## Deployment Summary (what’s in Azure)

* Resource group: rg-rag
* Azure AI Search: holds the vector index for retrieval.
* Azure Container Registry (ACR): stores your container image.
* Azure Container Apps: runs the API and exposes a public FQDN (see /docs).
* Log Analytics: collects logs/metrics for observability (optional but recommended).

---

## Runtime Configuration (secrets and environment variables)

The app reads these variables:

* AZ\_SEARCH\_ENDPOINT (e.g., [https://yoursearch.search.windows.net](https://yoursearch.search.windows.net))
* AZ\_SEARCH\_API\_KEY (admin or query key for Azure AI Search)
* AZ\_SEARCH\_INDEX (e.g., docs-index)
* OPENAI\_API\_KEY (OpenAI access key)
* JWT\_SECRET (secret for signing demo JWTs)
* JWT\_ALG (e.g., HS256)

How they are provided in Azure

* Each secret is stored in Azure Key Vault (e.g., kv-rag-12345).
* The Container App (aca-rag) has a system-assigned managed identity with Key Vault Secrets User role.
* Container Apps secrets reference Key Vault URIs (e.g., keyvault://kv-rag-12345/secrets/OpenAIKey) and map them to environment variables.
* Example mapping inside Container Apps:
  """
  OPENAI_API_KEY=secretref:openaikey
  AZ_SEARCH_API_KEY=secretref:az-search-api-key
  JWT_SECRET=secretref:jwt-secret
  """
Rotating a secret in Key Vault does not require redeploys; the Container App refreshes automatically.

---

## CI/CD (GitHub Actions with Azure OIDC)

* Trigger: push to main.
* Build and publish: builds the Docker image and pushes it to ACR.
* Deploy: updates the Azure Container App to the new image; each deploy creates a new revision for safe rollback.
* Authentication: GitHub → Azure uses short-lived OIDC tokens and Azure RBAC (no long-lived Azure credentials stored in GitHub).

### GitHub repository secrets used by the workflow

* AZURE\_CLIENT\_ID (App registration’s application/client ID for OIDC)
* AZURE\_TENANT\_ID (Directory/tenant ID)
* AZURE\_SUBSCRIPTION\_ID (subscription GUID)

### Runtime secrets

Remain in Container Apps; they are not stored in GitHub and do not require redeploys when changed.

### Output

The workflow prints the public URL (FQDN) after deployment. Live API docs remain at: [https://aca-rag.wittysand-46da5683.ukwest.azurecontainerapps.io/docs](https://aca-rag.wittysand-46da5683.ukwest.azurecontainerapps.io/docs)

---

## Security and Privacy

* The query endpoint is protected by JWT for demo purposes; real identity (Azure AD, APIM) can be added without code changes.
* No secrets in code or image; secrets are provided via environment variables and stored as Container Apps secrets (next step: Azure Key Vault with managed identity).
* Retrieval-augmented generation reduces hallucinations and returns sources for traceability.
* The query endpoint is protected by JWT for demo purposes; real identity (Azure AD, APIM) can be added without code changes.
* Secrets are never stored in code, image, or GitHub.
    * Local dev uses .env (gitignored).
    * Cloud runtime uses Key Vault + managed identity to provide secrets.
* Retrieval-augmented generation reduces hallucinations and returns sources for traceability.

---

## Scalability and Reliability

* Container Apps scales to zero when idle and up under load; revisions support safe rollbacks.
* Azure AI Search provides low-latency vector + keyword retrieval.
* Health endpoint (/health) supports probes and external monitoring.

---

## Observability

* Logs and metrics via Azure Monitor/Log Analytics and the Container Apps log stream.
* /health exposed for health checks.
* Structure supports adding prompt/response logging, tracing, and latency metrics.

---

## Cost Control

* Azure AI Search: Basic SKU with one replica is sufficient for small corpora and demos.
* Container Apps: minimal CPU/memory and scale-to-zero keep runtime costs small.
* OpenAI costs are controlled on the OpenAI dashboard.
* Cleanup: deleting the resource group removes all Azure resources and stops charges.

---

## Embedded Project Documents (what’s in the knowledge base)

The demo knowledge base comprises three documents—one text, one Word, and one PDF—that together explain the project end-to-end (architecture, code layout, deployment commands, and talking points). These files are ingested into Azure AI Search and used to ground answers. Recruiters and reviewers can ask questions about the project in the live API; responses cite these documents. To update the knowledge, replace the files and re-run the ingestion script; no redeploy is required.
Live testing: [https://aca-rag.wittysand-46da5683.ukwest.azurecontainerapps.io/docs](https://aca-rag.wittysand-46da5683.ukwest.azurecontainerapps.io/docs)

---

## FAQ Prompts (use with POST /query in /docs)

* What problem does this service solve for a business team?
* How does retrieval-augmented generation work here?
* Which documents are embedded and what do they cover?
* How do I add new documents or refresh existing ones?
* How do I remove a document from the index?
* What security exists today, and what would you add in production?
* Why Azure AI Search instead of a standalone vector database?
* What are the main components (FastAPI, LangChain, Azure services) and how do they interact?
* How do I obtain a token and call the API securely?
* What does /query return, and how are sources shown?
* How does the system scale, and what are the default scaling settings?
* What are the expected costs for a small demo, and how do you keep them low?
* How are secrets managed now, and how would you move them to Key Vault?
* What observability is available (logs, health checks), and where do I find it?
* What are the main limitations or risks, and how would you mitigate them?
* Which models are used for embeddings and chat, and can they be swapped?
* How would you enforce citations/guardrails to further reduce hallucinations?
* Can this integrate with SharePoint or Confluence for ingestion?

---

## Troubleshooting (common issues and fixes)

* “Subscription not registered to use namespace …” → Register providers: Microsoft.Search, Microsoft.ContainerRegistry, Microsoft.App, Microsoft.OperationalInsights.
* ACR pull failures during first deploy → Either enable ACR admin temporarily or, preferably, use RBAC.
* Container Apps secret name invalid → Use lowercase and hyphens (e.g., az-search-endpoint). Map them to environment variables using secret references.
* Re-ingesting creates duplicates → The ingestion uses stable IDs; re-run the loader to upsert. If you changed filenames, delete old docs first.
* OpenAI 401/429 → Verify OPENAI\_API\_KEY via the test and check quota.
* Changing docs without redeploying → Yes; re-run the ingestion script and the running API will use the updated index immediately.

---

## Roadmap (easy next steps)

* Move secrets to Azure Key Vault with managed identity.
* Add Azure API Management (APIM) for governance (keys, quotas, IP rules, versioning).
* Add PR preview deployments and post-deploy smoke tests to CI/CD.
* Add evaluation (Ragas/Promptfoo) and light guardrails (citation checks, refusals).
* Build a tiny UI that calls the API and shows sources inline.
* Private networking and storage-backed ingestion for sensitive corpora.

---

## Credits

This project is intentionally small and production-shaped. It brings together FastAPI, LangChain, and Azure AI Search, packaged in Docker and run on Azure Container Apps, to show a clean, secure pattern for RAG in the cloud. The template includes JWT-protected endpoints, Swagger docs, and a simple /health check; images are stored in Azure Container Registry, and the design leaves clear seams for Key Vault (secrets), Azure API Management (governance), and GitHub Actions (CI/CD). It’s meant to be a minimal starter you can extend — not rewrite — as needs grow.
