import unittest  # Import the standard Python testing framework
import os  # Import os to check for file existence
import shutil  # Import shutil to clean up directories
from fastapi.testclient import TestClient  # Import TestClient to simulate web requests
from main import app  # Import our FastAPI app
from file_manager import UPLOAD_DIR  # Import the upload directory constant
from database import init_db, DB_NAME  # Import database setup functions

# Create a test client that will make requests to our app
client = TestClient(app)

class TestMainApp(unittest.TestCase):

    def setUp(self):
        # Initialize the database to ensure tables exist
        if os.path.exists(DB_NAME):
            os.remove(DB_NAME)
        init_db()
        # Clean up the upload directory to start fresh
        if os.path.exists(UPLOAD_DIR):
            shutil.rmtree(UPLOAD_DIR)

    def tearDown(self):
        # Clean up the database file
        if os.path.exists(DB_NAME):
            os.remove(DB_NAME)
        # Clean up the upload directory
        if os.path.exists(UPLOAD_DIR):
            shutil.rmtree(UPLOAD_DIR)

    def test_read_root_endpoint(self):
        # Send a GET request to the root URL "/"
        response = client.get("/")
        
        # Verify that the server responds with HTTP 200 OK
        self.assertEqual(response.status_code, 200)
        # Verify that the response content type is HTML
        self.assertIn("text/html", response.headers["content-type"])
        # Verify that the returned HTML contains our app title
        self.assertIn("Financial Report Generator", response.text)

    def test_upload_file_endpoint(self):
        # Define a fake filename and some fake content
        filename = "test_report.xlsx"
        file_content = b"fake excel content"

        # POST request with fake file: {'field': ('name', content, 'type')}
        mime_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        response = client.post(
            "/uploadfile/",
            files={"file": (filename, file_content, mime_type)},
        )

        # Check 1: The server should respond with status code 200 (OK)
        self.assertEqual(response.status_code, 200)
        
        # Get the JSON response
        json_response = response.json()
        # Check 2: Verify the response contains the filename, status, and a file_id
        self.assertEqual(json_response["filename"], filename)
        self.assertEqual(json_response["status"], "File uploaded successfully")
        self.assertIsInstance(json_response["file_id"], int)

        # Check 3: The file should physically exist in the 'uploads' folder
        self.assertTrue(os.path.exists(os.path.join(UPLOAD_DIR, filename)))

if __name__ == '__main__':
    unittest.main()