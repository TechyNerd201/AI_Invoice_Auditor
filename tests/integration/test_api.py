"""
Integration tests for AI Invoice Auditor API

Run with: pytest tests/integration/test_api.py -v
Or: python -m pytest tests/integration/test_api.py -v -s
"""

import requests
import json
import time
from pathlib import Path
from typing import Optional
import pytest


class TestAPIClient:
    """API Client for testing"""
    
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.session = requests.Session()

    def health_check(self) -> bool:
        """Check if server is running"""
        try:
            response = self.session.get(f"{self.base_url}/docs", timeout=5)
            return response.status_code == 200
        except:
            return False

    def upload_invoice(self, invoice_path: Path, metadata_path: Optional[Path] = None) -> Optional[str]:
        """Upload invoice and return job_id"""
        if not invoice_path.exists():
            raise FileNotFoundError(f"Invoice not found: {invoice_path}")

        files = {
            "invoice_file": (invoice_path.name, open(invoice_path, "rb"), "application/pdf"),
        }
        
        if metadata_path and metadata_path.exists():
            files["metadata_file"] = (metadata_path.name, open(metadata_path, "rb"), "application/json")

        try:
            response = self.session.post(f"{self.base_url}/upload", files=files)
            for f in files.values():
                f[1].close()
            
            if response.status_code == 200:
                return response.json().get("job_id")
            return None
        except Exception as e:
            for f in files.values():
                f[1].close()
            raise

    def get_job_status(self, job_id: str) -> Optional[dict]:
        """Get job status"""
        try:
            response = self.session.get(f"{self.base_url}/jobs/{job_id}")
            if response.status_code == 200:
                return response.json()
            return None
        except:
            return None

    def get_audit_report(self, job_id: str) -> Optional[dict]:
        """Get JSON audit report"""
        try:
            response = self.session.get(f"{self.base_url}/jobs/{job_id}/report")
            if response.status_code == 200:
                return response.json()
            return None
        except:
            return None

    def get_markdown_report(self, job_id: str) -> Optional[str]:
        """Get Markdown report"""
        try:
            response = self.session.get(f"{self.base_url}/jobs/{job_id}/report/markdown")
            if response.status_code == 200:
                return response.text
            return None
        except:
            return None

    def query_invoice(self, query: str, job_id: Optional[str] = None) -> Optional[dict]:
        """Query invoice using RAG"""
        payload = {"query": query, "job_id": job_id}
        try:
            response = self.session.post(
                f"{self.base_url}/query",
                json=payload,
                headers={"Content-Type": "application/json"}
            )
            if response.status_code == 200:
                return response.json()
            return None
        except:
            return None

    def wait_for_completion(self, job_id: str, timeout: int = 120, poll_interval: int = 10) -> bool:
        """Wait for job to complete"""
        start_time = time.time()
        while time.time() - start_time < timeout:
            status_data = self.get_job_status(job_id)
            if status_data:
                status = status_data.get("status")
                if status in ["completed", "failed"]:
                    return status == "completed"
            time.sleep(poll_interval)
        return False


@pytest.fixture
def api_client(api_base_url):
    """Create API client"""
    return TestAPIClient(api_base_url)


class TestServerHealth:
    """Test server connectivity"""

    def test_server_running(self, api_client):
        """Test that server is running and responding"""
        assert api_client.health_check(), "Server not responding at {api_client.base_url}"

    def test_docs_endpoint(self, api_base_url):
        """Test that documentation is accessible"""
        response = requests.get(f"{api_base_url}/docs")
        assert response.status_code == 200, "Documentation endpoint not accessible"


class TestUpload:
    """Test invoice upload functionality"""

    def test_upload_invoice(self, api_client, sample_invoice_path):
        """Test uploading an invoice"""
        if not sample_invoice_path:
            pytest.skip("No sample invoice found")
        
        job_id = api_client.upload_invoice(sample_invoice_path)
        assert job_id is not None, "Failed to upload invoice"
        assert isinstance(job_id, str), "Job ID should be string"
        assert len(job_id) > 0, "Job ID should not be empty"

    def test_upload_with_metadata(self, api_client, sample_invoice_path, sample_metadata_path):
        """Test uploading invoice with metadata"""
        if not sample_invoice_path or not sample_metadata_path:
            pytest.skip("Sample files not found")
        
        job_id = api_client.upload_invoice(sample_invoice_path, sample_metadata_path)
        assert job_id is not None, "Failed to upload with metadata"

    def test_upload_missing_file(self, api_client):
        """Test upload with non-existent file"""
        with pytest.raises(FileNotFoundError):
            api_client.upload_invoice(Path("nonexistent.pdf"))


class TestJobStatus:
    """Test job status retrieval"""

    def test_get_job_status(self, api_client, sample_invoice_path):
        """Test getting job status"""
        if not sample_invoice_path:
            pytest.skip("No sample invoice found")
        
        job_id = api_client.upload_invoice(sample_invoice_path)
        assert job_id is not None
        
        status = api_client.get_job_status(job_id)
        assert status is not None, "Failed to get job status"
        assert "job_id" in status, "Status missing job_id"
        assert "status" in status, "Status missing status field"
        assert status["status"] in ["queued", "processing", "completed", "failed"]

    def test_nonexistent_job(self, api_client):
        """Test getting status of non-existent job"""
        status = api_client.get_job_status("nonexistent-id-12345")
        assert status is None, "Should return None for nonexistent job"


class TestJobWaiting:
    """Test waiting for job completion"""

    @pytest.mark.slow
    def test_wait_for_job_completion(self, api_client, sample_invoice_path):
        """Test waiting for job to complete"""
        if not sample_invoice_path:
            pytest.skip("No sample invoice found")
        
        job_id = api_client.upload_invoice(sample_invoice_path)
        assert job_id is not None
        
        # Wait for completion (with shorter timeout for testing)
        completed = api_client.wait_for_completion(job_id, timeout=180, poll_interval=15)
        assert completed, "Job did not complete within timeout"


class TestReports:
    """Test report retrieval"""

    @pytest.mark.slow
    def test_get_json_report(self, api_client, sample_invoice_path):
        """Test retrieving JSON audit report"""
        if not sample_invoice_path:
            pytest.skip("No sample invoice found")
        
        job_id = api_client.upload_invoice(sample_invoice_path)
        assert api_client.wait_for_completion(job_id, timeout=180), "Job did not complete"
        
        report = api_client.get_audit_report(job_id)
        assert report is not None, "Failed to get audit report"
        assert "job_id" in report
        assert "validation_passed" in report
        assert "validation_findings" in report
        assert isinstance(report["validation_findings"], list)

    @pytest.mark.slow
    def test_get_markdown_report(self, api_client, sample_invoice_path):
        """Test retrieving Markdown report"""
        if not sample_invoice_path:
            pytest.skip("No sample invoice found")
        
        job_id = api_client.upload_invoice(sample_invoice_path)
        assert api_client.wait_for_completion(job_id, timeout=180), "Job did not complete"
        
        report = api_client.get_markdown_report(job_id)
        assert report is not None, "Failed to get markdown report"
        assert len(report) > 0, "Markdown report is empty"


class TestQuery:
    """Test RAG query functionality"""

    @pytest.mark.slow
    def test_query_after_upload(self, api_client, sample_invoice_path):
        """Test querying invoice after upload"""
        if not sample_invoice_path:
            pytest.skip("No sample invoice found")
        
        job_id = api_client.upload_invoice(sample_invoice_path)
        assert api_client.wait_for_completion(job_id, timeout=180), "Job did not complete"
        
        queries = [
            "What is the total amount?",
            "Who is the vendor?",
            "What is the PO number?",
        ]
        
        for query in queries:
            result = api_client.query_invoice(query, job_id=job_id)
            assert result is not None, f"Query failed: {query}"
            assert "answer" in result or "query" in result

    @pytest.mark.slow
    def test_multiple_queries(self, api_client, sample_invoice_path):
        """Test multiple queries on same invoice"""
        if not sample_invoice_path:
            pytest.skip("No sample invoice found")
        
        job_id = api_client.upload_invoice(sample_invoice_path)
        assert api_client.wait_for_completion(job_id, timeout=180), "Job did not complete"
        
        for i in range(3):
            result = api_client.query_invoice("What is the invoice number?", job_id=job_id)
            assert result is not None, f"Query {i+1} failed"
            time.sleep(1)  # Small delay between queries


class TestMultiLanguage:
    """Test multi-language support"""

    @pytest.mark.slow
    def test_english_invoice(self, api_client, sample_invoice_en):
        """Test English invoice processing"""
        if not sample_invoice_en:
            pytest.skip("No English invoice found")
        
        job_id = api_client.upload_invoice(sample_invoice_en)
        assert api_client.wait_for_completion(job_id, timeout=180)
        
        report = api_client.get_audit_report(job_id)
        assert report is not None
        assert report.get("detected_language") in ["en", "english", "eng", None]

    @pytest.mark.slow
    def test_german_invoice(self, api_client, sample_invoice_de):
        """Test German invoice processing"""
        if not sample_invoice_de:
            pytest.skip("No German invoice found")
        
        job_id = api_client.upload_invoice(sample_invoice_de)
        assert api_client.wait_for_completion(job_id, timeout=180)
        
        report = api_client.get_audit_report(job_id)
        assert report is not None

    @pytest.mark.slow
    def test_spanish_invoice(self, api_client, sample_invoice_es):
        """Test Spanish invoice processing"""
        if not sample_invoice_es:
            pytest.skip("No Spanish invoice found")
        
        job_id = api_client.upload_invoice(sample_invoice_es)
        assert api_client.wait_for_completion(job_id, timeout=180)
        
        report = api_client.get_audit_report(job_id)
        assert report is not None


# Test execution shortcuts
if __name__ == "__main__":
    import sys
    pytest.main([__file__, "-v"] + sys.argv[1:])
