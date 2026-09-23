import unittest  # Import standard Python testing framework
import os  # Import os to check for file existence
import shutil  # Import shutil to clean up directories
import io  # Import io for in-memory byte streams
from typing import Optional
import pandas as pd  # Import pandas to create a valid test Excel file
from fastapi.testclient import TestClient  # Import TestClient to simulate web requests
from main import app  # Import our FastAPI app
from file_manager import UPLOAD_DIR  # Import upload directory constant
from database import init_db, DB_NAME  # Import database setup functions

# Create a test client that will make requests to our app
client: TestClient = TestClient(app)

class TestMainApp(unittest.TestCase):

    def setUp(self) -> None:
        # Initialize the database to ensure tables exist
        if os.path.exists(DB_NAME):
            os.remove(DB_NAME)
        init_db()
        # Clean up the upload directory to start fresh
        if os.path.exists(UPLOAD_DIR):
            shutil.rmtree(UPLOAD_DIR)

    def tearDown(self) -> None:
        # Clean up the database file
        if os.path.exists(DB_NAME):
            os.remove(DB_NAME)
        # Clean up the upload directory
        if os.path.exists(UPLOAD_DIR):
            shutil.rmtree(UPLOAD_DIR)

    def test_upload_file_endpoint(self) -> None:
        # Create a small valid Excel file in memory using pandas
        df_test: pd.DataFrame = pd.DataFrame({
            "Region": ["North", "South"],
            "Amount": [100.50, 250.75]
        })
        excel_buffer: io.BytesIO = io.BytesIO()
        df_test.to_excel(excel_buffer, index=False, engine="openpyxl")
        excel_bytes: bytes = excel_buffer.getvalue()

        filename: str = "test_report.xlsx"

        # Send a POST request to "/uploadfile/" with the valid Excel bytes
        response = client.post(
            "/uploadfile/",
            files={"file": (filename, excel_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
        )

        # Check 1: The server should respond with status code 200 (OK)
        self.assertEqual(response.status_code, 200)
        
        # Get the JSON response
        json_response: dict = response.json()
        
        # Check 2: Verify response contains filename, status, file_id, and rows_stored
        self.assertEqual(json_response["filename"], filename)
        self.assertEqual(json_response["status"], "File uploaded and raw data stored via raw SQL")
        self.assertIsInstance(json_response["file_id"], int)
        self.assertEqual(json_response["rows_stored"], 2)

        # Check 3: The file should physically exist in the 'uploads' folder
        self.assertTrue(os.path.exists(os.path.join(UPLOAD_DIR, filename)))

if __name__ == '__main__':
    unittest.main()