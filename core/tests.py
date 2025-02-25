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
    """Test suite for User model functionality.
    
    Tests user creation, authentication, and token generation.
    Validates user profile data and string representation.
    """
    
    def setUp(self):
        """Create test user with complete profile data."""
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
        """Verify user instance creation and string representation."""
        self.assertTrue(isinstance(self.user, User))
        self.assertEqual(self.user.__str__(), 'Test User')

    def test_user_token_creation(self):
        """Ensure authentication token is created for new users."""
        from rest_framework.authtoken.models import Token
        self.assertTrue(Token.objects.filter(user=self.user).exists())

class MembershipModelTest(TestCase):
    """Test suite for Membership model.
    
    Validates membership creation, pricing, and duration handling.
    """
    
    def setUp(self):
        """Create test membership with standard attributes."""
        self.membership = Membership.objects.create(
            name='Premium',
            price=Decimal('99.99'),
            duration=30,
            benefits='Premium benefits'
        )

    def test_membership_creation(self):
        """Verify membership attributes are correctly stored."""
        self.assertEqual(self.membership.name, 'Premium')
        self.assertEqual(self.membership.price, Decimal('99.99'))

class AddressModelTest(TestCase):
    """Test suite for Address model.
    
    Validates address creation and geocoding functionality.
    """
    
    def setUp(self):
        """Create test address with complete location data."""
        self.address = Address.objects.create(
            street_address='123 Test St',
            city='Test City',
            state='Test State',
            zip_code='12345',
            country='Test Country'
        )

    def test_address_creation(self):
        """Verify address instance and geocoding results."""
        self.assertTrue(isinstance(self.address, Address))
        self.assertTrue(self.address.latitude is not None)
        self.assertTrue(self.address.longitude is not None)

class ServiceProviderModelTest(TestCase):
    """Test suite for ServiceProvider model.
    
    Validates service provider creation, profile management, and address association.
    Tests provider-specific functionality and relationships.
    """
    
    def setUp(self):
        """Create test service provider with associated user and address."""
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
        """Verify service provider creation and relationships."""
        self.assertEqual(self.provider.user.username, 'provider')
        self.assertEqual(self.provider.service_type, 'Test Service')
        self.assertEqual(self.provider.address, self.address)

class ServiceModelTest(TestCase):
    """Test suite for Service model.
    
    Validates service creation, pricing calculations, and time management.
    Tests service categorization and buffer time handling.
    """
    
    def setUp(self):
        """Create test service with category and time specifications."""
        self.category = ServiceCategory.objects.create(name='Test Category')
        self.service = Service.objects.create(
            name='Test Service',
            description='Test Description',
            category=self.category,
            base_price=Decimal('50.00'),
            unit_price=Decimal('25.00'),
            duration=timedelta(hours=1),
            buffer_time=timedelta(minutes=15)
        )

    def test_service_creation(self):
        """Verify service attributes and relationships."""
        self.assertEqual(self.service.name, 'Test Service')
        self.assertEqual(self.service.base_price, Decimal('50.00'))
        self.assertEqual(self.service.category, self.category)

    def test_service_timing(self):
        """Validate service duration and buffer time calculations."""
        total_time = self.service.duration + self.service.buffer_time
        self.assertEqual(total_time, timedelta(hours=1, minutes=15))

class BookingModelTest(TestCase):
    """Test suite for Booking model.
    
    Validates booking creation, time slot management, and pricing calculations.
    Tests booking status transitions and validation rules.
    """
    
    def setUp(self):
        """Create necessary objects for booking tests."""
        self.user = User.objects.create_user(username='customer', password='pass123')
        self.provider_user = User.objects.create_user(username='provider', password='pass123')
        self.provider = ServiceProvider.objects.create(user=self.provider_user, service_type='Test')
        self.service = Service.objects.create(
            name='Test Service',
            base_price=Decimal('50.00'),
            unit_price=Decimal('25.00'),
            duration=timedelta(hours=1),
            buffer_time=timedelta(minutes=15)
        )

    def test_booking_creation(self):
        """Verify booking creation and initial status."""
        booking = Booking.objects.create(
            user=self.user,
            service_provider=self.provider,
            service=self.service,
            appointment_time=now() + timedelta(days=1)
        )
        self.assertEqual(booking.status, 'pending')
        self.assertEqual(booking.payment_status, 'pending')

    def test_buffer_time_validation(self):
        """Test booking time slot validation with buffer time."""
        booking_time = now() + timedelta(days=1)
        Booking.objects.create(
            user=self.user,
            service_provider=self.provider,
            service=self.service,
            appointment_time=booking_time
        )

        with self.assertRaises(ValidationError):
            Booking.objects.create(
                user=self.user,
                service_provider=self.provider,
                service=self.service,
                appointment_time=booking_time + timedelta(minutes=10)
            )

    def test_price_calculation(self):
        """Validate booking price calculation logic."""
        booking = Booking.objects.create(
            user=self.user,
            service_provider=self.provider,
            service=self.service,
            appointment_time=now() + timedelta(days=1)
        )
        expected_price = self.service.base_price + (self.service.unit_price * Decimal('1.0'))
        self.assertEqual(booking.calculate_price(), expected_price)

class ReviewModelTest(TestCase):
    """Test suite for Review model.
    
    Validates review creation, rating validation, and relationship with bookings.
    Tests review submission rules and constraints.
    """
    
    def setUp(self):
        """Create test objects needed for review testing."""
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
        """Verify review creation and attribute validation."""
        review = Review.objects.create(
            user=self.user,
            service_provider=self.provider,
            rating=5,
            comment='Great service!',
            booking=self.booking
        )
        self.assertEqual(review.rating, 5)
        self.assertEqual(review.comment, 'Great service!')

    def test_review_validation(self):
        """Test review validation rules for incomplete bookings."""
        # Test review for incomplete booking
        incomplete_booking = Booking.objects.create(
            user=self.user,
            service_provider=self.provider,
            service=self.service,
            appointment_time=now() + timedelta(days=1),
            status='pending'
        )
        with self.assertRaises(ValidationError):
            Review.objects.create(
                user=self.user,
                service_provider=self.provider,
                rating=5,
                comment='Great service!',
                booking=incomplete_booking
            )

class GroupBookingModelTest(TestCase):
    """Test suite for GroupBooking and GroupParticipant models.
    
    Validates group booking creation, participant management, and capacity controls.
    Tests group booking specific features and constraints.
    """
    
    def setUp(self):
        """Create test objects for group booking scenarios."""
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
        """Test group booking creation and participant management."""
        group_booking = GroupBooking.objects.create(
            service_provider=self.provider,
            service=self.service,
            appointment_time=now() + timedelta(days=1),
            max_participants=5
        )
        self.assertEqual(group_booking.current_participants, 0)
        
        participant = GroupParticipant.objects.create(
            user=self.user,
            group_booking=group_booking
        )
        group_booking.refresh_from_db()
        self.assertEqual(group_booking.current_participants, 1)

class APITests(APITestCase):
    """Test suite for API endpoints.
    
    Validates API functionality, authentication, and response handling.
    Tests various API endpoints and their behavior.
    """
    
    def setUp(self):
        """Set up test client and authenticated user."""
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        self.client.login(username='testuser', password='testpass123')

    def test_service_list_api(self):
        """Test service listing endpoint."""
        url = reverse('service-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_booking_creation_api(self):
        """Test booking creation through API."""
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
