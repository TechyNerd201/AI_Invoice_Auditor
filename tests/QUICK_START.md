# 🚀 Test Suite - Quick Start Guide

## 📁 Test Folder Structure

```
tests/
├── __init__.py                    # Package init
├── conftest.py                    # Pytest fixtures & config
├── pytest.ini                     # Pytest configuration
├── run_tests.py                   # Quick test runner
├── requirements-test.txt          # Test dependencies
├── README.md                       # Full documentation
├── QUICK_START.md                 # This file
├── MANUAL_TEST_CASES.md           # Manual testing guide
├── postman_collection.json        # Postman import
├── integration/
│   ├── __init__.py
│   └── test_api.py                # Integration tests
├── data/                          # Test data directory
└── output/                        # Test results (created at runtime)
```

---

## ⚡ Quick Start (5 minutes)

### 1️⃣ Install Test Dependencies
```bash
pip install -r tests/requirements-test.txt
```

### 2️⃣ Start Server (Terminal 1)
```bash
python main.py
```

### 3️⃣ Run Tests (Terminal 2)

**Option A: Automated Test Runner** (Recommended)
```bash
python tests/run_tests.py
```

**Option B: Pytest Direct**
```bash
pytest tests/ -v
```

**Option C: Quick Smoke Tests Only**
```bash
pytest tests/ -v -m "not slow"
```

### 4️⃣ View Results
- Tests pass: ✅ Green
- Tests fail: ❌ Red
- Slow tests: 🐢 Marked with `[slow]`

---

## 🧪 Common Test Commands

### Run All Tests (5-15 minutes)
```bash
pytest tests/ -v
```

### Run Quick Tests Only (< 2 minutes)
```bash
pytest tests/ -v -m "not slow"
```

### Run Specific Test
```bash
pytest tests/integration/test_api.py::TestUpload::test_upload_invoice -v
```

### Run with Output Display
```bash
pytest tests/ -v -s
```

### Generate Coverage Report
```bash
pytest tests/ --cov=API --cov=services --cov-report=html
open htmlcov/index.html
```

### Generate HTML Report
```bash
pytest tests/ --html=tests/output/report.html
```

### Run Test Runner Script
```bash
python tests/run_tests.py --full --coverage --html
```

---

## 🎯 Test Categories

### Quick Tests (No waiting required)
```bash
pytest tests/ -v -m "not slow"
```
- Server health check
- Upload functionality
- Error handling
- Status retrieval

**Time:** < 2 minutes

### Slow Tests (Requires processing time)
```bash
pytest tests/ -v -m "slow"
```
- Job completion waiting
- Report retrieval
- RAG queries
- Multi-language support

**Time:** 3-15 minutes each

### Specific Test Classes
```bash
# Test server connectivity
pytest tests/integration/test_api.py::TestServerHealth -v

# Test upload functionality
pytest tests/integration/test_api.py::TestUpload -v

# Test job status
pytest tests/integration/test_api.py::TestJobStatus -v

# Test reports
pytest tests/integration/test_api.py::TestReports -v

# Test queries
pytest tests/integration/test_api.py::TestQuery -v

# Test multi-language
pytest tests/integration/test_api.py::TestMultiLanguage -v
```

---

## 🛠️ Test Runner Script

Use `run_tests.py` for convenience:

```bash
# Recommended: Quick tests
python tests/run_tests.py

# Full suite
python tests/run_tests.py --full

# With coverage
python tests/run_tests.py --full --coverage

# With HTML report
python tests/run_tests.py --full --html

# Smoke tests only
python tests/run_tests.py --smoke

# Verbose output
python tests/run_tests.py --verbose

# Custom marker
python tests/run_tests.py -m "not slow"

# Show help
python tests/run_tests.py --help
```

---

## 📊 Understanding Test Results

### ✅ Passing Test
```
tests/integration/test_api.py::TestUpload::test_upload_invoice PASSED
```

### ❌ Failing Test
```
tests/integration/test_api.py::TestUpload::test_upload_invoice FAILED
AssertionError: Failed to upload invoice
```

### ⏭️ Skipped Test
```
tests/integration/test_api.py::TestUpload::test_upload_invoice SKIPPED
(reason: No sample invoice found)
```

### ⏱️ Slow Test
```
tests/integration/test_api.py::TestJobWaiting::test_wait_for_job_completion PASSED [slow]
```

---

## 🐛 Troubleshooting Tests

### ❌ "Cannot connect to server"
```
Error: Server not responding at http://localhost:8000
```
**Fix:** Start server in another terminal
```bash
python main.py
```

### ❌ "No sample invoice found"
```
SKIPPED: No sample invoice found
```
**Fix:** Ensure PDFs exist in `data/incoming/`
```bash
ls data/incoming/*.pdf
```

### ❌ "Test timeout"
```
Timeout: Job did not complete within timeout
```
**Fix:** Tests have 3-min timeout. Increase with:
```bash
pytest tests/ -v --timeout=600
```

### ❌ "ImportError"
```
ImportError: cannot import name 'HuggingFaceEndpointEmbeddings'
```
**Fix:** Reinstall dependencies
```bash
pip install -r tests/requirements-test.txt
```

### ❌ "API Key not found"
```
Error: GROQ_API_KEY not found in environment
```
**Fix:** Verify `.env` file has valid API keys

---

## 📈 Test Performance

| Phase | Time | Note |
|-------|------|------|
| Quick Tests | < 2 min | Recommended for CI/CD |
| Full Tests | 10-15 min | For comprehensive validation |
| With Coverage | +2-3 min | Additional overhead |
| HTML Report | +1 min | Generate pretty report |

---

## 🔄 Continuous Testing

### Watch Mode (Re-run on file change)
```bash
pip install pytest-watch
ptw tests/ -- -v
```

### Parallel Execution (Faster)
```bash
pip install pytest-xdist
pytest tests/ -v -n auto
```

### Multiple Python Versions
```bash
pip install tox
tox -c tests/tox.ini
```

---

## 📚 Documentation Files

| File | Purpose |
|------|---------|
| `README.md` | Complete test documentation |
| `QUICK_START.md` | This file |
| `MANUAL_TEST_CASES.md` | Step-by-step manual tests |
| `conftest.py` | Pytest fixtures & config |
| `pytest.ini` | Pytest settings |
| `requirements-test.txt` | Python test dependencies |

---

## 🔗 Integration with Tools

### GitHub Actions
```yaml
- name: Run Tests
  run: pytest tests/ -v
```

### Pre-commit Hook
```bash
#!/bin/bash
pytest tests/integration/test_api.py::TestServerHealth -v
exit $?
```

### VS Code Test Explorer
1. Install: "Python Test Explorer"
2. Select pytest
3. Discovers tests automatically
4. Run from UI

### PyCharm
1. Right-click `tests/` folder
2. Select "Run pytest in tests"
3. View results in test panel

---

## ✨ Best Practices

1. **Always run quick tests first**
   ```bash
   pytest tests/ -v -m "not slow"
   ```

2. **Check server is running**
   ```bash
   curl http://localhost:8000/docs
   ```

3. **Use fixtures for common setup**
   ```python
   def test_my_feature(api_client, sample_invoice_path):
       # fixtures auto-injected
   ```

4. **Mark slow tests appropriately**
   ```python
   @pytest.mark.slow
   def test_long_running():
       pass
   ```

5. **Generate reports for CI/CD**
   ```bash
   pytest tests/ --html=report.html --cov
   ```

---

## 🆘 Support

### Check Logs
```bash
# Server logs (Terminal 1)
# Look for errors during test execution

# Test output (Terminal 2)
pytest tests/ -v -s
# -s captures all print statements
```

### Debug Mode
```bash
pytest tests/ -v -s --pdb
# Enters Python debugger on failure
```

### Check API Health
```bash
curl http://localhost:8000/docs
curl http://localhost:8000/jobs/test-id
```

---

## 🎉 Next Steps

1. ✅ Run quick tests: `python tests/run_tests.py`
2. ✅ Check results
3. ✅ Read `README.md` for advanced options
4. ✅ Write new tests following the patterns
5. ✅ Submit to CI/CD pipeline

---

**Happy Testing! 🚀**
