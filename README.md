# Financial Report Generator

[![Tests](https://github.com/MiroslavKocian/financial-report-generator/actions/workflows/test.yml/badge.svg)](https://github.com/MiroslavKocian/financial-report-generator/actions/workflows/test.yml)

A small web app: you upload an Excel file with sales data, the app saves every row into a SQLite database, and you can view a summary, grouped JSON reports, and an Excel summary export with decimal-safe `amount` totals.

Built with Python 3.11, FastAPI, pandas, and SQLite. All database queries are plain SQL written by hand (no Object–relational mapping).

## Requirements

- [Python 3.11](https://www.python.org/downloads/)
- [Git](https://git-scm.com/downloads)
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (only if you want to run the app in Docker)

## Run locally

### 1. Download the project

```sh
git clone https://github.com/MiroslavKocian/financial-report-generator.git
cd financial-report-generator
```

This creates a folder named `financial-report-generator`. Run every following command inside this folder.

### 2. Install dependencies

Windows (PowerShell):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

macOS / Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

`requirements.txt` is what the app needs to run. `requirements-dev.txt` adds pytest, coverage, and Ruff. Docker installs only `requirements.txt`.

If PowerShell refuses to run `Activate.ps1`, run this once and try again:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

### 3. Start the app

```sh
python main.py
```

Keep this terminal window open. The app runs as long as it is open. To stop it, press **Ctrl+C**.

### 4. Use the app

1. Open [http://127.0.0.1:8000](http://127.0.0.1:8000) in your browser.

   ![Upload page at http://127.0.0.1:8000](docs/images/04-upload-page.jpg)

2. Under **Select Excel file**, click the file button and pick the sample file `sales_example.xlsx`. It is in the `examples` folder inside the project folder you downloaded in step 1.
3. Click **Upload and Store**. The browser shows a short confirmation, for example:

   ```json
   {"filename": "sales_example.xlsx", "file_id": 1, "rows_stored": 4, "status": "File uploaded and raw data stored via raw SQL"}
   ```

   ![Upload confirmation JSON](docs/images/04-upload-response.jpg)

4. Open [http://127.0.0.1:8000/summary](http://127.0.0.1:8000/summary). For the sample file you will see money as two-decimal strings (not binary floats):

   ```json
   {"row_count": 4, "total_amount": "41.00", "min_amount": "1.00", "max_amount": "25.00"}
   ```

   ![Summary JSON for the sample file](docs/images/04-summary.jpg)

5. Grouped report (sample file, after upload):
   - By region: [http://127.0.0.1:8000/report/grouped?group_by=region](http://127.0.0.1:8000/report/grouped?group_by=region) — North `11.00`, South `30.00`.

     ![Grouped report by region](docs/images/04-grouped-region.jpg)

   - By product: [http://127.0.0.1:8000/report/grouped?group_by=product](http://127.0.0.1:8000/report/grouped?group_by=product) — A `35.00`, B `6.00`.

     ![Grouped report by product](docs/images/04-grouped-product.jpg)
6. Download the summary as Excel: [http://127.0.0.1:8000/report/export.xlsx](http://127.0.0.1:8000/report/export.xlsx). The workbook has one **Summary** sheet (same numbers as `/summary`).

Every new upload replaces the previous data. Uploading a file with the same name again is allowed.

FastAPI also generates an interactive API page at [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs), where you can see and try every endpoint.

![FastAPI interactive API docs at /docs](docs/images/04-api-docs.jpg)

## Run with Docker

Start Docker Desktop, then in the project folder run:

```sh
docker compose up --build
```

When the log shows `Application startup complete`, follow the steps in [Use the app](#4-use-the-app). The log says `http://0.0.0.0:8000`; that is the address inside the container. In your browser, use [http://127.0.0.1:8000](http://127.0.0.1:8000).

To stop, press **Ctrl+C**, then run:

```sh
docker compose down
```

The database lives inside the container, so after `docker compose down` the data is gone. Upload the file again after the next start.

## Excel file rules

- The file must be `.xlsx`.
- It must have a column named `amount`. Capital letters and extra spaces in the header are fine (`Amount`, ` AMOUNT `).
- Every `amount` cell must be a number, and the file must have at least one data row. Amounts are stored and returned as decimal text with two places (`10.00`), so totals do not use binary floats.
- A grouped report needs `region` or `product`, unless you pass another stored column as `group_by`. The sample file has both; the default group is `region`.
- Other columns (for example `region`, `product`) are saved too.
- Column names may contain only letters, digits, and underscores (spaces become underscores). `id` and `upload_id` are not allowed as column names.

If a file breaks a rule, the app shows an error message and keeps the previously uploaded data.

## How it works

```mermaid
flowchart TD
    browser[Browser upload form] --> save[Save file as temporary copy]
    save --> read[Read Excel with pandas]
    read --> check[Check the amount column]
    check --> db[Replace data in SQLite in one transaction]
    db --> publish[Keep the file under its real name]
    summary[Summary and grouped report] --> query[Read rows from SQLite]
    query --> totals[Compute totals with Decimal]
    totals --> export[Excel workbook with Summary sheet]
```

1. The uploaded file is first saved as a temporary copy.
2. pandas reads it and the `amount` column is checked.
3. Only if everything is valid, the old data is replaced with the new rows in a single database transaction. If anything fails, the old data stays untouched.
4. Summary and grouped report read the rows back from SQLite and compute totals with `Decimal`. Excel export writes those totals to a workbook.

| File | Responsibility |
|------|----------------|
| `main.py` | Starts the app (`python main.py`) |
| `financial_report_generator/main.py` | Web routes and the upload flow |
| `financial_report_generator/file_manager.py` | Safe file names, temporary file, final file |
| `financial_report_generator/excel_loader.py` | Reading Excel and cleaning up column names |
| `financial_report_generator/analysis.py` | Checking `amount`, summary, and grouped totals |
| `financial_report_generator/money.py` | Decimal parse and two-decimal text |
| `financial_report_generator/database.py` | All SQL queries |
| `financial_report_generator/export.py` | Excel workbook for the report |
| `financial_report_generator/schemas.py` | Shape of the JSON responses |
| `templates/index.html` | Upload page |

For a longer walkthrough (request flow, key functions per module, and design notes), see [docs/architecture.md](docs/architecture.md).

Files created while the app runs (not stored in Git): `sales_data.db` (the database) and the `uploads` folder (the latest uploaded Excel file). Both appear in the project folder.

## Tests

With the virtual environment active:

```sh
pip install -r requirements-dev.txt
pytest
ruff check .
ruff format --check .
```

`pytest` runs all tests and requires 100% code coverage. `ruff` checks code style.

GitHub runs the same three commands automatically after every push (file `.github/workflows/test.yml`). The green **Tests** badge at the top of this page shows the latest result.

## Project structure

```text
financial-report-generator/
├── main.py
├── financial_report_generator/
│   ├── main.py
│   ├── database.py
│   ├── file_manager.py
│   ├── excel_loader.py
│   ├── analysis.py
│   ├── money.py
│   ├── export.py
│   └── schemas.py
├── templates/
│   └── index.html
├── examples/
│   └── sales_example.xlsx
├── docs/
│   ├── architecture.md
│   └── images/
├── tests/
├── .github/workflows/test.yml
├── Dockerfile
├── compose.yaml
├── requirements.txt
├── requirements-dev.txt
├── pyproject.toml
└── AGENTS.md
```

`pyproject.toml` holds the pytest and Ruff settings. `AGENTS.md` holds the coding rules followed while building this project.

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Browser says the page cannot be reached | The app is not running. Start it with `python main.py` and keep the terminal open. |
| `Address already in use` / port 8000 busy | Another app (or a second copy of this one) is using port 8000. Close it and start again. |
| Summary shows `No sales data is stored.` | Nothing has been uploaded yet. Upload a file first. |
| Upload shows an error | The file breaks one of the [Excel file rules](#excel-file-rules). The message says which one. |

## License

No license is granted. The code is published to be viewed as a portfolio project.
