  # Booking Platform Backend

A Django/DRF-based application providing a booking and scheduling platform, featuring:

- **Django REST Framework** for API endpoints  
- **Celery** for async task processing (e.g., sending emails, generating invoices)  
- **Redis** as a broker for Celery tasks and a cache backend  
- **PostgreSQL** for the main database  
- **Elasticsearch** integration for full-text search on services  
- **Google API** (Gmail/Calendar) integration for email sending and calendar sync  
- **Geopy** for address geocoding and distance calculations  

---

## Table of Contents

1. [Requirements](#requirements)  
2. [Installation (Local)](#installation-local)  
3. [Running Locally (Without Docker)](#running-locally-without-docker)  
4. [Running With Docker](#running-with-docker)  
5. [Migrations & Superuser](#migrations--superuser)  
6. [Environment Variables](#environment-variables)  
7. [Google API Credentials](#google-api-credentials)  
8. [Usage](#usage)  
9. [License](#license)  

---

## Requirements

- **Python 3.9+** (3.10 recommended)  
- **PostgreSQL** (if running locally without Docker)  
- **Redis** (if running locally without Docker)  
- **Elasticsearch** (if running locally without Docker)  
- Optionally, **virtualenv** or **conda** for Python environment isolation.

For Docker-based setup:
- **Docker** and **Docker Compose** installed.

---

## Installation (Local)

1. **Clone** this repository:
   git clone https://github.com/Vijayaadhithan/booking_platform.git
   cd booking_platform
2. **Create a virtual environment** (optional but recommended):
   python -m venv venv
   source venv/bin/activate   # on Linux/Mac
   # or on Windows: venv\Scripts\activate
3. **Install Python dependencies:**
   pip install --upgrade pip
   pip install -r requirements.txt

# Running Locally (Without Docker)

**1. Set up environment variables** (see [Environment Variables](#environment-variables)) or create a `.env` file in the project root.

**2. Ensure PostgreSQL, Redis, and Elasticsearch** are running locally, and update `settings.py` / your `.env` with proper host/port credentials. For example:
- PostgreSQL on `localhost:5432`
- Redis on `localhost:6379`
- Elasticsearch on `localhost:9200`

**3. Apply migrations** (see [Migrations & Superuser](#migrations--superuser)).

**4. Start Django server:**
  python manage.py runserver
  The API is available at http://127.0.0.1:8000/.

**5. Start Celery worker in a separate terminal:
  celery -A booking_platform worker --loglevel=info    (or)
  celery -A booking_platform beat --loglevel=info

## Running With Docker
A Dockerfile and docker-compose.yml are included to run the full stack:
  - web (Django/DRF)
  - celery (Celery worker)
  - celery-beat (optional)
  - db (PostgreSQL)
  - redis (Redis broker/cache)
  - elasticsearch (Elasticsearch)

1. **Build & Launch**
   # From the project root (same folder as docker-compose.yml)
   docker-compose build
   docker-compose up
   To run in the background (detached):
   docker-compose up -d
2. **Migrate & Create Superuser**
   Once containers are running:
   docker-compose exec web python manage.py migrate
   docker-compose exec web python manage.py createsuperuser
3. **Access the App**
   - Django/DRF: http://localhost:8000
   - PostgreSQL: localhost:5432
   - Redis: localhost:6379
   - Elasticsearch: http://localhost:9200

## Migrations & Superuser
Regardless of local or Docker usage:
python manage.py migrate
python manage.py createsuperuser
Then log into Django Admin at:
http://127.0.0.1:8000/admin/

## Environment Variables

Some important variables you may need in your .env or environment:
  - SECRET_KEY – Django secret key
  - DEBUG – True or False
  - DB_NAME – PostgreSQL database name
  - DB_USER – PostgreSQL username
  - DB_PASSWORD – PostgreSQL password
  - DB_HOST – Usually localhost (or db if using Docker)
  - DB_PORT – Usually 5432
  - CELERY_BROKER_URL – Typically redis://localhost:6379/0 (or redis://redis:6379/0 in Docker)
  - CELERY_RESULT_BACKEND – Same as broker or a separate Redis DB


## Google API Credentials
If you’re using Gmail/Calendar:
  - Files credentials.json and token.json are in config/.
  - By default, the code references them via paths like config/credentials.json.
  - If running with Docker, they’re copied into the container (unless you mount them externally).
  - For production, consider a more secure approach than committing credentials to source control (e.g., environment variables, secret manager, or volume mounting).

## Usage
Common endpoints (examples):
  - API Root: /api/
  - Admin: /admin/
  - API Docs (if using drf-spectacular’s Swagger): /api/docs/

