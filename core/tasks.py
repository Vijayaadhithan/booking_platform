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


# Path to credentials.json
CREDENTIALS_FILE = os.path.join('config', 'credentials.json')
TOKEN_FILE = os.path.join('config', 'token.json')
# Define the scopes
SCOPES = [
    'https://www.googleapis.com/auth/gmail.send',
    'https://www.googleapis.com/auth/calendar',
]

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


@shared_task
def send_booking_confirmation_email_gmail(to_email, booking_details):
    """
    Task to send booking confirmation emails using Gmail API.
    """
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

    return f"Email sent: {result.get('id')}"

@shared_task
def generate_invoice(booking_id, invoice_details):
    """
    Task to generate a PDF invoice for a booking.
    """
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

    return f"Invoice generated at {invoice_path}"

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

@shared_task
def sync_booking_to_google_calendar(booking_id):
    """
    Task to sync a booking to Google Calendar.
    """
    from .models import Booking

    try:
        booking = Booking.objects.get(id=booking_id)
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
        }

        service.events().insert(calendarId='primary', body=event).execute()
        return f"Booking {booking_id} synced to Google Calendar."
    except Booking.DoesNotExist:
        return f"Booking ID {booking_id} does not exist."
    except Exception as e:
        return f"Failed to sync booking {booking_id} to Google Calendar: {str(e)}"
    
@shared_task
def send_booking_confirmation(booking_id):
    """
    Task to send a booking confirmation email.
    """
    from .models import Booking
    booking = Booking.objects.get(id=booking_id)
    # Send email logic...
    booking.confirmation_sent = True
    booking.save()
    return f"Booking confirmation sent for booking {booking_id}."

@shared_task
def send_booking_reminder(booking_id):
    """
    Task to send a booking reminder email.
    """
    from .models import Booking
    booking = Booking.objects.get(id=booking_id)
    # Send email logic...
    booking.reminder_sent = True
    booking.save()
    return f"Booking reminder sent for booking {booking_id}."
