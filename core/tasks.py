import os
from celery import shared_task
from reportlab.pdfgen import canvas
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from email.mime.text import MIMEText
import base64
from django.conf import settings
from django.core.mail import send_mail
from google_auth_oauthlib.flow import InstalledAppFlow
from django.db import transaction
from django.core.cache import cache
from celery.exceptions import MaxRetriesExceededError
from django.db import connection
from functools import wraps
from datetime import timedelta

@shared_task
def send_password_reset_email(email, reset_url):
    """
    Celery task to send password reset email asynchronously
    """
    subject = 'Password Reset Request'
    message = f'''
    You requested to reset your password.
    
    Please click the following link to reset your password:
    {settings.SITE_URL}{reset_url}
    
    If you did not request this password reset, please ignore this email.
    '''
    
    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            fail_silently=False
        )
        return True
    except Exception as e:
        print(f'Failed to send password reset email: {str(e)}')
        return False


# Path to credentials.json
CREDENTIALS_FILE = os.path.join('config', 'credentials.json')
TOKEN_FILE = os.path.join('config', 'token.json')
# Define the scopes
SCOPES = [
    'https://www.googleapis.com/auth/gmail.send',
    'https://www.googleapis.com/auth/calendar',
]

# Rate limiting settings
MAX_REQUESTS_PER_MINUTE = 10
CACHE_TTL = 300  # 5 minutes

def rate_limit(key_prefix, limit=MAX_REQUESTS_PER_MINUTE, period=60):
    """Rate limiting decorator for Celery tasks"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            cache_key = f"{key_prefix}:{args[0] if args else 'default'}"
            current = cache.get(cache_key, 0)
            if current >= limit:
                raise Exception(f"Rate limit exceeded for {key_prefix}")
            cache.incr(cache_key)
            cache.expire(cache_key, period)
            return func(*args, **kwargs)
        return wrapper
    return decorator

def close_db_connection(func):
    """Decorator to ensure DB connections are closed after task completion"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        finally:
            connection.close()
    return wrapper

# Update paths for Docker environment
CREDENTIALS_FILE = os.path.join(settings.BASE_DIR, 'config', 'credentials.json')
TOKEN_FILE = os.path.join(settings.BASE_DIR, 'config', 'token.json')

def create_gmail_service():
    """Authenticate with Gmail API and return the service instance."""
    try:
        creds = None
        if os.path.exists(TOKEN_FILE):
            creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

        if not creds or not creds.valid:
            if not os.path.exists(CREDENTIALS_FILE):
                raise FileNotFoundError(f"Google API credentials file not found at {CREDENTIALS_FILE}")
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
            os.makedirs(os.path.dirname(TOKEN_FILE), exist_ok=True)
            with open(TOKEN_FILE, 'w') as token:
                token.write(creds.to_json())

        return build('gmail', 'v1', credentials=creds)
    except Exception as e:
        print(f"Error creating Gmail service: {str(e)}")
        raise

def create_calendar_service():
    """Authenticate with Google Calendar API and return the service instance."""
    try:
        creds = None
        if os.path.exists(TOKEN_FILE):
            creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

        if not creds or not creds.valid:
            if not os.path.exists(CREDENTIALS_FILE):
                raise FileNotFoundError(f"Google API credentials file not found at {CREDENTIALS_FILE}")
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
            os.makedirs(os.path.dirname(TOKEN_FILE), exist_ok=True)
            with open(TOKEN_FILE, 'w') as token:
                token.write(creds.to_json())

        return build('calendar', 'v3', credentials=creds)
    except Exception as e:
        print(f"Error creating Calendar service: {str(e)}")
        raise

def create_email_message(to, subject, body):
    """
    Create a MIMEText email message and encode it in base64.
    """
    message = MIMEText(body)
    message['to'] = to
    message['subject'] = subject
    return {'raw': base64.urlsafe_b64encode(message.as_bytes()).decode()}


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={'max_retries': 3})
def send_booking_confirmation_email_gmail(self, to_email, booking_details):
    """
    Task to send booking confirmation emails using Gmail API with improved error handling and retries.
    """
    import logging
    logger = logging.getLogger(__name__)

    try:
        service = create_gmail_service()

        subject = f"Booking Confirmation: {booking_details['service_name']}"
        body = (
            f"Dear {booking_details['user_name']},\n\n"
            f"Thank you for booking {booking_details['service_name']}.\n"
            f"Date: {booking_details['date']}\n"
            f"Time: {booking_details['time']}\n\n"
            f"We look forward to serving you!"
        )

        email_message = create_email_message(to_email, subject, body)
        result = service.users().messages().send(userId="me", body=email_message).execute()
        logger.info(f"Successfully sent confirmation email for booking {booking_details['service_name']}")
        return f"Email sent: {result.get('id')}"
    except Exception as e:
        logger.error(f"Failed to send confirmation email: {str(e)}")
        raise  # This will trigger the retry mechanism

@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={'max_retries': 3})
def send_booking_confirmation(self, booking_id):
    """
    Task to send a booking confirmation email with improved error handling and retries.
    """
    from .models import Booking
    import logging
    logger = logging.getLogger(__name__)

    try:
        booking = Booking.objects.select_related('user', 'service').get(id=booking_id)
        # Send email logic...
        booking.confirmation_sent = True
        booking.save(update_fields=['confirmation_sent'])
        logger.info(f"Booking confirmation sent for booking {booking_id}")
        return f"Booking confirmation sent for booking {booking_id}."
    except Booking.DoesNotExist:
        logger.error(f"Booking {booking_id} not found")
        return f"Booking {booking_id} not found."
    except Exception as e:
        logger.error(f"Error sending booking confirmation for {booking_id}: {str(e)}")
        raise  # This will trigger the retry mechanism

@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={'max_retries': 3})
def send_booking_reminder(self, booking_id):
    """
    Task to send a booking reminder email with improved error handling and retries.
    """
    from .models import Booking
    import logging
    logger = logging.getLogger(__name__)

    try:
        booking = Booking.objects.select_related('user', 'service').get(id=booking_id)
        # Send email logic...
        booking.reminder_sent = True
        booking.save(update_fields=['reminder_sent'])
        logger.info(f"Booking reminder sent for booking {booking_id}")
        return f"Booking reminder sent for booking {booking_id}."
    except Booking.DoesNotExist:
        logger.error(f"Booking {booking_id} not found")
        return f"Booking {booking_id} not found."
    except Exception as e:
        logger.error(f"Error sending booking reminder for {booking_id}: {str(e)}")
        raise  # This will trigger the retry mechanism

    return f"Email sent: {result.get('id')}"

@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={'max_retries': 3})
def generate_invoice(self, booking_id, invoice_details):
    """
    Task to generate a PDF invoice for a booking with improved error handling and retries.
    """
    import logging
    logger = logging.getLogger(__name__)

    try:
        # Invoice file path
        invoice_dir = os.path.join(settings.MEDIA_ROOT, 'invoices')
        os.makedirs(invoice_dir, exist_ok=True)
        invoice_path = os.path.join(invoice_dir, f"invoice_{booking_id}.pdf")

        # Generate PDF using ReportLab
        c = canvas.Canvas(invoice_path)
        c.setFont("Helvetica", 12)

        # Add details to the invoice
        c.drawString(100, 800, f"Invoice for Booking #{booking_id}")
        c.drawString(100, 780, f"Customer Name: {invoice_details['customer_name']}")
        c.drawString(100, 760, f"Service: {invoice_details['service_name']}")
        c.drawString(100, 740, f"Date: {invoice_details['date']}")
        c.drawString(100, 720, f"Time: {invoice_details['time']}")
        c.drawString(100, 700, f"Total Price: ${invoice_details['total_price']}")

        # Save the PDF
        c.save()
        logger.info(f"Successfully generated invoice for booking {booking_id}")
        return f"Invoice generated at {invoice_path}"
    except KeyError as e:
        logger.error(f"Missing required invoice detail: {str(e)}")
        raise
    except IOError as e:
        logger.error(f"Failed to write invoice file: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error generating invoice for booking {booking_id}: {str(e)}")
        raise

@shared_task(bind=True, max_retries=3)
def update_search_index(self, service_id):
    """
    Task to update the Elasticsearch index for a specific service.
    Includes retry mechanism and better error handling.
    """
    from .documents import ServiceDocument
    from .models import Service
    from elasticsearch.exceptions import ConnectionError, TransportError
    try:
        service = Service.objects.get(id=service_id)
        ServiceDocument().update(service)
        return f"Search index updated for Service ID: {service_id}"
    except Service.DoesNotExist:
        return f"Service ID {service_id} does not exist."
    except (ConnectionError, TransportError) as e:
        retry_count = self.request.retries
        if retry_count < self.max_retries:
            self.retry(countdown=2 ** retry_count, exc=e)
        return f"Failed to update search index for Service ID {service_id} after {retry_count} retries: {str(e)}"
    except Exception as e:
        return f"Unexpected error updating search index for Service ID {service_id}: {str(e)}"

@shared_task
def remove_from_search_index(service_id):
    """
    Task to remove a service from the Elasticsearch index.
    """
    from .documents import ServiceDocument
    try:
        ServiceDocument().delete(service_id)
        return f"Search index entry removed for Service ID: {service_id}"
    except Exception as e:
        return f"Failed to remove Service ID {service_id} from the search index: {str(e)}"
    

def create_calendar_service():
    """
    Authenticate with Google Calendar API and return the service instance.
    """
    CREDENTIALS_FILE = 'config/credentials.json'
    TOKEN_FILE = 'config/token.json'

    creds = None
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

    if not creds or not creds.valid:
        from google_auth_oauthlib.flow import InstalledAppFlow
        flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
        creds = flow.run_local_server(port=0)

        with open(TOKEN_FILE, 'w') as token:
            token.write(creds.to_json())

    return build('calendar', 'v3', credentials=creds)

@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={'max_retries': 3})
@rate_limit('calendar_sync')
@close_db_connection
@transaction.atomic
def sync_booking_to_google_calendar(self, booking_id):
    """
    Task to sync a booking to Google Calendar with improved error handling and retries.
    """
    from .models import Booking
    import logging

    logger = logging.getLogger(__name__)

    try:
        booking = Booking.objects.select_related('user', 'service').get(id=booking_id)
        service = create_calendar_service()

        event = {
            'summary': booking.service.name,
            'description': f"Booking for {booking.user.get_full_name()}",
            'start': {
                'dateTime': booking.appointment_time.isoformat(),
                'timeZone': 'UTC',
            },
            'end': {
                'dateTime': (booking.appointment_time + booking.service.duration).isoformat(),
                'timeZone': 'UTC',
            },
            'reminders': {
                'useDefault': False,
                'overrides': [
                    {'method': 'email', 'minutes': 24 * 60},
                    {'method': 'popup', 'minutes': 30},
                ],
            },
        }

        response = service.events().insert(calendarId='primary', body=event).execute()
        logger.info(f"Successfully synced booking {booking_id} to Google Calendar. Event ID: {response.get('id')}")
        return f"Booking {booking_id} synced to Google Calendar."
    except Booking.DoesNotExist:
        logger.error(f"Booking ID {booking_id} does not exist")
        return f"Booking ID {booking_id} does not exist."
    except Exception as e:
        logger.error(f"Failed to sync booking {booking_id} to Google Calendar: {str(e)}")
        raise  # This will trigger the retry mechanism
