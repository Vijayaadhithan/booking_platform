# test_api_config.py

from django.test import TestCase, override_settings
from django.conf import settings
from django.core import mail
from django.utils.timezone import now, timedelta
from rest_framework.test import APITestCase
from rest_framework import status

from core.models import User, Booking, ServiceProvider, Service
from decimal import Decimal

class APIConfigurationTest(TestCase):
    """
    Validate that critical API settings are properly configured (DRF, auth, etc.).
    """
    def test_required_settings(self):
        required_settings = [
            'REST_FRAMEWORK',
            'DEFAULT_FROM_EMAIL',
            'EMAIL_BACKEND',
        ]
        for s in required_settings:
            self.assertTrue(hasattr(settings, s), f"{s} is missing in settings.")

    def test_cors_configuration(self):
        self.assertTrue(hasattr(settings, 'CORS_ALLOWED_ORIGINS'))
        self.assertIsInstance(settings.CORS_ALLOWED_ORIGINS, (list, tuple))


class NotificationConfigTest(TestCase):
    """
    Validates email and calendar integration configurations.
    """
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser', email='test@example.com', password='testpass123'
        )
        self.provider_user = User.objects.create_user(
            username='provider', email='provider@example.com', password='pass123'
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

    def test_email_configuration(self):
        self.assertTrue(hasattr(settings, 'EMAIL_BACKEND'))
        self.assertTrue(hasattr(settings, 'EMAIL_HOST'))
        self.assertTrue(hasattr(settings, 'EMAIL_PORT'))

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_email_sending(self):
        booking = Booking.objects.create(
            user=self.user,
            service_provider=self.provider,
            service=self.service,
            appointment_time=now() + timedelta(days=1)
        )
        mail.send_mail(
            'Test Email',
            f'Your booking: {booking.id}',
            'from@example.com',
            [self.user.email],
            fail_silently=False
        )
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(str(booking.id), mail.outbox[0].body)

    def test_calendar_configuration(self):
        required_calendar_settings = [
            'GOOGLE_API_CREDENTIALS_FILE',
            'GOOGLE_API_TOKEN_FILE',
            'GOOGLE_API_SCOPES',
        ]
        for rc in required_calendar_settings:
            self.assertTrue(hasattr(settings, rc), f"{rc} missing in settings.")


class ExternalServiceConfigTest(TestCase):
    """
    Validates Redis, Celery, and other external service configs.
    """
    def test_redis_configuration(self):
        self.assertTrue(hasattr(settings, 'REDIS_URL'))
        self.assertTrue(hasattr(settings, 'CELERY_BROKER_URL'))

    def test_celery_configuration(self):
        self.assertTrue(hasattr(settings, 'CELERY_RESULT_BACKEND'))
        self.assertTrue(hasattr(settings, 'CELERY_ACCEPT_CONTENT'))


class APIEndpointTest(APITestCase):
    """
    Validates basic API endpoint functionality.
    """
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.client.force_authenticate(user=self.user)

    def test_profile_api(self):
        response = self.client.get('/api/profile/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_api_throttling(self):
        # Example for user rate limit test
        for _ in range(1001):
            response = self.client.get('/api/services/')
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
