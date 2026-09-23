import sqlite3
from typing import Any

# Define the global name for our database file
DB_NAME: str = "sales_data.db"


def get_db_connection() -> sqlite3.Connection:
    # Create a connection to the SQLite database file
    conn: sqlite3.Connection = sqlite3.connect(DB_NAME)
    # Configure rows to behave like dictionaries for easier access
    conn.row_factory = sqlite3.Row
    # Return the active connection object
    return conn


def init_db() -> None:
    """Initialize the database tables."""
    # Get a fresh connection to the database
    conn: sqlite3.Connection = get_db_connection()
    with conn:
        # Execute the SQL command to create the 'uploads' table if it doesn't exist yet
        conn.execute("""
            CREATE TABLE IF NOT EXISTS uploads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT NOT NULL,
                upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
    # Close the connection when done
    conn.close()


def save_upload_metadata(filename: str) -> int:
    # Establish a connection to the SQLite database
    conn: sqlite3.Connection = get_db_connection()
    with conn:
        # Create a cursor object to execute SQL commands
        cursor: sqlite3.Cursor = conn.cursor()
        # Prepare the SQL INSERT statement with a placeholder for the filename
        sql: str = "INSERT INTO uploads (filename) VALUES (?)"
        # Execute the SQL statement, passing the filename as a tuple
        cursor.execute(sql, (filename,))
        # Retrieve the unique ID generated for this new row
        new_id: int | None = cursor.lastrowid
    # Close the connection to free up database resources
    conn.close()
    # Return the ID of the newly created record
    return new_id if new_id is not None else 0


def insert_generic_row(table_name: str, row_data: dict[str, Any]) -> int:
    """
    Inserts a single generic row into any SQLite table
    using a fully dynamic, manual raw SQL INSERT statement.
    Parameters:
        table_name (str): The name of the database table.
        row_data (dict): Dictionary of column names and their values.
    Returns:
        int: The primary key ID of the newly inserted row.
    """
    # Establish a connection to the SQLite database
    conn: sqlite3.Connection = get_db_connection()

    # Create a cursor object to execute raw SQL commands
    cursor: sqlite3.Cursor = conn.cursor()

    # Extract column names dynamically from dictionary keys
    columns: str = ", ".join(row_data.keys())

    # Generate question mark placeholders for parameterized query
    placeholders: str = ", ".join(["?" for _ in row_data])

    # Construct the raw SQL insert query dynamically
    sql: str = f"""
        INSERT INTO {table_name} 
        ({columns})
        VALUES ({placeholders})
    """

    # Extract values from the dictionary into a tuple
    values: tuple = tuple(row_data.values())

    # Execute the raw SQL query with parameters for security
    cursor.execute(sql, values)

    # Commit the transaction to permanently save the record
    conn.commit()

    # Retrieve the unique primary key ID generated for this row
    new_row_id: int | None = cursor.lastrowid

    # Close the database connection to release resources
    conn.close()

    # Return the newly created row ID
    return new_row_id if new_row_id is not None else 0
