import os
import base64
import logging

from celery import shared_task
from celery.exceptions import MaxRetriesExceededError
from celery.utils.log import get_task_logger
from reportlab.pdfgen import canvas

from django.conf import settings
from django.core.mail import send_mail
from django.core.cache import cache
from django.db import connection, transaction

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from email.mime.text import MIMEText

from functools import wraps
from datetime import timedelta

#from .models import Booking

logger = get_task_logger(__name__)


# ------------------------------------------------------------------------
# Rate-limiting decorator (optional)
# ------------------------------------------------------------------------
MAX_REQUESTS_PER_MINUTE = 10
CACHE_TTL = 60  # 1 minute

def rate_limit(key_prefix, limit=MAX_REQUESTS_PER_MINUTE, period=60):
    """
    Simple rate-limiting decorator for Celery tasks.
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            cache_key = f"{key_prefix}:{args[0] if args else 'default'}"
            current_count = cache.get(cache_key, 0)
            if current_count >= limit:
                raise Exception(f"Rate limit exceeded for {key_prefix}")
            cache.incr(cache_key)
            cache.expire(cache_key, period)
            return func(*args, **kwargs)
        return wrapper
    return decorator


# ------------------------------------------------------------------------
# Database Connection Closer
# ------------------------------------------------------------------------
def close_db_connection(func):
    """
    Decorator to ensure DB connections are closed after task completion.
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        finally:
            connection.close()
    return wrapper


# ------------------------------------------------------------------------
# Google API Scopes & File Paths
# ------------------------------------------------------------------------
SCOPES = [
    'https://www.googleapis.com/auth/gmail.send',
    'https://www.googleapis.com/auth/calendar',
]

# We assume credentials/token are in config/ as set in settings.py, or fallback
CREDENTIALS_FILE = getattr(settings, 'GOOGLE_API_CREDENTIALS_FILE', os.path.join('config', 'credentials.json'))
TOKEN_FILE = getattr(settings, 'GOOGLE_API_TOKEN_FILE', os.path.join('config', 'token.json'))


# ------------------------------------------------------------------------
# Helper: Create Gmail Service
# ------------------------------------------------------------------------
def create_gmail_service():
    """
    Authenticate with Gmail API and return a service instance.
    """
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


# ------------------------------------------------------------------------
# Helper: Create Calendar Service
# ------------------------------------------------------------------------
def create_calendar_service():
    """
    Authenticate with Google Calendar API and return the service instance.
    """
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


# ------------------------------------------------------------------------
# Helper: Create Email Message for Gmail
# ------------------------------------------------------------------------
def create_email_message(to, subject, body):
    """
    Create a MIMEText email message, base64-encoded for Gmail API.
    """
    message = MIMEText(body)
    message['to'] = to
    message['subject'] = subject
    return {'raw': base64.urlsafe_b64encode(message.as_bytes()).decode()}


# ------------------------------------------------------------------------
# Celery Tasks
# ------------------------------------------------------------------------


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={'max_retries': 3})
def send_password_reset_email(self, email, reset_url):
    """
    Celery task to send password reset email asynchronously using Django's send_mail.
    """
    subject = 'Password Reset Request'
    message = (
        f"You requested to reset your password.\n\n"
        f"Please click the following link to reset your password:\n"
        f"{settings.SITE_URL}{reset_url}\n\n"
        f"If you did not request this password reset, please ignore this email."
    )
    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            fail_silently=False
        )
        logger.info(f'Password reset email sent to {email}')
        return True
    except Exception as e:
        logger.error(f'Failed to send password reset email to {email}: {str(e)}')
        raise


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={'max_retries': 3})
def send_booking_confirmation_email_gmail(self, to_email, booking_details):
    """
    Sends a booking confirmation email via Gmail API.
    """
    logger.info(f"Preparing to send booking confirmation email to {to_email}")
    try:
        service = create_gmail_service()
        subject = f"Booking Confirmation: {booking_details.get('service_name', 'Service')}"
        body = (
            f"Dear {booking_details.get('user_name', 'Customer')},\n\n"
            f"Thank you for booking {booking_details.get('service_name', 'Service')}.\n"
            f"Date: {booking_details.get('date', '')}\n"
            f"Time: {booking_details.get('time', '')}\n\n"
            "We look forward to serving you!"
        )
        email_message = create_email_message(to_email, subject, body)
        result = service.users().messages().send(userId="me", body=email_message).execute()
        logger.info(f"Booking confirmation email sent to {to_email}: {result.get('id')}")
        return f"Email sent: {result.get('id')}"
    except Exception as e:
        logger.error(f"Failed to send confirmation email to {to_email}: {str(e)}")
        raise


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={'max_retries': 3})
def send_booking_confirmation(self, booking_id):
    """
    Sends a booking confirmation email (placeholder for any other emailing logic).
    Could also call 'send_booking_confirmation_email_gmail' internally.
    """
    logger.info(f"send_booking_confirmation triggered for Booking ID {booking_id}")
    try:
        booking = Booking.objects.select_related('user', 'service').get(id=booking_id)
        # You might do something like send an email via send_mail
        # For demonstration, we just set a flag
        booking.confirmation_sent = True
        booking.save(update_fields=['confirmation_sent'])
        logger.info(f"Booking confirmation logic complete for {booking_id}")
        return f"Booking confirmation completed for {booking_id}."
    except Booking.DoesNotExist:
        logger.error(f"Booking {booking_id} not found")
        return f"Booking {booking_id} not found."
    except Exception as e:
        logger.error(f"Error in send_booking_confirmation for {booking_id}: {str(e)}")
        raise


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={'max_retries': 3})
def send_booking_reminder(self, booking_id):
    """
    Sends a booking reminder email (placeholder).
    """
    logger.info(f"send_booking_reminder triggered for Booking ID {booking_id}")
    try:
        booking = Booking.objects.select_related('user', 'service').get(id=booking_id)
        # Insert actual email sending logic
        booking.reminder_sent = True
        booking.save(update_fields=['reminder_sent'])
        logger.info(f"Booking reminder sent for {booking_id}")
        return f"Booking reminder sent for {booking_id}."
    except Booking.DoesNotExist:
        logger.error(f"Booking {booking_id} not found")
        return f"Booking {booking_id} not found."
    except Exception as e:
        logger.error(f"Error in send_booking_reminder for {booking_id}: {str(e)}")
        raise


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={'max_retries': 3})
def generate_invoice(self, booking_id, invoice_details):
    """
    Generates a PDF invoice for a booking using ReportLab.
    """
    logger.info(f"generate_invoice triggered for Booking ID {booking_id}")
    try:
        invoice_dir = os.path.join(settings.MEDIA_ROOT, 'invoices')
        os.makedirs(invoice_dir, exist_ok=True)
        invoice_path = os.path.join(invoice_dir, f"invoice_{booking_id}.pdf")

        c = canvas.Canvas(invoice_path)
        c.setFont("Helvetica", 12)

        c.drawString(100, 800, f"Invoice for Booking #{booking_id}")
        c.drawString(100, 780, f"Customer Name: {invoice_details.get('customer_name', '')}")
        c.drawString(100, 760, f"Service: {invoice_details.get('service_name', '')}")
        c.drawString(100, 740, f"Date: {invoice_details.get('date', '')}")
        c.drawString(100, 720, f"Time: {invoice_details.get('time', '')}")
        c.drawString(100, 700, f"Total Price: ${invoice_details.get('total_price', '0.00')}")

        c.save()
        logger.info(f"Invoice generated at {invoice_path}")
        return f"Invoice generated at {invoice_path}"
    except KeyError as e:
        logger.error(f"Missing invoice detail: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error generating invoice for booking {booking_id}: {str(e)}")
        raise


@shared_task(bind=True, max_retries=3)
def update_search_index(self, service_id):
    """
    Updates the Elasticsearch index for a specific service.
    """
    logger.info(f"update_search_index triggered for Service ID {service_id}")
    try:
        from elasticsearch.exceptions import ConnectionError, TransportError
        from .documents import ServiceDocument
        from .models import Service

        service = Service.objects.get(id=service_id)
        ServiceDocument().update(service)
        logger.info(f"Search index updated for Service ID: {service_id}")
        return f"Search index updated for Service ID: {service_id}"

    except Service.DoesNotExist:
        msg = f"Service ID {service_id} does not exist."
        logger.error(msg)
        return msg
    except (ConnectionError, TransportError) as e:
        retry_count = self.request.retries
        logger.error(f"Connection/Transport error: {str(e)}. Retry count: {retry_count}")
        if retry_count < self.max_retries:
            self.retry(countdown=2 ** retry_count, exc=e)
        return f"Failed to update search index for {service_id} after {retry_count} retries: {str(e)}"
    except Exception as e:
        logger.error(f"Unexpected error updating search index for Service ID {service_id}: {str(e)}")
        raise


@shared_task
def remove_from_search_index(service_id):
    """
    Removes a service from the Elasticsearch index.
    """
    logger.info(f"remove_from_search_index triggered for Service ID {service_id}")
    try:
        from .documents import ServiceDocument
        ServiceDocument().delete(service_id)
        return f"Search index entry removed for Service ID: {service_id}"
    except Exception as e:
        logger.error(f"Failed to remove Service ID {service_id} from the search index: {str(e)}")
        return f"Failed to remove Service ID {service_id} from the search index: {str(e)}"


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={'max_retries': 3}
)
@rate_limit('calendar_sync')
@close_db_connection
@transaction.atomic
def sync_booking_to_google_calendar(self, booking_id):
    """
    Sync a booking to Google Calendar.
    """
    from .models import Booking
    logger.info(f"sync_booking_to_google_calendar triggered for Booking ID {booking_id}")
    try:
        booking = Booking.objects.select_related('user', 'service').get(id=booking_id)
        calendar_service = create_calendar_service()

        event_body = {
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

        response = calendar_service.events().insert(calendarId='primary', body=event_body).execute()
        event_id = response.get('id')
        logger.info(f"Booking {booking_id} synced to Google Calendar. Event ID: {event_id}")
        return f"Booking {booking_id} synced to Google Calendar."

    except Booking.DoesNotExist:
        msg = f"Booking ID {booking_id} does not exist."
        logger.error(msg)
        return msg
    except Exception as e:
        logger.error(f"Failed to sync booking {booking_id} to Google Calendar: {str(e)}")
        raise
