import unittest  # Import the standard Python testing framework
import os  # Import os to check for file existence
import shutil  # Import shutil to clean up directories
from fastapi.testclient import TestClient  # Import TestClient to simulate web requests
from main import app  # Import our FastAPI app
from file_manager import UPLOAD_DIR  # Import the upload directory constant

# Create a test client that will make requests to our app
client = TestClient(app)

class TestMainApp(unittest.TestCase):

    def setUp(self):
        # Run before every test: Clean up the upload directory to start fresh
        if os.path.exists(UPLOAD_DIR):
            shutil.rmtree(UPLOAD_DIR)

    def tearDown(self):
        # Run after every test: Clean up the upload directory
        if os.path.exists(UPLOAD_DIR):
            shutil.rmtree(UPLOAD_DIR)

    def test_upload_file_endpoint(self):
        # Define a fake filename and some fake content
        filename = "test_report.xlsx"
        file_content = b"fake excel content"

        # Send a POST request to "/uploadfile/" with the fake file
        # 'files' dictionary format: {'field_name': ('filename', content, 'content_type')}
        response = client.post(
            "/uploadfile/",
            files={"file": (filename, file_content, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
        )

        # Check 1: The server should respond with status code 200 (OK)
        self.assertEqual(response.status_code, 200)
        # Check 2: The response JSON should say the file was uploaded successfully
        self.assertEqual(response.json(), {"filename": filename, "status": "File uploaded successfully"})
        # Check 3: The file should physically exist in the 'uploads' folder
        self.assertTrue(os.path.exists(os.path.join(UPLOAD_DIR, filename)))

if __name__ == '__main__':
    unittest.main()