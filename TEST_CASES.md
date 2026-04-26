# API Test Cases - Quick Reference

## Prerequisites
- Server running: `python main.py`
- Have a sample PDF invoice file ready

## Test Cases

### Test 1: Check Server Health
```bash
# Visit in browser
http://localhost:8000/docs

# Or using curl
curl http://localhost:8000/docs
```
**Expected:** Swagger UI should load

---

### Test 2: Upload Invoice
```bash
# Replace invoice.pdf with actual file
curl -X POST http://localhost:8000/upload \
  -F "invoice_file=@path/to/invoice.pdf"
```

**Response Example:**
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "queued"
}
```

**Save the `job_id` for next tests!**

---

### Test 3: Check Job Status
```bash
# Replace JOB_ID with actual job_id from Test 2
curl http://localhost:8000/jobs/JOB_ID
```

**Response Example:**
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "processing",
  "updated_at": "2026-04-26T10:30:45.123456+00:00"
}
```

**Statuses:**
- `queued` - Waiting to start
- `processing` - Currently running (takes 1-5 minutes)
- `completed` - Done
- `failed` - Error occurred

---

### Test 4: Get JSON Audit Report
```bash
# Only works when status = "completed"
curl http://localhost:8000/jobs/JOB_ID/report
```

**Response Example:**
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "validation_passed": true,
  "validation_findings": [],
  "errors": [],
  "detected_language": "en",
  "extraction_confidence": 0.95,
  "chunk_count": 5
}
```

---

### Test 5: Get Markdown Audit Report
```bash
curl http://localhost:8000/jobs/JOB_ID/report/markdown
```

**Response:** Full HTML-formatted audit report

---

### Test 6: Query Invoice (RAG)
```bash
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What is the total amount?",
    "job_id": "JOB_ID"
  }'
```

**Response Example:**
```json
{
  "query": "What is the total amount?",
  "answer": "The total amount is $1,250.00",
  "sources": ["invoice_collection"]
}
```

---

## Testing Workflow

### Full End-to-End Test:
1. ✓ Start server: `python main.py`
2. ✓ Upload invoice (Test 2)
3. ✓ Check status repeatedly until "completed" (Test 3)
4. ✓ Get JSON report (Test 4)
5. ✓ Get Markdown report (Test 5)
6. ✓ Query the invoice (Test 6)

### Quick Automated Test:
```bash
python test_api.py
```

This script will:
- Check server health
- Find sample invoices in `data/incoming/`
- Upload the first one
- Wait for completion
- Retrieve all reports
- Run sample queries

---

## Expected Processing Times

| Phase | Duration | Notes |
|-------|----------|-------|
| Upload | < 1s | File upload |
| Queued | < 5s | Job startup |
| Processing | 2-5 min | PDF extraction, LLM processing |
| Report Generation | < 1s | Once processing done |
| Query Response | 2-5s | Per query |

---

## Sample Invoices
Use invoices from: `data/incoming/`
- `INV_EN_001.meta.json` - English invoice with metadata
- `INV_DE_004.meta.json` - German invoice
- `INV_ES_003.meta.json` - Spanish invoice

---

## Troubleshooting

### Server not responding?
```
Error: Cannot connect to http://localhost:8000
```
**Fix:** Start server
```bash
python main.py
```

### Job stuck in "processing"?
- Check logs in terminal running `python main.py`
- Wait up to 5 minutes
- Check Groq/HuggingFace API connectivity

### 404 Error on report endpoints?
- Job might still be processing
- Wait longer and try again
- Check job status: `curl http://localhost:8000/jobs/JOB_ID`

### API Key errors?
- Verify `.env` has valid:
  - `GROQ_API_KEY`
  - `HUGGINGFACE_API_KEY`
  - `QDRANT_API_KEY`

---

## Using Postman (Alternative to curl)

1. Import endpoints into Postman
2. Create environment variables:
   - `base_url`: http://localhost:8000
   - `job_id`: (from upload response)
3. Run pre-built collection of requests

---

## Test Success Criteria

✓ All tests pass when:
- Upload returns 200 with job_id
- Status progresses: queued → processing → completed
- Report endpoints return 200 (when completed)
- Query endpoint returns answer
- No 500 errors in logs
