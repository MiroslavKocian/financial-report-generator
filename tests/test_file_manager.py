import unittest  # Import the standard Python testing framework
import os  # Import the os module to check for file existence
import shutil  # Import the shutil module to help us delete directories recursively
# Import the function 'setup_upload_dir' and the variable 'UPLOAD_DIR' from our file_manager.py
from file_manager import setup_upload_dir, save_uploaded_file, UPLOAD_DIR

# Define a test class that inherits from unittest.TestCase
class TestFileManager(unittest.TestCase):

    # This method runs automatically BEFORE every individual test function
    def setUp(self):
        # Check if the upload directory exists from a previous run (or manual creation)
        if os.path.exists(UPLOAD_DIR):
            # Remove the directory and all its contents to ensure a clean starting state
            shutil.rmtree(UPLOAD_DIR)

    # This method runs automatically AFTER every individual test function
    def tearDown(self):
        # Check if the upload directory was created during the test
        if os.path.exists(UPLOAD_DIR):
            # Clean it up (delete it) so we don't leave junk folders on your computer
            shutil.rmtree(UPLOAD_DIR)

    # This is the actual test function (must start with 'test_')
    def test_create_upload_dir(self):
        # Verify (Assert) that the directory does NOT exist at the very start
        self.assertFalse(os.path.exists(UPLOAD_DIR))
        
        # Call the function we are testing and store the result in a variable
        result = setup_upload_dir()
        
        # Verify (Assert) that the function returned the correct directory name string
        self.assertEqual(result, UPLOAD_DIR)
        # Verify (Assert) that the directory actually exists on the disk now
        self.assertTrue(os.path.exists(UPLOAD_DIR))

    def test_save_uploaded_file(self):
        # Create a mock upload file object with standard attributes
        from io import BytesIO
        from fastapi import UploadFile

        file_content = b"sample excel content"
        fake_file = UploadFile(
            filename="sample.xlsx",
            file=BytesIO(file_content)
        )

        # Call the file_manager function to save the uploaded file
        saved_path = save_uploaded_file(fake_file)

        # Verify that the returned file path exists on disk
        self.assertTrue(os.path.exists(saved_path))
        # Verify that the path points to the correct folder and file name
        self.assertEqual(saved_path, os.path.join(UPLOAD_DIR, "sample.xlsx"))

# This block checks if this file is being run directly by Python
if __name__ == '__main__':
    # If so, run the tests defined in the class above
    unittest.main()