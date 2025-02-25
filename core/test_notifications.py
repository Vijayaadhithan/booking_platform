from django.test import TestCase
from django.core import mail
from django.utils.timezone import now, timedelta
from unittest.mock import patch, MagicMock
from .models import User, Booking, ServiceProvider, Service
from decimal import Decimal

class NotificationTest(TestCase):
    """Test suite for notification-related functionality in the booking platform.
    
    This class tests various notification features including:
    - Email confirmations for new bookings
    - Reminder emails for upcoming appointments
    - Calendar event creation and updates
    - Actual email sending functionality
    """
    
    def setUp(self):
        """Set up test data for all notification tests.
        
        Creates test users (customer and service provider), service provider profile,
        and a basic service for testing.
        """
        # Create test users
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.provider_user = User.objects.create_user(
            username='provider',
            email='provider@example.com',
            password='pass123'
        )
        self.provider = ServiceProvider.objects.create(
            user=self.provider_user,
            service_type='Test Service'
        )
        self.service = Service.objects.create(
            name='Test Service',
            base_price=Decimal('50.00'),
            unit_price=Decimal('25.00'),
            duration=timedelta(hours=1)
        )

    @patch('core.tasks.send_booking_confirmation_email.delay')
    def test_booking_confirmation_email(self, mock_email_task):
        """Test that booking confirmation emails are triggered correctly.
        
        Verifies that the confirmation email task is called with the correct
        booking ID when a new booking is created.
        """
        # Create a booking
        booking = Booking.objects.create(
            user=self.user,
            service_provider=self.provider,
            service=self.service,
            appointment_time=now() + timedelta(days=1)
        )
        
        # Check if email task was called
        mock_email_task.assert_called_once_with(booking.id)

    @patch('core.tasks.send_reminder_email.delay')
    def test_reminder_email(self, mock_reminder_task):
        """Test that reminder emails are scheduled correctly.
        
        Ensures that the reminder email task is scheduled with the correct
        booking ID for future appointments.
        """
        # Create a booking for tomorrow
        booking = Booking.objects.create(
            user=self.user,
            service_provider=self.provider,
            service=self.service,
            appointment_time=now() + timedelta(days=1)
        )
        
        # Check if reminder task was scheduled
        mock_reminder_task.assert_called_once_with(booking.id)

    @patch('core.tasks.create_calendar_event.delay')
    def test_calendar_event_creation(self, mock_calendar_task):
        """Test calendar event creation for new bookings.
        
        Verifies that calendar events are created with correct participant
        emails when a new booking is made.
        """
        # Create a booking
        booking = Booking.objects.create(
            user=self.user,
            service_provider=self.provider,
            service=self.service,
            appointment_time=now() + timedelta(days=1)
        )
        
        # Check if calendar task was called
        mock_calendar_task.assert_called_once_with(
            booking.id,
            self.user.email,
            self.provider_user.email
        )

    @patch('core.tasks.update_calendar_event.delay')
    def test_calendar_event_update(self, mock_calendar_update):
        """Test calendar event updates when booking times change.
        
        Ensures that calendar events are properly updated when the
        appointment time of a booking is modified.
        """
        # Create a booking
        booking = Booking.objects.create(
            user=self.user,
            service_provider=self.provider,
            service=self.service,
            appointment_time=now() + timedelta(days=1)
        )
        
        # Update booking time
        new_time = now() + timedelta(days=2)
        booking.appointment_time = new_time
        booking.save()
        
        # Check if calendar update task was called
        mock_calendar_update.assert_called_once_with(
            booking.id,
            new_time.isoformat()
        )

    def test_actual_email_sending(self):
        """Test the actual email sending functionality.
        
        Verifies that emails are properly formatted and sent to the correct
        recipient with the expected subject and content.
        """
        # Create a booking
        booking = Booking.objects.create(
            user=self.user,
            service_provider=self.provider,
            service=self.service,
            appointment_time=now() + timedelta(days=1)
        )
        
        # Send test email
        mail.send_mail(
            'Booking Confirmation',
            f'Your booking for {self.service.name} is confirmed.',
            'from@example.com',
            [self.user.email],
            fail_silently=False,
        )
        
        # Test that one message has been sent
        self.assertEqual(len(mail.outbox), 1)
        
        # Verify the email content
        self.assertEqual(mail.outbox[0].subject, 'Booking Confirmation')
        self.assertEqual(mail.outbox[0].to[0], self.user.email)

    def test_failed_email_sending(self):
        """Test handling of email sending failures.
        
        Verifies that the system properly handles cases where email sending fails.
        """
        booking = Booking.objects.create(
            user=self.user,
            service_provider=self.provider,
            service=self.service,
            appointment_time=now() + timedelta(days=1)
        )
        
        # Test email sending with invalid recipient
        with self.assertRaises(Exception):
            mail.send_mail(
                'Booking Confirmation',
                'Test message',
                'from@example.com',
                ['invalid-email'],  # Invalid email address
                fail_silently=False,
            )

    def test_multiple_notification_recipients(self):
        """Test sending notifications to multiple recipients.
        
        Verifies that notifications can be sent to multiple recipients
        (e.g., user, provider, and admin) correctly.
        """
        booking = Booking.objects.create(
            user=self.user,
            service_provider=self.provider,
            service=self.service,
            appointment_time=now() + timedelta(days=1)
        )
        
        # Send test email to multiple recipients
        recipients = [self.user.email, self.provider_user.email, 'admin@example.com']
        mail.send_mail(
            'Booking Confirmation',
            f'Booking confirmation for {self.service.name}',
            'from@example.com',
            recipients,
            fail_silently=False,
        )
        
        # Verify all recipients received the email
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(set(mail.outbox[0].to), set(recipients))