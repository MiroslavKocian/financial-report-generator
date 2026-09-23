# 1. Base image with lightweight Python 3.11
FROM python:3.11-slim

# 2. Set working directory in container
WORKDIR /app

# 3. Prevent writing .pyc files and enable unbuffered logging
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# 4. Install system dependencies for Pandas and OpenPyXL
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# 5. Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 6. Copy application source code
COPY . .

# 7. Create directory for uploaded files
RUN mkdir -p uploads

# 8. Expose FastAPI default port
EXPOSE 8000

# 9. Run FastAPI application via Uvicorn
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]