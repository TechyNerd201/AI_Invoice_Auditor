# AI Invoice Auditor - Test Suite Documentation

## Directory Structure

```
tests/
├── __init__.py
├── conftest.py                 # Pytest configuration & fixtures
├── integration/
│   ├── __init__.py
│   └── test_api.py             # API integration tests
├── data/                        # Test data directory
└── output/                      # Test output directory (created at runtime)
```

## Running Tests

### Prerequisites
```bash
pip install pytest requests python-dotenv
```

### Run All Tests
```bash
pytest tests/ -v
```

### Run Specific Test File
```bash
pytest tests/integration/test_api.py -v
```

### Run Specific Test Class
```bash
pytest tests/integration/test_api.py::TestUpload -v
```

### Run Specific Test
```bash
pytest tests/integration/test_api.py::TestUpload::test_upload_invoice -v
```

### Run with Output
```bash
pytest tests/integration/test_api.py -v -s
```

### Run Slow Tests (takes 5-10 minutes)
```bash
pytest tests/integration/test_api.py -v -m slow
```

### Skip Slow Tests
```bash
pytest tests/integration/test_api.py -v -m "not slow"
```

### Run with Coverage Report
```bash
pip install pytest-cov
pytest tests/ --cov=. --cov-report=html
```

---

## Test Organization

### TestServerHealth
- ✓ test_server_running - Verify server is accessible
- ✓ test_docs_endpoint - Verify API docs are available

### TestUpload
- ✓ test_upload_invoice - Upload single invoice
- ✓ test_upload_with_metadata - Upload with metadata JSON
- ✓ test_upload_missing_file - Error handling for missing files

### TestJobStatus
- ✓ test_get_job_status - Retrieve job status
- ✓ test_nonexistent_job - Handle non-existent job gracefully

### TestJobWaiting (SLOW - ~3 min)
- ✓ test_wait_for_job_completion - Poll until job completes

### TestReports (SLOW - ~3-5 min each)
- ✓ test_get_json_report - Retrieve structured JSON report
- ✓ test_get_markdown_report - Retrieve formatted Markdown report

### TestQuery (SLOW - ~2-3 min each)
- ✓ test_query_after_upload - Single query test
- ✓ test_multiple_queries - Multiple queries on same invoice

### TestMultiLanguage (SLOW - ~3 min each)
- ✓ test_english_invoice - Process English invoices
- ✓ test_german_invoice - Process German invoices
- ✓ test_spanish_invoice - Process Spanish invoices

---

## Test Fixtures (conftest.py)

Available fixtures for tests:

```python
@pytest.fixture
def api_client(api_base_url):
    """API client instance"""

@pytest.fixture
def api_base_url():
    """API base URL from env or default http://localhost:8000"""

@pytest.fixture
def sample_invoice_path():
    """Path to any sample invoice"""

@pytest.fixture
def sample_metadata_path():
    """Path to any sample metadata"""

@pytest.fixture
def sample_invoice_en():
    """English invoice specifically"""

@pytest.fixture
def sample_invoice_de():
    """German invoice specifically"""

@pytest.fixture
def sample_invoice_es():
    """Spanish invoice specifically"""
```

### Usage Example:
```python
def test_my_feature(api_client, sample_invoice_path):
    job_id = api_client.upload_invoice(sample_invoice_path)
    assert job_id is not None
```

---

## Quick Test Scenarios

### Scenario 1: Basic Connectivity (30 seconds)
```bash
pytest tests/integration/test_api.py::TestServerHealth -v
```
**Tests:** Server running, docs accessible

### Scenario 2: Upload Test (1 minute)
```bash
pytest tests/integration/test_api.py::TestUpload -v
```
**Tests:** File upload, metadata upload, error handling

### Scenario 3: Full Flow (5 minutes)
```bash
pytest tests/integration/test_api.py::TestServerHealth tests/integration/test_api.py::TestUpload tests/integration/test_api.py::TestJobWaiting -v
```
**Tests:** Server → Upload → Wait for completion

### Scenario 4: Complete End-to-End (15 minutes)
```bash
pytest tests/integration/test_api.py -v --tb=short
```
**Tests:** Everything including multi-language

### Scenario 5: Quick Test (exclude slow)
```bash
pytest tests/ -v -m "not slow"
```
**Tests:** Health, upload, status checks

---

## Environment Configuration

Create `.env` file in project root:
```env
API_BASE_URL=http://localhost:8000
GROQ_API_KEY=your_key
HUGGINGFACE_API_KEY=your_key
```

Or set defaults in conftest.py

---

## Expected Test Results

### Passing Scenario
```
tests/integration/test_api.py::TestServerHealth::test_server_running PASSED
tests/integration/test_api.py::TestUpload::test_upload_invoice PASSED
tests/integration/test_api.py::TestJobWaiting::test_wait_for_job_completion PASSED
tests/integration/test_api.py::TestReports::test_get_json_report PASSED
tests/integration/test_api.py::TestQuery::test_query_after_upload PASSED
```

### Failing Scenario
```
FAILED tests/integration/test_api.py::TestServerHealth::test_server_running
Error: Server not responding at http://localhost:8000
→ Solution: Start server with: python main.py
```

---

## Troubleshooting

### Tests Can't Find Sample Invoices
- Ensure PDF files exist in `data/incoming/`
- Fixtures will skip tests gracefully if files missing

### Test Timeout
- Slow tests have 3-5 minute timeout
- Can extend with: `-o timeout=300`
- Job processing typically takes 2-3 minutes

### API Connection Failed
- Verify server running: `python main.py`
- Check `API_BASE_URL` in `.env`
- Verify firewall allows localhost:8000

### Import Errors
```bash
pip install -e .
```

---

## CI/CD Integration

### GitHub Actions Example
```yaml
- name: Run Tests
  run: |
    pytest tests/ -v --tb=short
```

### Pre-commit Hook
```bash
#!/bin/bash
pytest tests/integration/test_api.py::TestServerHealth -v
```

---

## Performance Tips

1. **Parallel execution** (with pytest-xdist):
   ```bash
   pip install pytest-xdist
   pytest tests/ -v -n auto
   ```

2. **Cache results**:
   ```bash
   pytest tests/ -v --cache-clear
   ```

3. **Show slowest tests**:
   ```bash
   pytest tests/ -v --durations=10
   ```

---

## Test Coverage

Target coverage: > 80%

Generate coverage report:
```bash
pytest tests/ --cov=API --cov=services --cov-report=html
open htmlcov/index.html
```

---

## Contributing Tests

1. Add test functions to appropriate class in `tests/integration/test_api.py`
2. Use descriptive names: `test_<feature>_<scenario>`
3. Add docstrings explaining what's being tested
4. Mark slow tests with `@pytest.mark.slow`
5. Use fixtures for common setups
6. Run: `pytest tests/ -v` before committing
