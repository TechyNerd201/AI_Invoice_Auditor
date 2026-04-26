"""
Pytest configuration and fixtures for AI Invoice Auditor tests
"""

import pytest
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Define base paths
TESTS_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = TESTS_DIR.parent
TEST_DATA_DIR = TESTS_DIR / "data"
TEST_OUTPUT_DIR = TESTS_DIR / "output"

# Create output directory
TEST_OUTPUT_DIR.mkdir(exist_ok=True)


@pytest.fixture(scope="session")
def api_base_url():
    """Get API base URL from environment or use default"""
    return os.getenv("API_BASE_URL", "http://localhost:8000")


@pytest.fixture(scope="session")
def test_data_dir():
    """Get test data directory"""
    return TEST_DATA_DIR


@pytest.fixture(scope="session")
def test_output_dir():
    """Get test output directory"""
    return TEST_OUTPUT_DIR


@pytest.fixture(scope="session")
def project_root():
    """Get project root directory"""
    return PROJECT_ROOT


@pytest.fixture
def sample_invoice_path():
    """Get path to sample invoice"""
    invoices = list(PROJECT_ROOT.glob("data/incoming/*.pdf"))
    if invoices:
        return invoices[0]
    return None


@pytest.fixture
def sample_metadata_path():
    """Get path to sample metadata"""
    metadata_files = list(PROJECT_ROOT.glob("data/incoming/*.meta.json"))
    if metadata_files:
        return metadata_files[0]
    return None


@pytest.fixture
def sample_invoice_en():
    """Get English invoice"""
    invoices = list(PROJECT_ROOT.glob("data/incoming/*EN*.pdf"))
    if invoices:
        return invoices[0]
    return None


@pytest.fixture
def sample_invoice_de():
    """Get German invoice"""
    invoices = list(PROJECT_ROOT.glob("data/incoming/*DE*.pdf"))
    if invoices:
        return invoices[0]
    return None


@pytest.fixture
def sample_invoice_es():
    """Get Spanish invoice"""
    invoices = list(PROJECT_ROOT.glob("data/incoming/*ES*.pdf"))
    if invoices:
        return invoices[0]
    return None
