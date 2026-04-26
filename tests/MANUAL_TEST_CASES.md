# Manual Test Cases - API Testing Guide

## Test Environment Setup

### Prerequisites
1. Server running: `python main.py`
2. Swagger UI available: `http://localhost:8000/docs`
3. Sample invoices in `data/incoming/`

---

## Test Case 1: Server Health Check
**Objective:** Verify server is running and accessible

### Steps:
1. Open browser: `http://localhost:8000/docs`
2. Verify Swagger UI loads

### Expected Result:
- ✓ Status Code: 200
- ✓ Swagger UI interface visible
- ✓ All endpoints listed

**Time:** < 5 seconds

---

## Test Case 2: Upload Invoice (No Metadata)
**Objective:** Upload single invoice file

### Steps:
1. Open Swagger UI: `http://localhost:8000/docs`
2. Click `/upload` endpoint
3. Click "Try it out"
4. Select PDF file from `data/incoming/`
5. Click "Execute"

### Expected Result:
- ✓ Status Code: 200
- ✓ Response contains `job_id`
- ✓ Response contains `status: "queued"`
- ✓ `job_id` is UUID format

**Response Example:**
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "queued"
}
```

**Time:** < 2 seconds

---

## Test Case 3: Upload Invoice With Metadata
**Objective:** Upload invoice + metadata JSON

### Steps:
1. In Swagger: `/upload` → "Try it out"
2. Select PDF file from `data/incoming/`
3. Also select `.meta.json` file
4. Click "Execute"

### Expected Result:
- ✓ Status Code: 200
- ✓ Response contains `job_id`
- ✓ Both files processed

**Time:** < 2 seconds

---

## Test Case 4: Check Job Status - Queued
**Objective:** Verify job status immediately after upload

### Setup:
- Have `job_id` from Test Case 2

### Steps:
1. In Swagger: `/jobs/{job_id}` endpoint
2. Paste `job_id` value
3. Click "Execute"

### Expected Result:
- ✓ Status Code: 200
- ✓ `status` field = `"queued"` or `"processing"`
- ✓ Contains timestamp

**Response Example:**
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "queued",
  "updated_at": "2026-04-26T10:30:45.123456+00:00"
}
```

**Time:** < 1 second

---

## Test Case 5: Check Job Status - Processing
**Objective:** Verify job transitions to processing

### Setup:
- Wait 5-10 seconds after Test Case 4

### Steps:
1. Repeat Test Case 4 step

### Expected Result:
- ✓ Status Code: 200
- ✓ `status` field = `"processing"`
- ✓ `updated_at` timestamp updated

**Time:** 5-10 seconds to setup

---

## Test Case 6: Poll Job Status - Completion
**Objective:** Wait for job to complete

### Setup:
- Have job_id from earlier
- Poll every 30 seconds

### Steps:
1. Repeatedly call `/jobs/{job_id}`
2. Monitor `status` field
3. Stop when `status` = `"completed"`

### Expected Result:
- ✓ Eventually `status` = `"completed"`
- ✓ Within 5 minutes typically

**Time:** 2-5 minutes

**Status Timeline:**
```
queued (0-10s)
  ↓
processing (10s-4min)
  ↓
completed (4-5min)
```

---

## Test Case 7: Get JSON Audit Report
**Objective:** Retrieve structured report (only after completion)

### Setup:
- Job must be completed
- Have `job_id`

### Steps:
1. In Swagger: `/jobs/{job_id}/report`
2. Paste `job_id`
3. Click "Execute"

### Expected Result:
- ✓ Status Code: 200
- ✓ Contains `validation_passed` boolean
- ✓ Contains `validation_findings` array
- ✓ Contains `detected_language`
- ✓ Contains `extraction_confidence` float

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

**Failure Case:**
- If job still processing: Status Code 404
- Wait longer and retry

**Time:** < 1 second

---

## Test Case 8: Get Markdown Report
**Objective:** Retrieve detailed Markdown report

### Setup:
- Job must be completed
- Have `job_id`

### Steps:
1. In Swagger: `/jobs/{job_id}/report/markdown`
2. Paste `job_id`
3. Click "Execute"

### Expected Result:
- ✓ Status Code: 200
- ✓ Response is long text (Markdown formatted)
- ✓ Contains structured report with headers
- ✓ Contains validation details

**Response Example:**
```markdown
# Invoice Audit Report

**Job ID:** 550e8400-e29b-41d4-a716-446655440000
**Status:** Completed

## Extraction Results
- Language: English
- Confidence: 95%

## Validation Findings
- No issues detected

...
```

**Time:** < 1 second

---

## Test Case 9: Query - Simple Question
**Objective:** Test RAG query functionality

### Setup:
- Job must be completed
- Have `job_id`

### Steps:
1. In Swagger: POST `/query`
2. Fill request body:
   ```json
   {
     "query": "What is the total amount?",
     "job_id": "YOUR_JOB_ID"
   }
   ```
3. Click "Execute"

### Expected Result:
- ✓ Status Code: 200
- ✓ Contains `answer` field
- ✓ Answer is human-readable text

**Response Example:**
```json
{
  "query": "What is the total amount?",
  "answer": "The total amount is $1,250.00",
  "sources": ["invoice_collection"]
}
```

**Time:** 2-5 seconds

---

## Test Case 10: Query - Multiple Questions
**Objective:** Test multiple queries on same invoice

### Setup:
- Job completed
- Have `job_id`

### Steps:
1. Repeat Test Case 9 with different queries:
   - "Who is the vendor?"
   - "What is the PO number?"
   - "What is the invoice date?"
   - "What line items are included?"

### Expected Result:
- ✓ All queries return Status Code 200
- ✓ All responses contain answers
- ✓ Answers are relevant to questions

**Time:** 10-15 seconds total

---

## Test Case 11: Error Handling - Invalid Job ID
**Objective:** Verify proper error handling

### Steps:
1. In Swagger: `/jobs/invalid-id-12345`
2. Click "Execute"

### Expected Result:
- ✓ Status Code: 404
- ✓ Error message: "job not found"

**Time:** < 1 second

---

## Test Case 12: Error Handling - Report Too Early
**Objective:** Test accessing report before completion

### Setup:
- Just uploaded invoice (status = queued)
- Have `job_id`

### Steps:
1. Immediately try `/jobs/{job_id}/report`
2. Click "Execute"

### Expected Result:
- ✓ Status Code: 404
- ✓ Error: "report not ready"

**Time:** < 1 second

---

## Test Case 13: Multi-Language - English
**Objective:** Process English invoice

### Setup:
- Have English invoice (INV_EN_*.pdf)

### Steps:
1. Upload English invoice
2. Wait for completion
3. Get report
4. Verify language detection

### Expected Result:
- ✓ `detected_language` = "en" or "english"
- ✓ High confidence score
- ✓ Proper extraction

**Time:** 3-5 minutes

---

## Test Case 14: Multi-Language - German
**Objective:** Process German invoice

### Setup:
- Have German invoice (INV_DE_*.pdf)

### Steps:
1. Upload German invoice
2. Wait for completion
3. Get report
4. Verify language detection

### Expected Result:
- ✓ `detected_language` = "de" or "german"
- ✓ Proper character encoding
- ✓ Correct extraction

**Time:** 3-5 minutes

---

## Test Case 15: Multi-Language - Spanish
**Objective:** Process Spanish invoice

### Setup:
- Have Spanish invoice (INV_ES_*.pdf)

### Steps:
1. Upload Spanish invoice
2. Wait for completion
3. Get report

### Expected Result:
- ✓ `detected_language` = "es" or "spanish"
- ✓ Proper accent handling
- ✓ Correct validation

**Time:** 3-5 minutes

---

## Test Case 16: Malformed Invoice
**Objective:** Handle corrupted/malformed PDF

### Setup:
- Have malformed invoice (INV_EN_006_malformed.pdf)

### Steps:
1. Upload malformed file
2. Wait for completion
3. Check result

### Expected Result:
- ✓ Job completes (doesn't crash)
- ✓ Status shows completion
- ✓ Appropriate error message OR partial extraction

**Time:** 2-3 minutes

---

## Test Case 17: Concurrent Uploads
**Objective:** Test multiple simultaneous uploads

### Steps:
1. Upload Invoice 1
2. Immediately upload Invoice 2 (don't wait)
3. Check status of both jobs
4. Wait for both to complete

### Expected Result:
- ✓ Both job_ids unique
- ✓ Both jobs progress independently
- ✓ Both complete successfully

**Time:** 5-10 minutes

---

## Test Case 18: Large File Handling
**Objective:** Test with large PDF

### Setup:
- Have large invoice PDF (20+ MB)

### Steps:
1. Upload large file
2. Monitor upload

### Expected Result:
- ✓ Upload succeeds or returns appropriate error
- ✓ Processing handles large files
- ✓ Completes within reasonable time

**Time:** Depends on file size

---

## Test Case 19: Session Persistence
**Objective:** Verify data persists across requests

### Steps:
1. Upload invoice
2. Get status
3. (Kill and restart server - optional)
4. Get same report again

### Expected Result:
- ✓ Report still accessible
- ✓ Data not lost
- ✓ Consistent results

**Time:** 5 minutes

---

## Test Summary Table

| Test | Type | Time | Critical |
|------|------|------|----------|
| 1. Server Health | Quick | <5s | ✓ YES |
| 2. Upload Basic | Quick | <2s | ✓ YES |
| 3. Upload w/ Metadata | Quick | <2s | ✗ No |
| 4. Job Status Queued | Quick | <1s | ✓ YES |
| 5. Job Status Processing | Quick | 5s | ✓ YES |
| 6. Job Completion | Slow | 5m | ✓ YES |
| 7. JSON Report | Slow | 5m | ✓ YES |
| 8. Markdown Report | Slow | 5m | ✓ YES |
| 9. Query Single | Slow | 5m | ✓ YES |
| 10. Query Multiple | Slow | 5m | ✓ YES |
| 11. Error Invalid ID | Quick | <1s | ✗ No |
| 12. Error Too Early | Quick | 2m | ✗ No |
| 13. Language EN | Slow | 5m | ✗ No |
| 14. Language DE | Slow | 5m | ✗ No |
| 15. Language ES | Slow | 5m | ✗ No |
| 16. Malformed | Slow | 3m | ✗ No |
| 17. Concurrent | Slow | 10m | ✗ No |
| 18. Large File | Slow | Varies | ✗ No |
| 19. Persistence | Slow | 5m | ✗ No |

---

## Quick Test Flow (< 15 minutes)

1. ✓ Test 1: Server Health (30s)
2. ✓ Test 2: Upload (30s)
3. ✓ Test 4-6: Status polling (5m)
4. ✓ Test 7: JSON Report (1m)
5. ✓ Test 9: Query (2m)

**Total: ~10 minutes**

---

## Full Test Flow (~ 60 minutes)

Run all 19 test cases for comprehensive validation
