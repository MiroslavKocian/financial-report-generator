# Architecture

This document describes how the Financial Report Generator is structured: request flow, main modules, and the most important functions in each file. The [README](../README.md) stays focused on running the app; this page goes deeper for code review and interviews.

## HTTP surface

| Method | Path | Handler | Response |
|--------|------|---------|----------|
| `GET` | `/` | `read_root` | HTML upload form (`templates/index.html`) |
| `POST` | `/uploadfile/` | `create_upload_file` | JSON `UploadResponse` |
| `GET` | `/summary` | `read_summary` | JSON `SummaryResponse` |

FastAPI also exposes OpenAPI at `/docs`. Pydantic models in `schemas.py` define the JSON shapes and appear in that documentation.

On startup, the `lifespan` hook runs `init_db()` so the `uploads` metadata table exists before any request is served.

## Upload pipeline (happy path)

The upload route orchestrates other modules; it does not parse Excel or run SQL itself.

1. **`sanitize_filename`** (`file_manager.py`) — Keep only the final path segment so uploads cannot use path traversal (`../../../etc/passwd`).
2. **`save_temporary_upload`** — Stream bytes into a `.part` file under `uploads/`. The final filename is not used yet.
3. **`load_excel_dataframe`** (`excel_loader.py`) — Read `.xlsx` with pandas/openpyxl; normalize column headers to SQL-friendly names.
4. **`validate_sales_dataframe`** (`analysis.py`) — Require an `amount` column with numeric values and at least one data row.
5. **`replace_sales_dataset`** (`database.py`) — In one SQLite transaction: drop the previous sales table, clear `uploads`, insert the new upload row, create `dynamic_sales_data` with columns matching the Excel headers, insert all rows with parameterized SQL.
6. **`publish_upload`** (`file_manager.py`) — Move the temp file to `uploads/<safe_name>` and remove older files in `uploads/`.

If any step before `publish_upload` fails, the `finally` block deletes the temp file. If the database step fails, the transaction rolls back and the previous dataset remains. A bad file never overwrites good data on disk or in SQLite.

## Summary pipeline

1. **`load_sales_dataframe`** (`database.py`) — `SELECT` all user data columns from `dynamic_sales_data` into a pandas `DataFrame`.
2. **`summarize_sales`** (`analysis.py`) — Compute `row_count`, `total_amount`, `min_amount`, `max_amount` from the `amount` column (rounded to two decimal places).
3. Return a **`SummaryResponse`** instance.

Validation rules for `amount` are shared: upload uses `validate_sales_dataframe`; summary uses the same numeric checks inside `summarize_sales`.

## Module reference

### `main.py`

- **`lifespan`** — Application startup: `init_db()`.
- **`read_root`** — Serve the upload page.
- **`create_upload_file`** — Full upload pipeline; map `ValueError` to HTTP 400 and infrastructure errors to HTTP 500; log failures.
- **`read_summary`** — Load data and return the summary JSON.

### `file_manager.py`

- **`sanitize_filename`** — Reject empty or unsafe names; normalize slashes and take `basename` only.
- **`save_temporary_upload`** — `mkstemp` in `uploads/`, copy upload stream to disk.
- **`publish_upload`** — Atomic move to the final path, then keep only that file in `uploads/`.
- **`delete_uploaded_file`** — Best-effort cleanup when a later step fails.

Disk layout mirrors the safety story in the database: validate and persist to SQLite before publishing the file under its real name.

### `excel_loader.py`

- **`normalize_column_name`** — Trim, lowercase, spaces to underscores (e.g. ` Amount ` → `amount`).
- **`load_excel_dataframe`** — Load workbook; fail on invalid format, duplicate headers after normalization, or empty sheets.

Normalized names must pass `validate_sql_identifier` in `database.py` when columns become part of `CREATE TABLE`.

### `analysis.py`

- **`validate_sales_dataframe`** — Called before any database replace.
- **`summarize_sales`** — Aggregates for the summary endpoint.
- **`_numeric_amounts`** (internal) — Ensures `amount` exists and is numeric.

Pandas handles validation and aggregation; SQLite handles storage. The same summary could be expressed in SQL (`SUM`, `MIN`, `MAX`); this project keeps aggregates in pandas for clarity while learning the stack.

### `database.py`

All persistence uses the `sqlite3` standard library and hand-written SQL (no ORM).

- **`init_db`** — `CREATE TABLE IF NOT EXISTS uploads`.
- **`validate_sql_identifier`** — Regex guard before embedding table or column names in SQL.
- **`replace_sales_dataset`** — Main write path for uploads: transactional full replace of the active dataset and dynamic table schema.
- **`load_sales_dataframe`** — Main read path for summary.

Additional helpers (`ensure_dynamic_sales_table`, `insert_generic_row`, `store_dataframe_rows`, and others) support granular inserts and tests. The live upload path in `main.py` uses **`replace_sales_dataset`** only.

Parameterized placeholders (`?`) are used for values. Identifiers come only from validated column names, not from raw user strings in SQL text.

### `schemas.py`

- **`UploadResponse`** — `filename`, `file_id`, `rows_stored`, `status`.
- **`SummaryResponse`** — `row_count`, `total_amount`, `min_amount`, `max_amount`.

### `templates/index.html`

Multipart form posting to `/uploadfile/`, plus links to `/summary` and `/docs`. No business logic.

## Runtime artifacts (not in Git)

| Path | Purpose |
|------|---------|
| `sales_data.db` | SQLite database (`uploads` + `dynamic_sales_data`) |
| `uploads/` | Latest published `.xlsx` file (older copies removed on publish) |

## Design choices (short)

- **Validate before write** — Excel and `amount` checks run before `replace_sales_dataset` and before `publish_upload`.
- **Single active dataset** — Each successful upload replaces all previous rows and metadata.
- **Dynamic schema** — Excel columns become `TEXT` columns on `dynamic_sales_data`; reserved names `id` and `upload_id` are rejected.
- **Separation of concerns** — Routes, files, Excel I/O, analytics, SQL, and API contracts live in separate modules as listed in the README table.
