# test_utils.py

from django.test import TestCase
from django.utils.timezone import now, timedelta
from unittest.mock import patch, MagicMock
from rest_framework import status
from rest_framework.test import APIRequestFactory
from decimal import Decimal
import logging

from .models import (
    User, ServiceProvider, Service, Booking,
    ServiceProviderAvailability, ServiceCategory
)
from .utils import (
    check_provider_availability, format_availability_response,
    handle_booking_tasks, check_booking_overlap
)


class UtilsAvailabilityTest(TestCase):
    """Test the availability checking utility functions"""
    
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
        
        # Create service
        self.service = Service.objects.create(
            name='Test Service',
            description='Test Description',
            category=self.category,
            base_price=Decimal('50.00'),
            unit_price=Decimal('25.00'),
            duration=timedelta(hours=1),
            buffer_time=timedelta(minutes=15)
        )
        
        # Create provider availability for Monday
        self.monday_availability = ServiceProviderAvailability.objects.create(
            service_provider=self.provider,
            day_of_week='Monday',
            start_time='09:00:00',
            end_time='17:00:00'
        )
        
        # Create a future Monday date for testing
        # Find the next Monday from today
        today = now().date()
        days_ahead = 0 - today.weekday()
        if days_ahead <= 0:  # Target day already happened this week
            days_ahead += 7
        self.next_monday = today + timedelta(days=days_ahead)
        
        # Create appointment time string for testing (10 AM on next Monday)
        self.appointment_time_str = f"{self.next_monday.isoformat()}T10:00:00Z"
    
    def test_check_provider_availability_missing_params(self):
        """Test availability check with missing parameters"""
        # Test with missing provider_id
        result = check_provider_availability(None, self.service.id, self.appointment_time_str)
        self.assertEqual(result[0], False)
        self.assertEqual(result[1], "Missing required parameters.")
        self.assertEqual(result[2], status.HTTP_400_BAD_REQUEST)
        
        # Test with missing service_id
        result = check_provider_availability(self.provider.id, None, self.appointment_time_str)
        self.assertEqual(result[0], False)
        self.assertEqual(result[1], "Missing required parameters.")
        
        # Test with missing appointment_time
        result = check_provider_availability(self.provider.id, self.service.id, None)
        self.assertEqual(result[0], False)
        self.assertEqual(result[1], "Missing required parameters.")
    
    def test_check_provider_availability_invalid_time_format(self):
        """Test availability check with invalid time format"""
        result = check_provider_availability(
            self.provider.id, self.service.id, "invalid-time-format"
        )
        self.assertEqual(result[0], False)
        self.assertEqual(result[1], "Invalid appointment_time format.")
        self.assertEqual(result[2], status.HTTP_400_BAD_REQUEST)
    
    def test_check_provider_availability_provider_not_available(self):
        """Test when provider is not available at the requested time"""
        # Create a Tuesday appointment (provider only available on Monday)
        tuesday_date = self.next_monday + timedelta(days=1)
        tuesday_appointment = f"{tuesday_date.isoformat()}T10:00:00Z"
        
        result = check_provider_availability(
            self.provider.id, self.service.id, tuesday_appointment
        )
        self.assertEqual(result[0], False)
        self.assertEqual(result[1], "Provider not available at this time.")
        self.assertEqual(result[2], status.HTTP_200_OK)
    
    def test_check_provider_availability_service_not_exist(self):
        """Test when the requested service does not exist"""
        non_existent_service_id = 9999  # Assuming this ID doesn't exist
        
        result = check_provider_availability(
            self.provider.id, non_existent_service_id, self.appointment_time_str
        )
        self.assertEqual(result[0], False)
        self.assertEqual(result[1], "Service does not exist.")
        self.assertEqual(result[2], status.HTTP_200_OK)
    
    def test_check_provider_availability_with_overlap(self):
        """Test when there's an overlapping booking"""
        # Parse the appointment time
        parsed_time = now().replace(
            hour=10, minute=0, second=0, microsecond=0
        ) + timedelta(days=1)
        
        # Create an existing booking that overlaps
        Booking.objects.create(
            user=self.user,
            service_provider=self.provider,
            service=self.service,
            appointment_time=parsed_time
        )
        
        # Use the same time for the availability check
        appointment_time_str = parsed_time.isoformat() + "Z"
        
        result = check_provider_availability(
            self.provider.id, self.service.id, appointment_time_str
        )
        self.assertEqual(result[0], False)
        self.assertEqual(result[1], "Overlapping booking found.")
        self.assertEqual(result[2], status.HTTP_200_OK)
    
    def test_check_provider_availability_success(self):
        """Test successful availability check"""
        # Ensure the provider offers this service
        self.provider.services_offered.add(self.service)
        
        result = check_provider_availability(
            self.provider.id, self.service.id, self.appointment_time_str
        )
        self.assertEqual(result[0], True)
        self.assertEqual(result[1], "Time slot is available.")
        self.assertEqual(result[2], status.HTTP_200_OK)
        self.assertIsNotNone(result[3])  # parsed_time
        self.assertEqual(result[4], self.service)  # service object


class UtilsResponseFormattingTest(TestCase):
    """Test the response formatting utility functions"""
    
    def test_format_availability_response(self):
        """Test formatting of availability responses"""
        # Test available response
        response = format_availability_response(True, "Time slot is available.")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["available"], True)
        self.assertEqual(response.data["reason"], "Time slot is available.")
        
        # Test unavailable response
        response = format_availability_response(False, "Provider not available.")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["available"], False)
        self.assertEqual(response.data["reason"], "Provider not available.")
        
        # Test with custom status code
        response = format_availability_response(
            False, "Missing parameters.", status.HTTP_400_BAD_REQUEST
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class UtilsBookingTasksTest(TestCase):
    """Test the booking tasks utility functions"""
    
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
        
        # Create service
        self.service = Service.objects.create(
            name='Test Service',
            base_price=Decimal('50.00'),
            unit_price=Decimal('25.00'),
            duration=timedelta(hours=1)
        )
        
        # Create booking
        self.booking = Booking.objects.create(
            user=self.user,
            service_provider=self.provider,
            service=self.service,
            appointment_time=now() + timedelta(days=1),
            total_price=Decimal('75.00')
        )
        
        # Create logger
        self.logger = logging.getLogger('test_logger')
    
    @patch('core.utils.send_booking_confirmation_email_gmail.delay')
    @patch('core.utils.sync_booking_to_google_calendar.delay')
    @patch('core.utils.generate_invoice.delay')
    def test_handle_booking_tasks_success(self, mock_invoice, mock_calendar, mock_email):
        """Test successful handling of all booking tasks"""
        handle_booking_tasks(self.booking, self.logger)
        
        # Verify all tasks were called
        mock_email.assert_called_once()
        mock_calendar.assert_called_once_with(self.booking.id)
        mock_invoice.assert_called_once()
    
    @patch('core.utils.send_booking_confirmation_email_gmail.delay')
    @patch('core.utils.sync_booking_to_google_calendar.delay')
    @patch('core.utils.generate_invoice.delay')
    def test_handle_booking_tasks_email_exception(self, mock_invoice, mock_calendar, mock_email):
        """Test handling of email task exception"""
        mock_email.side_effect = Exception("Email error")
        
        # Should not raise exception
        handle_booking_tasks(self.booking, self.logger)
        
        # Other tasks should still be called
        mock_calendar.assert_called_once()
        mock_invoice.assert_called_once()
    
    @patch('core.utils.send_booking_confirmation_email_gmail.delay')
    @patch('core.utils.sync_booking_to_google_calendar.delay')
    @patch('core.utils.generate_invoice.delay')
    def test_handle_booking_tasks_calendar_exception(self, mock_invoice, mock_calendar, mock_email):
        """Test handling of calendar task exception"""
        mock_calendar.side_effect = Exception("Calendar error")
        
        # Should not raise exception
        handle_booking_tasks(self.booking, self.logger)
        
        # Other tasks should still be called
        mock_email.assert_called_once()
        mock_invoice.assert_called_once()
    
    @patch('core.utils.send_booking_confirmation_email_gmail.delay')
    @patch('core.utils.sync_booking_to_google_calendar.delay')
    @patch('core.utils.generate_invoice.delay')
    def test_handle_booking_tasks_invoice_exception(self, mock_invoice, mock_calendar, mock_email):
        """Test handling of invoice task exception"""
        mock_invoice.side_effect = Exception("Invoice error")
        
        # Should not raise exception
        handle_booking_tasks(self.booking, self.logger)
        
        # Other tasks should still be called
        mock_email.assert_called_once()
        mock_calendar.assert_called_once()


class UtilsBookingOverlapTest(TestCase):
    """Test the booking overlap utility functions"""
    
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
        
        # Create service with buffer time
        self.service = Service.objects.create(
            name='Test Service',
            base_price=Decimal('50.00'),
            unit_price=Decimal('25.00'),
            duration=timedelta(hours=1),
            buffer_time=timedelta(minutes=15)
        )
        
        # Create appointment time
        self.appointment_time = now().replace(
            hour=10, minute=0, second=0, microsecond=0
        ) + timedelta(days=1)
    
    def test_check_booking_overlap_no_overlap(self):
        """Test when there's no booking overlap"""
        # No existing bookings, so there should be no overlap
        result = check_booking_overlap(
            self.provider, self.appointment_time, self.service
        )
        self.assertFalse(result)
    
    def test_check_booking_overlap_with_overlap(self):
        """Test when there is a booking overlap"""
        # Create an existing booking at the same time
        Booking.objects.create(
            user=self.user,
            service_provider=self.provider,
            service=self.service,
            appointment_time=self.appointment_time
        )
        
        # Check for overlap at the same time
        result = check_booking_overlap(
            self.provider, self.appointment_time, self.service
        )
        self.assertTrue(result)
    
    def test_check_booking_overlap_with_buffer_overlap(self):
        """Test when there's an overlap due to buffer time"""
        # Create an existing booking that ends right before our appointment time
        earlier_time = self.appointment_time - timedelta(minutes=30)
        Booking.objects.create(
            user=self.user,
            service_provider=self.provider,
            service=self.service,
            appointment_time=earlier_time
        )
        
        # Check for overlap - this should overlap due to buffer time
        result = check_booking_overlap(
            self.provider, self.appointment_time, self.service
        )
        self.assertTrue(result)
        
    def test_check_booking_overlap_outside_buffer(self):
        """Test when a booking is outside the buffer time"""
        # Create a booking that's far enough away to not overlap
        distant_time = self.appointment_time - timedelta(hours=3)
        Booking.objects.create(
            user=self.user,
            service_provider=self.provider,
            service=self.service,
            appointment_time=distant_time
        )
        
        # Check for overlap - this should not overlap
        result = check_booking_overlap(
            self.provider, self.appointment_time, self.service
        )
        self.assertFalse(result)
        
    def test_check_booking_overlap_with_recurring_flag(self):
        """Test the is_recurring flag in booking overlap check"""
        # Create an existing booking
        Booking.objects.create(
            user=self.user,
            service_provider=self.provider,
            service=self.service,
            appointment_time=self.appointment_time
        )
        
        # Check with is_recurring flag
        result = check_booking_overlap(
            self.provider, self.appointment_time, self.service, is_recurring=True
        )
        self.assertTrue(result)
        
        # The is_recurring flag doesn't change the behavior in the current implementation
        # but we test it for completeness and future-proofing