from django.utils.dateparse import parse_datetime
from rest_framework.response import Response
from rest_framework import status
from .models import ServiceProviderAvailability, Service, Booking


def check_provider_availability(provider_id, service_id, appointment_time_str):
    """
    Utility function to check if a service provider is available at a specific time.
    
    Args:
        provider_id: ID of the service provider
        service_id: ID of the service
        appointment_time_str: String representation of the appointment time
        
    Returns:
        tuple: (is_available, reason, status_code, parsed_time, service)
            - is_available: Boolean indicating if the time slot is available
            - reason: String explaining why the slot is available/unavailable
            - status_code: HTTP status code
            - parsed_time: Parsed datetime object (or None if parsing failed)
            - service: Service object (or None if service doesn't exist)
    """
    # Validate parameters
    if not all([provider_id, service_id, appointment_time_str]):
        return False, "Missing required parameters.", status.HTTP_400_BAD_REQUEST, None, None
    
    # Parse appointment time
    parsed_time = parse_datetime(appointment_time_str)
    if not parsed_time:
        return False, "Invalid appointment_time format.", status.HTTP_400_BAD_REQUEST, None, None
    
    # 1. Check provider availability
    day_of_week = parsed_time.strftime('%A')
    availability_exists = ServiceProviderAvailability.objects.filter(
        service_provider_id=provider_id,
        day_of_week=day_of_week,
        start_time__lte=parsed_time.time(),
        end_time__gte=parsed_time.time()
    ).exists()
    
    if not availability_exists:
        return False, "Provider not available at this time.", status.HTTP_200_OK, parsed_time, None
    
    # 2. Check service exists and if provider offers this service
    try:
        # Use select_related to fetch category in the same query
        service = Service.objects.select_related('category').get(id=service_id)
    except Service.DoesNotExist:
        return False, "Service does not exist.", status.HTTP_200_OK, parsed_time, None
    
    # 3. Check buffer overlap
    buffer_time = service.buffer_time
    buffer_start = parsed_time - buffer_time
    buffer_end = parsed_time + service.duration + buffer_time
    
    # Use a more efficient query with indexing on appointment_time
    overlap = Booking.objects.filter(
        service_provider_id=provider_id,
        appointment_time__range=(buffer_start, buffer_end)
    ).exists()
    
    if overlap:
        return False, "Overlapping booking found.", status.HTTP_200_OK, parsed_time, service
    
    return True, "Time slot is available.", status.HTTP_200_OK, parsed_time, service


def format_availability_response(is_available, reason, status_code=status.HTTP_200_OK):
    """
    Format the availability check response consistently.
    
    Args:
        is_available: Boolean indicating if the time slot is available
        reason: String explaining why the slot is available/unavailable
        status_code: HTTP status code to return
        
    Returns:
        Response: DRF Response object with formatted data
    """
    return Response({"available": is_available, "reason": reason}, status=status_code)


def handle_booking_tasks(booking, logger):
    """
    Handle all post-booking tasks (email, calendar sync, invoice generation).
    Centralizes error handling for these tasks.
    
    Args:
        booking: The Booking object
        logger: Logger instance for error logging
        
    Returns:
        None
    """
    from .tasks import send_booking_confirmation_email_gmail, sync_booking_to_google_calendar, generate_invoice
    
    # Prepare booking details for email and invoice
    booking_details = {
        'user_name': booking.user.get_full_name(),
        'service_name': booking.service.name,
        'date': booking.appointment_time.date().isoformat(),
        'time': str(booking.appointment_time.time()),
    }
    
    # Send confirmation email
    try:
        send_booking_confirmation_email_gmail.delay(booking.user.email, booking_details)
    except Exception as e:
        logger.error(f"Error sending email for booking {booking.id}: {e}")
    
    # Sync with Google Calendar
    try:
        sync_booking_to_google_calendar.delay(booking.id)
    except Exception as e:
        logger.error(f"Error syncing booking {booking.id} to Google Calendar: {e}")
    
    # Generate invoice
    try:
        invoice_details = {
            **booking_details,
            'customer_name': booking.user.get_full_name(),
            'total_price': float(booking.total_price),
        }
        generate_invoice.delay(booking.id, invoice_details)
    except Exception as e:
        logger.error(f"Error generating invoice for booking {booking.id}: {e}")


def check_booking_overlap(service_provider, appointment_time, service, is_recurring=False):
    """
    Check if a booking overlaps with existing bookings considering buffer time.
    
    Args:
        service_provider: The ServiceProvider object
        appointment_time: The appointment datetime
        service: The Service object
        is_recurring: Boolean indicating if this is a recurring booking check
        
    Returns:
        bool: True if there's an overlap, False otherwise
    """
    buffer_time = service.buffer_time
    service_duration = service.duration
    
    # Calculate the start and end times with buffer
    buffer_start = appointment_time - buffer_time
    buffer_end = appointment_time + service_duration + buffer_time
    
    # More efficient query using appointment_time index
    # This query finds any booking that overlaps with our time slot
    overlapping = Booking.objects.filter(
        service_provider=service_provider,
        appointment_time__lt=buffer_end,
        appointment_time__gt=buffer_start - service_duration - buffer_time
    ).exists()
    
    return overlapping