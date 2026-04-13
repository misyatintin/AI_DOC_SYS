# AI Document Intelligence System

A production-minded invoice intelligence system for ingesting invoice PDFs, extracting structured data, validating the results, storing the source and output, and reviewing everything through a responsive UI built for human verification.

## Delivered capabilities

- Single and bulk PDF upload
- Original PDF storage on disk
- Structured extraction stored in MySQL
- Hybrid extraction pipeline
- OpenAI-first extraction path with PDF input and strict JSON schema when `OPENAI_API_KEY` is configured
- Optional Gemini path
- Stronger layout-aware fallback extraction when no LLM key is configured
- Prompt versioning with create, edit, and activate support
- Validation for missing fields, date normalization, line-item arithmetic, and confidence score
- Manual correction and revalidation
- PDF preview next to extracted fields for operator verification
- Reprocess and delete document workflows
- Monitoring dashboard for throughput, confidence, review queue, and processing latency
- Responsive UI for desktop, tablet, and mobile

## Tech stack

- Backend: FastAPI, SQLAlchemy async, MySQL
- Frontend: React 19, Vite, Recharts
- PDF parsing: PyMuPDF, pdfplumber
- Storage: local PDF storage + MySQL metadata and extraction records

## API surface

- `POST /api/documents`
- `POST /api/documents/bulk`
- `GET /api/documents`
- `GET /api/documents/{id}`
- `GET /api/documents/{id}/file`
- `PATCH /api/documents/{id}/correction`
- `POST /api/reprocess/{id}`
- `DELETE /api/documents/{id}`
- `GET /api/metrics/overview`
- `GET /api/prompts`
- `POST /api/prompts`
- `PUT /api/prompts/{id}`
- `POST /api/prompts/{id}/activate`

## MySQL configuration

Default local configuration:

```env
DATABASE_URL=mysql+aiomysql://root:new_password@localhost/ai_doc_sys
```

Local credentials currently used:

- Username: `root`
- Password: `new_password`
- Host: `localhost`
- Database: `ai_doc_sys`

Create the database before running the backend:

```sql
CREATE DATABASE ai_doc_sys;
```

## Local setup

### Backend

```powershell
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python run.py
```

Backend URLs:

- API: `http://localhost:8000`
- Swagger: `http://localhost:8000/docs`

### Frontend

```powershell
cd frontend
npm install
npm run dev
```

Frontend URL:

- UI: `http://localhost:5173`

## Environment variables

Primary backend settings:

- `DATABASE_URL`
- `UPLOAD_DIR`
- `CORS_ORIGINS`
- `EXTRACTION_PROVIDER`
- `OPENAI_API_KEY`
- `OPENAI_MODEL`
- `OPENAI_TIMEOUT_SECONDS`
- `GEMINI_API_KEY`
- `GEMINI_MODEL`
- `PROMPT_VERSION`
- `TOTAL_TOLERANCE`

Recommended enterprise-like extraction configuration:

```env
EXTRACTION_PROVIDER=auto
OPENAI_API_KEY=your_key_here
OPENAI_MODEL=gpt-5-mini
PROMPT_VERSION=v2.0-openai-pdf
```

## UI workflow

1. Upload one or more invoice PDFs.
2. Select a processed document from the queue.
3. Compare the original PDF preview with extracted fields in the review workspace.
4. Review confidence, missing fields, and validation errors.
5. Correct extracted fields manually if needed.
6. Save verified extraction.
7. Reprocess the document with a newer prompt version when required.

## Prompt versioning workflow

- Create a new prompt version from the prompt panel.
- Select an existing prompt version to view or edit it.
- Activate a prompt version from the UI.
- Reprocess documents to apply the active prompt.

## Assignment coverage

### 1. Objective

- Done: invoice PDF ingestion, extraction, validation, APIs, and UI are implemented.

### 2. Time expectation

- Repo is structured as a take-home solution, but the architecture and UI have been pushed toward a more production-style workflow.

### 3. Input dataset handling

- Different layouts: supported through LLM + layout-aware fallback extraction.
- Different field names: supported through prompt-driven extraction and alias-based fallback parsing.
- Multiple line items: supported.
- Missing fields: supported and surfaced in validation.
- Slightly rotated or inconsistent tables: partially addressed through PDF table extraction plus LLM path. Best results come from the OpenAI PDF model path.

### 4. Fields to extract

- `vendor_name`
- `invoice_number`
- `invoice_date`
- `currency`
- `total_amount`
- `tax_amount`
- `line_items(description, quantity, unit_price, line_total)`

### 5. Core requirements

- Accept invoice upload, single and bulk: done
- Parse the document: done
- AI or hybrid extraction: done
- Prompt versioning: done
- Normalize extracted data: done
- Store structured results in DB: done

### 6. Validation layer

- Sum line items against total: done
- Normalize date formats: done
- Detect missing fields: done
- Return confidence score and validation errors: done

### 7. REST APIs

- `POST /documents`: done
- `GET /documents`: done
- `GET /documents/{id}`: done
- `POST /reprocess/{id}`: done

Additional operational APIs included:

- `GET /documents/{id}/file`
- `DELETE /documents/{id}`
- prompt management endpoints
- metrics endpoint

### 8. Frontend requirements

- Upload invoices: done
- View processed invoices: done
- Display extracted fields: done
- Show validation errors and confidence score: done
- Allow manual correction: done
- Show error report dashboard: done
- Show monitoring metrics dashboard: done
- View source PDF beside extracted fields for verification: added
- Delete uploaded document: added

### 9. Storage

- Store original PDF: done
- Store extracted structured JSON: done
- Store processing metadata and confidence scores: done

## Deliverables in repo

- Setup instructions: this README
- Architecture overview: [docs/architecture_overview.md](/C:/Users/HP/Desktop/AI_DOC_SYS/docs/architecture_overview.md)
- Example output JSON: [docs/example_output.json](/C:/Users/HP/Desktop/AI_DOC_SYS/docs/example_output.json)

## Verification notes

- Extraction regression test for the shared invoice layout: `backend/tests/test_extraction_service.py`
- Current fallback extraction is much stronger than before, but the most reliable path for messy real-world invoices is the OpenAI PDF extraction path.
