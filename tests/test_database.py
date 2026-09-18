import unittest
import os
from database import (
    init_db, 
    save_upload_metadata, 
    insert_generic_row, 
    get_db_connection, 
    DB_NAME
)

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

    def test_insert_generic_row(self):
        """
        Test inserting a generic row into a dynamically created table 
        using raw SQL queries, ensuring correct ID return and data persistence.
        """
        # Step 1: Create a temporary test table using raw SQL
        conn = get_db_connection()
        with conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS test_products (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    product_name TEXT NOT NULL,
                    price REAL NOT NULL,
                    in_stock INTEGER NOT NULL
                )
            """)
        conn.close()

        # Step 2: Prepare sample row data dictionary
        sample_data = {
            "product_name": "Laptop Pro",
            "price": 1299.99,
            "in_stock": 15
        }

        # Step 3: Call the function we are testing
        row_id = insert_generic_row("test_products", sample_data)

        # Step 4: Verify that a valid positive integer ID is returned
        self.assertIsInstance(row_id, int)
        self.assertGreater(row_id, 0)

        # Step 5: Verify via raw SQL that the data was actually stored correctly
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT product_name, price, in_stock FROM test_products WHERE id = ?", 
            (row_id,)
        )
        row = cursor.fetchone()
        conn.close()

        # Step 6: Assert that fetched values match what was inserted
        self.assertIsNotNone(row)
        self.assertEqual(row["product_name"], "Laptop Pro")
        self.assertEqual(row["price"], 1299.99)
        self.assertEqual(row["in_stock"], 15)

if __name__ == '__main__':
    unittest.main()