# Use a slim Python image to reduce size
FROM python:3.10-slim-bullseye

# Prevent Python from writing pyc files, and do unbuffered logging
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install system packages for PostgreSQL (psycopg2), geopy (libgeos), etc.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    libmagic1 \
    libgeos-dev \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Create a directory for your application
WORKDIR /app

# Copy requirements first (to leverage Docker's caching)
COPY requirements.txt /app/
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Copy the whole project into the container
COPY . /app/

# Expose port 8000 (Gunicorn or Django default)
EXPOSE 8000

# Default command: run Gunicorn with our config file in production mode
CMD ["gunicorn", "booking_platform.wsgi:application", "-c", "gunicorn.conf.py"]
