import os
from celery import shared_task
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from email.mime.text import MIMEText
import base64
from django.core.mail import send_mail
from google_auth_oauthlib.flow import InstalledAppFlow


# Path to credentials.json
CREDENTIALS_FILE = os.path.join('config', 'credentials.json')
TOKEN_FILE = os.path.join('config', 'token.json')
# Define the scopes
SCOPES = ['https://www.googleapis.com/auth/gmail.send']


def create_gmail_service():
    """
    Authenticate with Gmail API and return the service instance.
    """
    creds = None
    TOKEN_FILE = 'config/token.json'
    CREDENTIALS_FILE = 'config/credentials.json'

    # Load the token if it exists
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

    # If there are no valid credentials, request the user to authenticate
    if not creds or not creds.valid:
        flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
        creds = flow.run_local_server(port=0)

        # Save the credentials for future use
        with open(TOKEN_FILE, 'w') as token:
            token.write(creds.to_json())

    service = build('gmail', 'v1', credentials=creds)
    return service

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
