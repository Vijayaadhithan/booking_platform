# Dockerfile
FROM python:3.10-slim-bullseye

# Prevent Python from writing pyc files, and do unbuffered logging
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# System packages for PostgreSQL (psycopg2), geopy (e.g., libgeos), etc.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    libmagic1 \
    libgeos-dev \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Create a directory for your application
WORKDIR /app

# Copy requirements and install them
COPY requirements.txt /app/
RUN pip install --no-cache-dir --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# Copy the whole project into the container
COPY . /app/

# Expose port 8000 (Django default or Gunicorn later)
EXPOSE 8000

# Use Gunicorn with our configuration file for production
CMD ["gunicorn", "booking_platform.wsgi:application", "-c", "gunicorn.conf.py"]

