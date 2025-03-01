# test_service_model.py

from django.test import TestCase
from django.utils.timezone import now, timedelta
from decimal import Decimal

from .models import (
    User, ServiceProvider, Service, Booking,
    ServiceCategory
)


class ServiceModelTest(TestCase):
    """Test the Service model methods"""
    
    def setUp(self):
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
        
        # Create service provider
        self.provider = ServiceProvider.objects.create(
            user=self.provider_user,
            service_type='Test Service'
        )
        
        # Create service category
        self.category = ServiceCategory.objects.create(name='Test Category')
        
        # Create service with buffer time
        self.service = Service.objects.create(
            name='Test Service',
            description='Test Description',
            category=self.category,
            base_price=Decimal('50.00'),
            unit_price=Decimal('25.00'),
            duration=timedelta(hours=1),
            buffer_time=timedelta(minutes=15)
        )
        
        # Add service to provider's offered services
        self.provider.services_offered.add(self.service)
        
        # Create appointment time
        self.appointment_time = now().replace(
            hour=10, minute=0, second=0, microsecond=0
        ) + timedelta(days=1)
    
    def test_get_total_duration(self):
        """Test calculation of total duration including buffer time"""
        expected_duration = timedelta(hours=1, minutes=15)  # 1 hour service + 15 min buffer
        self.assertEqual(self.service.get_total_duration(), expected_duration)
    
    def test_calculate_price_default_duration(self):
        """Test price calculation with default duration"""
        expected_price = Decimal('50.00') + Decimal('25.00')  # base + unit price for 1 hour
        self.assertEqual(self.service.calculate_price(), expected_price)
    
    def test_calculate_price_custom_duration(self):
        """Test price calculation with custom duration"""
        custom_duration = timedelta(hours=2)
        expected_price = Decimal('50.00') + (Decimal('25.00') * 2)  # base + unit price for 2 hours
        self.assertEqual(self.service.calculate_price(custom_duration), expected_price)
    
    def test_is_available_service_inactive(self):
        """Test availability check when service is inactive"""
        self.service.is_active = False
        self.service.save()
        
        is_available = self.service.is_available(self.provider, self.appointment_time)
        self.assertFalse(is_available)
    
    def test_is_available_provider_doesnt_offer(self):
        """Test availability when provider doesn't offer the service"""
        # Create a new service that the provider doesn't offer
        new_service = Service.objects.create(
            name='Unavailable Service',
            description='Not offered by provider',
            category=self.category,
            base_price=Decimal('100.00'),
            unit_price=Decimal('50.00'),
            duration=timedelta(hours=2)
        )
        
        is_available = new_service.is_available(self.provider, self.appointment_time)
        self.assertFalse(is_available)
    
    def test_is_available_with_overlap(self):
        """Test availability check with overlapping booking"""
        # Create an existing booking at the same time
        Booking.objects.create(
            user=self.user,
            service_provider=self.provider,
            service=self.service,
            appointment_time=self.appointment_time
        )
        
        is_available = self.service.is_available(self.provider, self.appointment_time)
        self.assertFalse(is_available)
    
    def test_is_available_success(self):
        """Test successful availability check"""
        is_available = self.service.is_available(self.provider, self.appointment_time)
        self.assertTrue(is_available)
    
    def test_is_available_with_buffer_overlap(self):
        """Test availability with buffer time overlap"""
        # Create a booking that ends right before our appointment time
        buffer_overlap_time = self.appointment_time - timedelta(minutes=10)  # Within buffer time
        Booking.objects.create(
            user=self.user,
            service_provider=self.provider,
            service=self.service,
            appointment_time=buffer_overlap_time
        )
        
        is_available = self.service.is_available(self.provider, self.appointment_time)
        self.assertFalse(is_available)
    
    def test_clean_validation(self):
        """Test the clean method validation"""
        from django.core.exceptions import ValidationError
        
        # Test negative unit price
        with self.assertRaises(ValidationError):
            invalid_service = Service(
                name='Invalid Service',
                description='Invalid',
                category=self.category,
                base_price=Decimal('50.00'),
                unit_price=Decimal('-10.00'),  # Negative unit price
                duration=timedelta(hours=1)
            )
            invalid_service.clean()
        
        # Test negative base price
        with self.assertRaises(ValidationError):
            invalid_service = Service(
                name='Invalid Service',
                description='Invalid',
                category=self.category,
                base_price=Decimal('-50.00'),  # Negative base price
                unit_price=Decimal('25.00'),
                duration=timedelta(hours=1)
            )
            invalid_service.clean()
        
        # Test zero duration
        with self.assertRaises(ValidationError):
            invalid_service = Service(
                name='Invalid Service',
                description='Invalid',
                category=self.category,
                base_price=Decimal('50.00'),
                unit_price=Decimal('25.00'),
                duration=timedelta(seconds=0)  # Zero duration
            )
            invalid_service.clean()
        
        # Test negative buffer time
        with self.assertRaises(ValidationError):
            invalid_service = Service(
                name='Invalid Service',
                description='Invalid',
                category=self.category,
                base_price=Decimal('50.00'),
                unit_price=Decimal('25.00'),
                duration=timedelta(hours=1),
                buffer_time=timedelta(minutes=-15)  # Negative buffer time
            )
            invalid_service.clean()