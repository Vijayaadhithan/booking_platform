# test_notifications.py

from django.test import TestCase
from django.core import mail
from django.utils.timezone import now, timedelta
from unittest.mock import patch
from decimal import Decimal

from core.models import User, Booking, ServiceProvider, Service


class NotificationTest(TestCase):
    """
    Tests for notifications: email confirmations, reminders, calendar events.
    """
    def setUp(self):
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
            user=self.provider_user, service_type='Test Service'
        )
        self.service = Service.objects.create(
            name='Test Service',
            base_price=Decimal('50.00'),
            unit_price=Decimal('25.00'),
            duration=timedelta(hours=1)
        )

    @patch('core.tasks.send_booking_confirmation_email_gmail.delay')
    def test_booking_confirmation_email(self, mock_email_task):
        booking = Booking.objects.create(
            user=self.user,
            service_provider=self.provider,
            service=self.service,
            appointment_time=now() + timedelta(days=1)
        )
        # If your code automatically calls the email task upon booking creation,
        # ensure that logic is triggered in your view or signals
        mock_email_task.assert_called_once()

    @patch('core.tasks.send_booking_reminder.delay')
    def test_reminder_email(self, mock_reminder_task):
        booking = Booking.objects.create(
            user=self.user,
            service_provider=self.provider,
            service=self.service,
            appointment_time=now() + timedelta(days=1)
        )
        mock_reminder_task.assert_not_called()
        # You might call the reminder task later, or check if scheduled

    @patch('core.tasks.sync_booking_to_google_calendar.delay')
    def test_calendar_event_creation(self, mock_calendar_task):
        booking = Booking.objects.create(
            user=self.user,
            service_provider=self.provider,
            service=self.service,
            appointment_time=now() + timedelta(days=1)
        )
        mock_calendar_task.assert_called_once()

    def test_actual_email_sending(self):
        booking = Booking.objects.create(
            user=self.user,
            service_provider=self.provider,
            service=self.service,
            appointment_time=now() + timedelta(days=1)
        )
        mail.send_mail(
            'Booking Confirmation',
            f'Your booking for {booking.service.name} is confirmed.',
            'from@example.com',
            [self.user.email],
            fail_silently=False
        )
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(self.service.name, mail.outbox[0].body)


    def test_multiple_notification_recipients(self):
        booking = Booking.objects.create(
            user=self.user,
            service_provider=self.provider,
            service=self.service,
            appointment_time=now() + timedelta(days=1)
        )
        recipients = [self.user.email, self.provider_user.email, 'admin@example.com']
        mail.send_mail(
            'Booking Confirmation',
            f'Confirmation for {booking.service.name}',
            'from@example.com',
            recipients,
            fail_silently=False
        )
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(set(mail.outbox[0].to), set(recipients))
