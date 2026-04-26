"""
Test cases for AI Invoice Auditor API

Run with: pytest test_api.py -v
Or manually test endpoints using:
  python test_api.py
"""

import requests
import json
import time
from pathlib import Path
from typing import Optional

# API Base URL
BASE_URL = "http://localhost:8000"

# Test data directory
TEST_DATA_DIR = Path(__file__).resolve().parent / "data" / "incoming"
TEST_OUTPUT_DIR = Path(__file__).resolve().parent / "test_output"
TEST_OUTPUT_DIR.mkdir(exist_ok=True)


class APITester:
    def __init__(self, base_url: str = BASE_URL):
        self.base_url = base_url
        self.session = requests.Session()

    def test_server_health(self) -> bool:
        """Test if server is responding"""
        print("\n✓ Testing server health...")
        try:
            response = self.session.get(f"{self.base_url}/docs")
            if response.status_code == 200:
                print("  ✓ Server is running and docs are accessible")
                return True
            else:
                print(f"  ✗ Server returned status {response.status_code}")
                return False
        except requests.exceptions.ConnectionError:
            print(f"  ✗ Cannot connect to server at {self.base_url}")
            print(f"    Make sure server is running: python main.py")
            return False

    def upload_invoice(self, invoice_path: Path, metadata_path: Optional[Path] = None) -> Optional[str]:
        """
        Upload an invoice file and optionally metadata
        Returns: job_id
        """
        print(f"\n✓ Uploading invoice: {invoice_path.name}")
        
        if not invoice_path.exists():
            print(f"  ✗ File not found: {invoice_path}")
            return None

        files = {
            "invoice_file": (invoice_path.name, open(invoice_path, "rb"), "application/pdf"),
        }
        
        if metadata_path and metadata_path.exists():
            files["metadata_file"] = (metadata_path.name, open(metadata_path, "rb"), "application/json")
            print(f"  - Also uploading metadata: {metadata_path.name}")

        try:
            response = self.session.post(f"{self.base_url}/upload", files=files)
            
            for file_obj in files.values():
                file_obj[1].close()

            if response.status_code == 200:
                data = response.json()
                job_id = data.get("job_id")
                status = data.get("status")
                print(f"  ✓ Upload successful!")
                print(f"    - Job ID: {job_id}")
                print(f"    - Status: {status}")
                return job_id
            else:
                print(f"  ✗ Upload failed with status {response.status_code}")
                print(f"    Response: {response.text}")
                return None
        except Exception as e:
            print(f"  ✗ Upload error: {e}")
            return None

    def check_job_status(self, job_id: str) -> Optional[dict]:
        """Get the current status of a job"""
        print(f"\n✓ Checking job status: {job_id}")
        
        try:
            response = self.session.get(f"{self.base_url}/jobs/{job_id}")
            
            if response.status_code == 200:
                data = response.json()
                status = data.get("status")
                print(f"  ✓ Status: {status}")
                print(f"    Response: {json.dumps(data, indent=2)}")
                return data
            elif response.status_code == 404:
                print(f"  ✗ Job not found")
                return None
            else:
                print(f"  ✗ Error: {response.status_code}")
                return None
        except Exception as e:
            print(f"  ✗ Error: {e}")
            return None

    def get_audit_report(self, job_id: str) -> Optional[dict]:
        """Get the JSON audit report (only available when job is completed)"""
        print(f"\n✓ Retrieving audit report (JSON): {job_id}")
        
        try:
            response = self.session.get(f"{self.base_url}/jobs/{job_id}/report")
            
            if response.status_code == 200:
                data = response.json()
                print(f"  ✓ Report retrieved!")
                print(f"    - Validation Passed: {data.get('validation_passed')}")
                print(f"    - Language: {data.get('detected_language')}")
                print(f"    - Confidence: {data.get('extraction_confidence')}")
                print(f"    - Findings: {len(data.get('validation_findings', []))} issues found")
                
                # Save report
                output_file = TEST_OUTPUT_DIR / f"{job_id}_report.json"
                with open(output_file, "w") as f:
                    json.dump(data, f, indent=2)
                print(f"    - Saved to: {output_file}")
                
                return data
            elif response.status_code == 404:
                print(f"  ⚠ Report not ready (job still processing)")
                return None
            else:
                print(f"  ✗ Error: {response.status_code}")
                return None
        except Exception as e:
            print(f"  ✗ Error: {e}")
            return None

    def get_markdown_report(self, job_id: str) -> Optional[str]:
        """Get the full Markdown audit report"""
        print(f"\n✓ Retrieving audit report (Markdown): {job_id}")
        
        try:
            response = self.session.get(f"{self.base_url}/jobs/{job_id}/report/markdown")
            
            if response.status_code == 200:
                text = response.text
                print(f"  ✓ Markdown report retrieved ({len(text)} chars)")
                
                # Save report
                output_file = TEST_OUTPUT_DIR / f"{job_id}_report.md"
                with open(output_file, "w", encoding="utf-8") as f:
                    f.write(text)
                print(f"    - Saved to: {output_file}")
                
                return text
            elif response.status_code == 404:
                print(f"  ⚠ Report not ready (job still processing)")
                return None
            else:
                print(f"  ✗ Error: {response.status_code}")
                return None
        except Exception as e:
            print(f"  ✗ Error: {e}")
            return None

    def query_invoice(self, query: str, job_id: Optional[str] = None) -> Optional[dict]:
        """Ask a question about ingested invoices (RAG)"""
        print(f"\n✓ Querying: '{query}'")
        if job_id:
            print(f"  - Scope: job_id={job_id}")
        
        payload = {
            "query": query,
            "job_id": job_id,
        }
        
        try:
            response = self.session.post(
                f"{self.base_url}/query",
                json=payload,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                data = response.json()
                answer = data.get("answer", "")
                print(f"  ✓ Answer: {answer[:200]}...")
                return data
            else:
                print(f"  ✗ Error: {response.status_code}")
                print(f"    Response: {response.text}")
                return None
        except Exception as e:
            print(f"  ✗ Error: {e}")
            return None

    def wait_for_completion(self, job_id: str, timeout: int = 60, poll_interval: int = 5) -> bool:
        """Poll job status until completion (with timeout)"""
        print(f"\n✓ Waiting for job completion (timeout: {timeout}s)...")
        
        start_time = time.time()
        while time.time() - start_time < timeout:
            status_data = self.check_job_status(job_id)
            if status_data:
                status = status_data.get("status")
                if status == "completed":
                    print(f"  ✓ Job completed!")
                    return True
                elif status == "failed":
                    print(f"  ✗ Job failed!")
                    error = status_data.get("error")
                    if error:
                        print(f"    Error: {error}")
                    return False
            
            print(f"  - Waiting {poll_interval}s before next check...")
            time.sleep(poll_interval)
        
        print(f"  ✗ Timeout: Job did not complete within {timeout}s")
        return False


def main():
    """Run comprehensive test suite"""
    print("=" * 70)
    print("AI Invoice Auditor - API Test Suite")
    print("=" * 70)

    tester = APITester()

    # Test 1: Server Health
    if not tester.test_server_health():
        print("\n✗ Cannot connect to server. Please start it first:")
        print("  python main.py")
        return

    # Test 2: Find test invoices
    print("\n" + "=" * 70)
    print("TEST CASE 1: Upload Invoice")
    print("=" * 70)
    
    if not TEST_DATA_DIR.exists():
        print(f"⚠ Test data directory not found: {TEST_DATA_DIR}")
        print("  Creating sample test instructions...")
        return

    # Find invoice files
    invoice_files = list(TEST_DATA_DIR.glob("*.pdf")) + list(TEST_DATA_DIR.glob("*.PDF"))
    metadata_files = list(TEST_DATA_DIR.glob("*.meta.json"))

    if not invoice_files:
        print(f"⚠ No PDF files found in {TEST_DATA_DIR}")
        print("  Place sample invoice PDFs there to test.")
        return

    # Test with first invoice
    invoice_file = invoice_files[0]
    metadata_file = None
    
    # Try to find matching metadata
    if metadata_files:
        metadata_file = metadata_files[0]

    job_id = tester.upload_invoice(invoice_file, metadata_file)
    if not job_id:
        print("\n✗ Failed to upload invoice")
        return

    # Test 3: Check job status
    print("\n" + "=" * 70)
    print("TEST CASE 2: Check Job Status (immediate)")
    print("=" * 70)
    tester.check_job_status(job_id)

    # Test 4: Wait for completion
    print("\n" + "=" * 70)
    print("TEST CASE 3: Wait for Job Completion")
    print("=" * 70)
    if tester.wait_for_completion(job_id, timeout=120, poll_interval=10):
        
        # Test 5: Get audit report
        print("\n" + "=" * 70)
        print("TEST CASE 4: Get Audit Report (JSON)")
        print("=" * 70)
        report = tester.get_audit_report(job_id)

        # Test 6: Get markdown report
        print("\n" + "=" * 70)
        print("TEST CASE 5: Get Audit Report (Markdown)")
        print("=" * 70)
        tester.get_markdown_report(job_id)

        # Test 7: Query endpoint (RAG)
        print("\n" + "=" * 70)
        print("TEST CASE 6: Query Invoice (RAG)")
        print("=" * 70)
        test_queries = [
            "What is the total amount?",
            "Who is the vendor?",
            "What is the PO number?",
            "What is the invoice date?",
        ]
        
        for query in test_queries:
            result = tester.query_invoice(query, job_id=job_id)
            if result:
                time.sleep(2)  # Rate limiting
            else:
                break

    print("\n" + "=" * 70)
    print("Test Suite Complete!")
    print("=" * 70)
    print(f"\n✓ Test output saved to: {TEST_OUTPUT_DIR}")


if __name__ == "__main__":
    main()
