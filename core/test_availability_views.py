# test_availability_views.py

from django.test import TestCase
from django.urls import reverse
from django.utils.timezone import now, timedelta
from rest_framework.test import APIClient
from rest_framework import status
from decimal import Decimal
import json

from .models import (
    User, ServiceProvider, Service, Booking,
    ServiceProviderAvailability, ServiceCategory
)


class AvailabilityViewsTest(TestCase):
    """Test the availability checking views"""
    
    def setUp(self):
        # Create test users
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123',
            first_name='Test',
            last_name='User'
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
        
        # Create provider availability for all days of the week
        days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        for day in days:
            ServiceProviderAvailability.objects.create(
                service_provider=self.provider,
                day_of_week=day,
                start_time='09:00:00',
                end_time='17:00:00'
            )
        
        # Create appointment time for tomorrow at 10 AM
        self.appointment_time = now().replace(
            hour=10, minute=0, second=0, microsecond=0
        ) + timedelta(days=1)
        self.appointment_time_str = self.appointment_time.isoformat() + 'Z'
        
        # Setup API client
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
    
    def test_check_availability_view_missing_params(self):
        """Test the class-based view with missing parameters"""
        url = reverse('check-availability')
        
        # Test with missing provider_id
        response = self.client.get(url, {
            'service_id': self.service.id,
            'appointment_time': self.appointment_time_str
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['available'], False)
        self.assertEqual(response.data['reason'], 'Missing required parameters.')
        
        # Test with missing service_id
        response = self.client.get(url, {
            'provider_id': self.provider.id,
            'appointment_time': self.appointment_time_str
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        
        # Test with missing appointment_time
        response = self.client.get(url, {
            'provider_id': self.provider.id,
            'service_id': self.service.id
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_check_availability_view_invalid_time(self):
        """Test the class-based view with invalid time format"""
        url = reverse('check-availability')
        
        response = self.client.get(url, {
            'provider_id': self.provider.id,
            'service_id': self.service.id,
            'appointment_time': 'invalid-time-format'
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['available'], False)
        self.assertEqual(response.data['reason'], 'Invalid appointment_time format.')
    
    def test_check_availability_view_service_not_exist(self):
        """Test the class-based view with non-existent service"""
        url = reverse('check-availability')
        
        response = self.client.get(url, {
            'provider_id': self.provider.id,
            'service_id': 9999,  # Non-existent service ID
            'appointment_time': self.appointment_time_str
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['available'], False)
        self.assertEqual(response.data['reason'], 'Service does not exist.')
    
    def test_check_availability_view_with_overlap(self):
        """Test the class-based view with overlapping booking"""
        # Create an existing booking at the same time
        Booking.objects.create(
            user=self.user,
            service_provider=self.provider,
            service=self.service,
            appointment_time=self.appointment_time
        )
        
        url = reverse('check-availability')
        response = self.client.get(url, {
            'provider_id': self.provider.id,
            'service_id': self.service.id,
            'appointment_time': self.appointment_time_str
        })
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['available'], False)
        self.assertEqual(response.data['reason'], 'Overlapping booking found.')
    
    def test_check_availability_view_success(self):
        """Test successful availability check with class-based view"""
        url = reverse('check-availability')
        response = self.client.get(url, {
            'provider_id': self.provider.id,
            'service_id': self.service.id,
            'appointment_time': self.appointment_time_str
        })
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['available'], True)
        self.assertEqual(response.data['reason'], 'Time slot is available.')
    
    def test_function_based_check_availability(self):
        """Test the function-based availability check view"""
        url = reverse('check-availability-function')
        response = self.client.get(url, {
            'provider_id': self.provider.id,
            'service_id': self.service.id,
            'appointment_time': self.appointment_time_str
        })
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['available'], True)
        self.assertEqual(response.data['reason'], 'Time slot is available.')
    
    def test_unauthenticated_access(self):
        """Test that unauthenticated users cannot access the views"""
        # Create a new client without authentication
        client = APIClient()
        
        # Test class-based view
        url = reverse('check-availability')
        response = client.get(url, {
            'provider_id': self.provider.id,
            'service_id': self.service.id,
            'appointment_time': self.appointment_time_str
        })
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        
        # Test function-based view
        url = reverse('check-availability-function')
        response = client.get(url, {
            'provider_id': self.provider.id,
            'service_id': self.service.id,
            'appointment_time': self.appointment_time_str
        })
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_provider_availability_endpoint(self):
        """Test the service_provider_availability endpoint"""
        url = reverse('provider-availability', args=[self.provider.id])
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 7)  # 7 days of availability
        
        # Check the format of the response
        first_day = response.data[0]
        self.assertIn('day_of_week', first_day)
        self.assertIn('start_time', first_day)
        self.assertIn('end_time', first_day)
        self.assertEqual(first_day['start_time'], '09:00')
        self.assertEqual(first_day['end_time'], '17:00')