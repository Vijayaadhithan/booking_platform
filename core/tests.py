# tests.py

from django.test import TestCase, Client
from django.urls import reverse
from django.core.exceptions import ValidationError
from django.utils.timezone import now, timedelta
from rest_framework.test import APITestCase
from rest_framework import status
from decimal import Decimal

from .models import (
    User, Membership, Service, ServiceProvider, Booking,
    Review, ServiceCategory, Address, ServiceProviderAvailability,
    ServiceVariation, ServiceBundle, GroupBooking, GroupParticipant,
    WaitingList, Favorite
)

class UserModelTest(TestCase):
    def setUp(self):
        self.user_data = {
            'username': 'testuser',
            'email': 'test@example.com',
            'password': 'testpass123',
            'first_name': 'Test',
            'last_name': 'User',
            'phone_number': '+1234567890'
        }
        self.user = User.objects.create_user(**self.user_data)

    def test_user_creation(self):
        self.assertTrue(isinstance(self.user, User))
        self.assertEqual(str(self.user), 'Test User')  # __str__

    def test_user_token_creation(self):
        from rest_framework.authtoken.models import Token
        self.assertTrue(Token.objects.filter(user=self.user).exists())


class MembershipModelTest(TestCase):
    def setUp(self):
        self.membership = Membership.objects.create(
            name='Premium',
            price=Decimal('99.99'),
            duration=30,
            benefits='Premium benefits'
        )

    def test_membership_creation(self):
        self.assertEqual(self.membership.name, 'Premium')


class AddressModelTest(TestCase):
    def setUp(self):
        self.address = Address.objects.create(
            street_address='123 Test St',
            city='Test City',
            state='Test State',
            zip_code='12345',
            country='Test Country'
        )

    def test_address_creation(self):
        self.assertTrue(isinstance(self.address, Address))
        # If geopy cannot locate 'Test City', lat/long might remain None
        # This test is environment-dependent
        # self.assertIsNotNone(self.address.latitude)


class ServiceProviderModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='provider', password='pass123')
        self.address = Address.objects.create(
            street_address='123 Provider St',
            city='Provider City',
            state='Provider State',
            zip_code='12345',
            country='Provider Country'
        )
        self.provider = ServiceProvider.objects.create(
            user=self.user,
            service_type='Test Service',
            address=self.address
        )

    def test_provider_creation(self):
        self.assertEqual(self.provider.user.username, 'provider')
        self.assertEqual(self.provider.address, self.address)


class ServiceModelTest(TestCase):
    def setUp(self):
        self.category = ServiceCategory.objects.create(name='Test Category')
        self.service = Service.objects.create(
            name='Test Service',
            description='Test Description',
            category=self.category,
            base_price=Decimal('50.00'),
            unit_price=Decimal('25.00'),
            duration=timedelta(hours=1)
        )

    def test_service_creation(self):
        self.assertEqual(self.service.name, 'Test Service')

    def test_service_timing(self):
        total_time = self.service.duration + self.service.buffer_time
        self.assertEqual(total_time, timedelta(hours=1))


class BookingModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='customer', password='pass123')
        self.provider_user = User.objects.create_user(username='provider', password='pass123')
        self.provider = ServiceProvider.objects.create(user=self.provider_user, service_type='Test')
        self.service = Service.objects.create(
            name='Test Service',
            base_price=Decimal('50.00'),
            unit_price=Decimal('25.00'),
            duration=timedelta(hours=1)
        )

    def test_booking_creation(self):
        booking_time = now() + timedelta(days=1)
        booking = Booking.objects.create(
            user=self.user,
            service_provider=self.provider,
            service=self.service,
            appointment_time=booking_time
        )
        self.assertEqual(booking.status, 'pending')
        self.assertEqual(booking.payment_status, 'pending')

    def test_price_calculation(self):
        booking_time = now() + timedelta(days=1)
        booking = Booking.objects.create(
            user=self.user,
            service_provider=self.provider,
            service=self.service,
            appointment_time=booking_time
        )
        expected_price = self.service.base_price + (self.service.unit_price * Decimal('1.0'))
        self.assertEqual(booking.calculate_price(), expected_price)


class ReviewModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='reviewer', password='pass123')
        self.provider_user = User.objects.create_user(username='provider', password='pass123')
        self.provider = ServiceProvider.objects.create(user=self.provider_user, service_type='Test')
        self.service = Service.objects.create(
            name='Test Service',
            base_price=Decimal('50.00'),
            unit_price=Decimal('25.00'),
            duration=timedelta(hours=1)
        )
        self.booking = Booking.objects.create(
            user=self.user,
            service_provider=self.provider,
            service=self.service,
            appointment_time=now() - timedelta(days=1),
            status='completed'
        )

    def test_review_creation(self):
        review = Review.objects.create(
            user=self.user,
            service_provider=self.provider,
            rating=5,
            booking=self.booking
        )
        self.assertEqual(review.rating, 5)
        self.assertEqual(review.booking, self.booking)


class GroupBookingModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='participant', password='pass123')
        self.provider_user = User.objects.create_user(username='provider', password='pass123')
        self.provider = ServiceProvider.objects.create(user=self.provider_user, service_type='Test')
        self.service = Service.objects.create(
            name='Group Service',
            base_price=Decimal('30.00'),
            unit_price=Decimal('15.00'),
            duration=timedelta(hours=1)
        )

    def test_group_booking_creation(self):
        group_booking = GroupBooking.objects.create(
            service_provider=self.provider,
            service=self.service,
            appointment_time=now() + timedelta(days=1),
            max_participants=5
        )
        self.assertEqual(group_booking.current_participants, 0)


class APITests(APITestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='testuser', password='testpass123')
        self.client.login(username='testuser', password='testpass123')

    def test_service_list_api(self):
        url = reverse('service-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_booking_creation_api(self):
        provider_user = User.objects.create_user(username='provider', password='pass123')
        provider = ServiceProvider.objects.create(user=provider_user, service_type='Test')
        service = Service.objects.create(
            name='Test Service',
            base_price=Decimal('50.00'),
            unit_price=Decimal('25.00'),
            duration=timedelta(hours=1)
        )
        url = reverse('booking-list')
        data = {
            'service_provider': provider.id,
            'service': service.id,
            'appointment_time': (now() + timedelta(days=1)).isoformat()
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
