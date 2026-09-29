"""Run the web app from the project root: ``python main.py``."""

from financial_report_generator.main import app

__all__ = ["app"]

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "financial_report_generator.main:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
    )
