from django.test import TestCase
from .models import Booking, Service, ServiceProvider, User
from django.utils.timezone import now, timedelta
from django.core.exceptions import ValidationError

class BookingTestCase(TestCase):
    def setUp(self):
        # Set up users, services, and providers
        self.user = User.objects.create(username='testuser')
        self.service = Service.objects.create(name='Test Service', duration=timedelta(hours=1), buffer_time=timedelta(minutes=15))
        self.provider = ServiceProvider.objects.create(user=self.user)

    def test_buffer_time_validation(self):
        # Create a booking
        booking_time = now() + timedelta(days=1)
        Booking.objects.create(service=self.service, service_provider=self.provider, appointment_time=booking_time)

        # Attempt to create another booking within buffer time
        with self.assertRaises(ValidationError):
            Booking.objects.create(service=self.service, service_provider=self.provider, appointment_time=booking_time + timedelta(minutes=50))
