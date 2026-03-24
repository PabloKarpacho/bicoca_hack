# Resume Search Console

Resume Search Console is a full-stack system for ingesting CVs, extracting structured candidate data, indexing resume semantics, and searching candidates through a combination of rule-based and vector retrieval.

The repository contains:
- a FastAPI backend for ingestion, normalization, extraction, indexing, and search
- a Quasar SPA frontend for upload, status tracking, and shortlist review
- PostgreSQL as the source of truth
- MinIO for original file storage
- Qdrant as the semantic index

## What the product does

The current product supports this workflow:

1. Upload a resume file (`pdf` or `docx`)
2. Store the original file in object storage
3. Run an asynchronous processing pipeline:
   - raw text extraction
   - entity extraction
   - normalization
   - vector chunk building and indexing
4. Monitor pipeline progress from the frontend through polling
5. Paste a vacancy description and prepare search filters from it
6. Review and edit filters in the frontend
7. Run candidate search using rule-based, vector, or hybrid retrieval
8. Open the matched resume through a generated download link

## Product architecture

### Backend

The backend is built with FastAPI and uses PostgreSQL as the main persisted model layer.

Key responsibilities:
- resume upload and background ingestion
- CV entity extraction
- generalized entity normalization
- vacancy preparation for search
- rule-based search in PostgreSQL
- semantic chunk indexing in Qdrant
- vector and hybrid search
- HH-based autocomplete and normalization for skills and professions

Important backend folders:
- [src/app/routers/rag](/home/pavel/work/hack/src/app/routers/rag)
- [src/app/service/cv](/home/pavel/work/hack/src/app/service/cv)
- [src/app/service/search](/home/pavel/work/hack/src/app/service/search)
- [src/app/service/normalization](/home/pavel/work/hack/src/app/service/normalization)
- [src/database/postgres](/home/pavel/work/hack/src/database/postgres)
- [src/database/s3](/home/pavel/work/hack/src/database/s3)

### Frontend

The frontend is a Quasar SPA focused on two operational flows:
- upload resumes and observe processing state
- prepare vacancy filters and review candidate results

Important frontend folders:
- [frontend/src/pages](/home/pavel/work/hack/frontend/src/pages)
- [frontend/src/components](/home/pavel/work/hack/frontend/src/components)
- [frontend/src/stores](/home/pavel/work/hack/frontend/src/stores)
- [frontend/src/composables](/home/pavel/work/hack/frontend/src/composables)
- [frontend/src/api](/home/pavel/work/hack/frontend/src/api)
- [frontend/src/types](/home/pavel/work/hack/frontend/src/types)

### Infrastructure

- PostgreSQL stores candidate entities, prepared jobs, normalization registry, processing runs, and vector chunk metadata
- MinIO stores original uploaded resume files
- Qdrant stores vector embeddings for candidate chunks

## How the backend works

### 1. Resume ingestion

The main upload route is:
- `POST /rag/ingest_file`

This route:
- validates the uploaded file
- resolves or creates the candidate
- stores the document metadata in PostgreSQL
- uploads the original file to MinIO
- schedules background processing
- returns `202 Accepted` with a polling URL

Relevant files:
- [rag.py](/home/pavel/work/hack/src/app/routers/rag/rag.py)
- [background_ingestion.py](/home/pavel/work/hack/src/app/service/cv/background_ingestion.py)

### 2. Background processing pipeline

The background ingestion pipeline currently runs:

1. raw text extraction
2. entity extraction
3. vector indexing
4. final document status update

If a later stage fails, the pipeline performs compensation cleanup for generated artifacts.

Relevant files:
- [background_ingestion.py](/home/pavel/work/hack/src/app/service/cv/background_ingestion.py)
- [entity_extraction/service.py](/home/pavel/work/hack/src/app/service/cv/entity_extraction/service.py)
- [candidate_vector_indexing.py](/home/pavel/work/hack/src/app/service/search/candidate_vector_indexing.py)

### 3. Entity extraction

The system extracts:
- candidate profile
- languages
- experiences
- skills
- education
- certifications

Extraction is LLM-based, but the result is normalized and persisted as structured data.

Relevant files:
- [entity_extraction/llm_client.py](/home/pavel/work/hack/src/app/service/cv/entity_extraction/llm_client.py)
- [entity_extraction/graph.py](/home/pavel/work/hack/src/app/service/cv/entity_extraction/graph.py)
- [entity_extraction.py](/home/pavel/work/hack/src/app/models/entity_extraction.py)

### 4. Normalization

The project uses a generalized normalization subsystem with a PostgreSQL registry:
- exact original lookup first
- reuse normalized result if already known
- otherwise dispatch to class-specific provider or agent
- persist the new mapping

Normalization currently covers major search-facing entities such as:
- languages
- proficiency levels
- seniority levels
- skills
- professions
- cities
- countries
- remote policy
- employment type
- education

Relevant files:
- [service.py](/home/pavel/work/hack/src/app/service/normalization/service.py)
- [primitives.py](/home/pavel/work/hack/src/app/service/normalization/primitives.py)
- [schema.py](/home/pavel/work/hack/src/database/postgres/schema.py)

### 5. Vacancy preparation

The route:
- `POST /rag/jobs/prepare`

turns raw vacancy text into a search-ready payload compatible with:
- `POST /rag/search`

The preparation result contains:
- structured rule filters
- semantic query text fields for vector search

Relevant files:
- [job_search/llm_client.py](/home/pavel/work/hack/src/app/service/job_search/llm_client.py)
- [job_search/service.py](/home/pavel/work/hack/src/app/service/job_search/service.py)
- [job_preparation.py](/home/pavel/work/hack/src/app/service/normalization/job_preparation.py)

### 6. Search

The main route is:
- `POST /rag/search`

Supported strategies:
- `rule_based`
- `vector`
- `hybrid`

#### Rule-based search

Rule-based search operates on normalized structured data in PostgreSQL.

It is designed to be practical and intentionally not overly strict:
- some signals are hard filters
- some are soft compatibility metadata only

For example:
- skills are currently supportive signals, not hard filters
- education is exposed as compatibility metadata
- employment type is checked by overlap and surfaced in metadata, but does not exclude candidates if missing

Relevant file:
- [candidate_rule_search.py](/home/pavel/work/hack/src/app/service/search/candidate_rule_search.py)

#### Vector search

Vector search works on semantic chunks stored in Qdrant.

The current chunk taxonomy is:
- `role_profile`
- `experience_role`
- `skills_profile`

The system:
- builds chunks from extracted candidate entities
- stores chunk rows in PostgreSQL
- embeds chunk text
- upserts chunk vectors into Qdrant
- aggregates chunk-level hits into candidate-level results

Relevant files:
- [candidate_chunk_builder.py](/home/pavel/work/hack/src/app/service/search/candidate_chunk_builder.py)
- [candidate_vector_indexing.py](/home/pavel/work/hack/src/app/service/search/candidate_vector_indexing.py)
- [candidate_vector_search.py](/home/pavel/work/hack/src/app/service/search/candidate_vector_search.py)

#### Hybrid search

Hybrid search uses:
- PostgreSQL for shortlist generation
- Qdrant for semantic reranking of that shortlist

This keeps structured constraints while improving ranking quality.

### 7. Search scoring

Search results expose two different score concepts:
- raw semantic `score` from vector retrieval
- user-facing `match_score_percent`

`match_score_percent` is a calibrated explainable score built from:
- vector semantic score
- role match
- skills overlap
- experience coverage
- language coverage

Relevant file:
- [candidate_match_scoring.py](/home/pavel/work/hack/src/app/service/search/candidate_match_scoring.py)

## API overview

Main routes:
- `POST /rag/ingest_file`
- `GET /rag/file/{file_id}`
- `GET /rag/file/{file_id}/pipeline-status`
- `POST /rag/file/{file_id}/extract-entities`
- `GET /rag/file/{file_id}/entities`
- `POST /rag/file/{file_id}/index-vectors`
- `DELETE /rag/file/{file_id}`
- `POST /rag/jobs/prepare`
- `GET /rag/jobs/{job_id}`
- `POST /rag/search`
- `POST /rag/search/vector-debug`
- `GET /rag/skills/autocomplete`
- `GET /rag/professions/autocomplete`

Open API docs are available at:
- `/docs`
- `/redoc`

## Frontend overview

The frontend contains two main pages.

### Upload page

Route:
- `/`

Capabilities:
- upload resume files
- see current document processing state
- inspect recent uploads
- poll backend status until terminal state

Relevant files:
- [UploadPage.vue](/home/pavel/work/hack/frontend/src/pages/UploadPage.vue)
- [useDocumentUpload.ts](/home/pavel/work/hack/frontend/src/composables/useDocumentUpload.ts)
- [documents.ts](/home/pavel/work/hack/frontend/src/stores/documents.ts)

### Search page

Route:
- `/search`

Capabilities:
- paste vacancy text and prepare filters
- edit rule-based filters
- run search automatically as filters change
- review candidate cards and open resumes

Relevant files:
- [SearchPage.vue](/home/pavel/work/hack/frontend/src/pages/SearchPage.vue)
- [CandidateSearchFiltersForm.vue](/home/pavel/work/hack/frontend/src/components/search/CandidateSearchFiltersForm.vue)
- [CandidateSearchResults.vue](/home/pavel/work/hack/frontend/src/components/search/CandidateSearchResults.vue)
- [CandidateResultCard.vue](/home/pavel/work/hack/frontend/src/components/search/CandidateResultCard.vue)

### Frontend architecture

The frontend is structured into clear layers:
- `pages` for route-level screens
- `components` for reusable UI
- `stores` for state via Pinia
- `composables` for page workflows
- `api` for transport abstraction
- `types` for typed domain models

The UI does not call `fetch` directly from components; requests go through the API layer.

## HH autocomplete integration

The project integrates HH autosuggest for:
- skills
- professions

Use cases:
- search form autocomplete
- skill normalization
- profession normalization

Russian-language HH suggestions are filtered out and debug logs are emitted for raw and parsed HH responses.

Relevant files:
- [hh_skill_normalizer.py](/home/pavel/work/hack/src/app/service/skills/hh_skill_normalizer.py)
- [hh_work_normalizer.py](/home/pavel/work/hack/src/app/service/work/hh_work_normalizer.py)

## Running the project locally

### Prerequisites

Backend:
- Python 3.12+
- a virtual environment in `.venv`

Frontend:
- Node.js 22+ or 24+
- npm

Infrastructure:
- PostgreSQL
- MinIO
- Qdrant

### Environment

The backend uses environment variables from `.env`.

Important groups of variables:
- PostgreSQL connection strings
- MinIO credentials and endpoint
- Qdrant URL
- LLM provider settings
- HH autosuggest settings

If you are setting up a new environment, make sure these are defined before starting the app.

### Backend local run

Install dependencies in the existing virtual environment and run migrations:

```bash
./scripts/run_migrations.sh
```

Start the API:

```bash
./scripts/run_app.sh
```

By default the backend runs on:
- `http://localhost:8000`

### Frontend local run

From the frontend directory:

```bash
cd frontend
npm install
npm run dev
```

By default the frontend runs on:
- `http://localhost:9001`

In development, Quasar proxies `/rag` requests to the backend on port `8000`.

## Running with Docker Compose

The repository now includes:
- backend Dockerfile
- frontend Dockerfile
- nginx config for SPA serving and backend proxying
- compose integration for backend, frontend, postgres, minio, qdrant, and pgadmin

Start everything:

```bash
docker compose up --build
```

Services:
- frontend: `http://localhost:9001`
- backend: `http://localhost:8000`
- backend docs: `http://localhost:8000/docs`
- pgAdmin: `http://localhost:5050`
- MinIO API: `http://localhost:9000`
- MinIO console: `http://localhost:7001`
- Qdrant: `http://localhost:6333`

Notes:
- backend container runs `alembic upgrade head` on startup
- frontend container serves the built SPA through nginx
- nginx proxies `/rag/*` to the backend service inside Docker

## Development workflow

### Backend

Typical loop:

1. start infrastructure
2. run migrations
3. start FastAPI app
4. change backend code
5. run tests for affected areas

Useful files:
- [scripts/run_app.sh](/home/pavel/work/hack/scripts/run_app.sh)
- [scripts/run_migrations.sh](/home/pavel/work/hack/scripts/run_migrations.sh)

### Frontend

Typical loop:

1. start Quasar dev server
2. update pages, stores, composables, or API adapters
3. verify build and lint

Useful commands:

```bash
cd frontend
npm run lint
npm run build
```

## Testing

Backend tests live in:
- [tests](/home/pavel/work/hack/tests)

Run the full suite:

```bash
PYTHONPATH=src DEBUG=false ./.venv/bin/pytest tests -q
```

Run a targeted file:

```bash
PYTHONPATH=src DEBUG=false ./.venv/bin/pytest tests/test_candidate_rule_search.py -q
```

Frontend checks:

```bash
cd frontend
npm run lint
npm run build
```

## Project structure

Top-level layout:

```text
src/                FastAPI application code
frontend/           Quasar SPA
tests/              backend tests
alembic/            database migrations
scripts/            local helper scripts
docker/             docker-related assets
docker-compose.yml  local multi-service environment
Dockerfile          backend container image
```

## Important implementation details

### PostgreSQL is the source of truth

Even when semantic search is enabled:
- canonical candidate and vacancy data live in PostgreSQL
- vector chunks are also persisted in PostgreSQL
- Qdrant is an index, not the primary record store

### Search readiness

The vacancy preparation route returns the same DTO shape consumed by `/rag/search`.

That means the intended flow is:

1. prepare vacancy text
2. review or tweak resulting filters
3. submit those filters directly to search

### Persistent normalization cache

The normalization registry acts as the persistent cache and source of truth for known mappings. Repeated original values do not need repeated agent calls.

## Current limitations

- some tests can be slow or unstable depending on local environment and external integrations
- vector relevance is heuristic and intentionally practical, not a learned reranker
- candidate profile detail UI is intentionally lightweight
- frontend currently focuses on upload and shortlist review, not full candidate profile exploration
- some compatibility signals, such as education and employment type, are soft metadata rather than hard filters

## Troubleshooting

### Backend starts but cannot connect to services

Check:
- `DB_POSTGRES_URL_ASYNC`
- `S3_ENDPOINT`
- `QDRANT_URL`

### Frontend loads but API calls fail

Check:
- backend is available on port `8000`
- in local dev, Quasar proxy is enabled
- in Docker, frontend nginx proxy is routing `/rag` to `backend:8000`

### Search returns no semantic results

Check:
- the document reached vector indexing successfully
- Qdrant is configured
- chunks exist for the candidate document

## Where to extend next

Common extension points:
- add new normalization classes in [normalization_class.py](/home/pavel/work/hack/src/app/config/enums/normalization_class.py)
- refine search scoring in [candidate_match_scoring.py](/home/pavel/work/hack/src/app/service/search/candidate_match_scoring.py)
- add new semantic chunk types in [candidate_chunk_builder.py](/home/pavel/work/hack/src/app/service/search/candidate_chunk_builder.py)
- expand the frontend search UX in [frontend/src/components/search](/home/pavel/work/hack/frontend/src/components/search)

## Quick start summary

Local backend:

```bash
./scripts/run_migrations.sh
./scripts/run_app.sh
```

Local frontend:

```bash
cd frontend
npm install
npm run dev
```

Full stack in Docker:

```bash
docker compose up --build
```
