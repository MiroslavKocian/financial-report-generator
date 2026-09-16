import sqlite3

# Define the global name for our database file
DB_NAME = "sales_data.db"

def get_db_connection():
    # Create a connection to the SQLite database file
    conn = sqlite3.connect(DB_NAME)
    # Configure rows to behave like dictionaries for easier access
    conn.row_factory = sqlite3.Row
    # Return the active connection object
    return conn

def init_db():
    """Initialize the database tables."""
    # Get a fresh connection to the database
    conn = get_db_connection()
    with conn:
        # Execute the SQL command to create the 'uploads' table if it doesn't exist yet
        conn.execute('''
            CREATE TABLE IF NOT EXISTS uploads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT NOT NULL,
                upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
    # Close the connection when done
    conn.close()

def save_upload_metadata(filename: str) -> int:
    # Establish a connection to the SQLite database
    conn = get_db_connection()
    with conn:
        # Create a cursor object to execute SQL commands
        cursor = conn.cursor()
        # Prepare the SQL INSERT statement with a placeholder for the filename
        sql = "INSERT INTO uploads (filename) VALUES (?)"
        # Execute the SQL statement, passing the filename as a tuple
        cursor.execute(sql, (filename,))
        # Retrieve the unique ID generated for this new row
        new_id = cursor.lastrowid
    # Close the connection to free up database resources
    conn.close()
    # Return the ID of the newly created record
    return new_id