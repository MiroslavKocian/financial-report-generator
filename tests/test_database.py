import unittest
import os
from database import init_db, save_upload_metadata, DB_NAME

# Define a test class inheriting from unittest.TestCase
class TestDatabase(unittest.TestCase):

    def setUp(self):
        # Run this before every test: ensure a fresh start
        if os.path.exists(DB_NAME):
            # Remove the database file if it already exists
            os.remove(DB_NAME)
        # Initialize a clean database with empty tables
        init_db()

    def tearDown(self):
        # Run this after every test: cleanup
        if os.path.exists(DB_NAME):
            # Delete the database file to keep the environment clean
            os.remove(DB_NAME)

    def test_save_upload_metadata(self):
        # Call the function with a sample filename
        file_id = save_upload_metadata("test_file.xlsx")
        
        # Verify that we got a valid integer ID back
        self.assertIsInstance(file_id, int)
        # Verify that the ID is greater than 0 (database IDs usually start at 1)
        self.assertGreater(file_id, 0)

    def test_save_upload_metadata_persists_in_db(self):
        from database import get_db_connection

        # Save metadata to generate a row
        filename = "persisted_test.xlsx"
        file_id = save_upload_metadata(filename)

        # Query the database directly to check if the record exists
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT filename FROM uploads WHERE id = ?", (file_id,))
        row = cursor.fetchone()
        conn.close()

        # Verify that a row was found and the filename matches
        self.assertIsNotNone(row)
        self.assertEqual(row["filename"], filename)

if __name__ == '__main__':
    unittest.main()