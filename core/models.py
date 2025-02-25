from django.db import models
from geopy.geocoders import Nominatim
from django.contrib.auth.models import AbstractUser
from django.core.validators import MaxValueValidator, MinValueValidator
from django.conf import settings
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from rest_framework.authtoken.models import Token
from django.core.cache import cache
from decimal import Decimal
from django.utils.timezone import now
from django.db.models import Avg
import datetime
from django.db import transaction
from datetime import timedelta
from .tasks import remove_from_search_index, update_search_index
min_value=Decimal("0.0")
# Automatically generate token for every new user
@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_auth_token(sender, instance=None, created=False, **kwargs):
    if created:
        Token.objects.create(user=instance)


# User Model
class User(AbstractUser):
    first_name = models.CharField(max_length=255, default='')
    last_name = models.CharField(max_length=255, default='')
    phone_number = models.CharField(max_length=15, unique=True, blank=True, null=True)
    membership_status = models.ForeignKey('Membership', on_delete=models.SET_NULL, null=True, blank=True, related_name="users")  # Add related_name
    profile_picture = models.ImageField(upload_to='profile_pictures/', blank=True, null=True)

    groups = models.ManyToManyField(
        'auth.Group',
        related_name='core_users',  # Add related_name here
        blank=True,
        help_text='The groups this user belongs to. A user will get all permissions granted to each of their groups.',
        verbose_name='groups',
    )
    user_permissions = models.ManyToManyField(
        'auth.Permission',
        related_name='core_users',  # Add related_name here
        blank=True,
        help_text='Specific permissions for this user.',
        verbose_name='user permissions',
    )

    def __str__(self):
        return f"{self.first_name} {self.last_name}"


# Membership Model
class Membership(models.Model):
    name = models.CharField(max_length=100)
    price = models.DecimalField(max_digits=10, decimal_places=2,validators=[MinValueValidator(Decimal('0.00'))])
    duration = models.PositiveIntegerField()  # in days
    benefits = models.TextField()

    def __str__(self):
        return self.name

class Address(models.Model):
    street_address = models.CharField(max_length=255)
    city = models.CharField(max_length=255)
    state = models.CharField(max_length=255)
    zip_code = models.CharField(max_length=20)
    country = models.CharField(max_length=255)
    latitude = models.FloatField(null=True, blank=True)  # Add latitude field
    longitude = models.FloatField(null=True, blank=True)  # Add longitude field

    def save(self, *args, **kwargs):
        geolocator = Nominatim(user_agent="booking_platform")
        location = geolocator.geocode(f"{self.street_address}, {self.city}, {self.state}, {self.zip_code}, {self.country}")
        if location:
            self.latitude = location.latitude
            self.longitude = location.longitude
        super(Address, self).save(*args, **kwargs)

    def __str__(self):
        return f"{self.street_address}, {self.city}, {self.state}, {self.zip_code}, {self.country}"

class ServiceProvider(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    service_type = models.CharField(max_length=255)  # Consider using ServiceCategory as a ForeignKey
    address = models.ForeignKey(Address, on_delete=models.SET_NULL, null=True)  # Use Address model
    #availability = models.JSONField()  # Consider a more robust solution
    rating = models.FloatField(default=0)
    profile_picture = models.ImageField(upload_to='provider_pictures/', blank=True, null=True)
    certifications = models.TextField(blank=True, null=True)
    services_offered = models.ManyToManyField(
        'Service', related_name='providers'
    )  # Add services_offered

    def __str__(self):
        return self.user.get_full_name()


class ServiceProviderAvailability(models.Model):
    service_provider = models.ForeignKey('ServiceProvider', on_delete=models.CASCADE, related_name='availabilities')
    day_of_week = models.CharField(max_length=10)  # e.g., 'Monday', 'Tuesday'
    start_time = models.TimeField()
    end_time = models.TimeField()

    def __str__(self):
        return f"{self.service_provider.user.get_full_name()} - {self.day_of_week} {self.start_time} to {self.end_time}"

class AvailabilityException(models.Model):
    service_provider = models.ForeignKey(ServiceProvider, on_delete=models.CASCADE, related_name='exceptions')
    date = models.DateField()
    reason = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.service_provider.user.get_full_name()} - {self.date} (Exception)"

class Recurrence(models.Model):
    """
    Model to store recurrence rules for bookings.
    """
    FREQUENCY_CHOICES = [
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
    ]

    booking = models.OneToOneField('Booking', null=True, blank=True, on_delete=models.CASCADE, related_name='recurrence')
    group_booking = models.OneToOneField('GroupBooking', null=True, blank=True, on_delete=models.CASCADE, related_name='recurrence')
    frequency = models.CharField(max_length=10, choices=FREQUENCY_CHOICES)
    interval = models.PositiveIntegerField(default=1)
    end_date = models.DateField()

    def __str__(self):
        return f"{self.booking.service.name} - {self.frequency} x {self.interval}"

class ServiceCategory(models.Model):
    """
    Category to group services.
    """
    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.name

# Service Model
class Service(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField()
    category = models.ForeignKey(ServiceCategory, on_delete=models.SET_NULL, null=True, related_name="services")
    base_price = models.DecimalField(
        max_digits=10, decimal_places=2, 
        validators=[MinValueValidator(Decimal('0.00'))]  # Ensure correct decimal format
    )
    duration = models.DurationField()
    unit_price = models.DecimalField(max_digits=10, decimal_places=2,validators=[MinValueValidator(Decimal('0.00'))])
    duration = models.DurationField(default=datetime.timedelta(hours=1))
    buffer_time = models.DurationField(default=timedelta(minutes=0))  # Default no buffer
    is_active = models.BooleanField(default=True) 

    class Meta:
        unique_together = ('name', 'category')
    
    def __str__(self):
        return self.name
    
# Booking Model
class Booking(models.Model):
    # Define choices as class-level variables
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('cancelled', 'Cancelled'),
        ('completed', 'Completed'),
    ]
    PAYMENT_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('paid', 'Paid'),
        ('refunded', 'Refunded'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="bookings")
    service_provider = models.ForeignKey(ServiceProvider, on_delete=models.CASCADE)
    service = models.ForeignKey(Service, on_delete=models.CASCADE, related_name="bookings")
    time_slot = models.ForeignKey(ServiceProviderAvailability, on_delete=models.SET_NULL, null=True, blank=True)  # Add time_slot field
    confirmation_sent = models.BooleanField(default=False)
    reminder_sent = models.BooleanField(default=False)
    duration = models.DurationField(default=None, null=True, blank=True)
    total_price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00,validators=[MinValueValidator(Decimal('0.00'))])
    # Date/Time fields
    appointment_time = models.DateTimeField()
    date = models.DateField(null=True, blank=True)
    class Meta:
        ordering = ['appointment_time'] 

    # Booking & Payment statuses
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending'
    )
    payment_status = models.CharField(
        max_length=20,
        choices=PAYMENT_STATUS_CHOICES,
        default='pending'
    )

    # Additional info
    notes = models.TextField(blank=True)
    payment_method = models.CharField(max_length=50, blank=True)
    transaction_id = models.CharField(max_length=100, blank=True)

    def calculate_price(self):  # Add price calculation method
        base_price = Decimal(self.service.base_price)
        unit_price = Decimal(self.service.unit_price) 
        # Use booking duration if available; otherwise, fall back to service duration
        if self.duration is not None:
            duration = self.duration
        elif self.service.duration is not None:
            duration = self.service.duration
        else:
        # Fallback to zero duration if neither is available
            duration = timedelta(0)
        # Convert duration to hours
        duration_hours = Decimal(duration.total_seconds()) / Decimal(3600)
        total_price = base_price + (unit_price * duration_hours)
        return total_price

    def save(self, *args, **kwargs):
        if not self.duration:
            self.duration = self.service.duration  # Assign service duration
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.user.username} - {self.service.name} - {self.appointment_time}"

    
# Review Model
class Review(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    service_provider = models.ForeignKey(ServiceProvider, on_delete=models.CASCADE)
    rating = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    comment = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    booking = models.OneToOneField(Booking, on_delete=models.CASCADE, null=True, blank=True)

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.booking:
            if self.booking.status != 'completed':
                raise ValidationError({
                    'booking': f'Cannot review a booking with status "{self.booking.status}". Booking must be completed.'
                })
            if self.user != self.booking.user:
                raise ValidationError({
                    'user': 'Only the booking user can create a review.'
                })

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)
        
        # Update service provider rating
        avg_rating = Review.objects.filter(
            service_provider=self.service_provider
        ).aggregate(Avg('rating'))['rating__avg']
        
        self.service_provider.rating = avg_rating or 0
        self.service_provider.save()

    class Meta:
        unique_together = ['user', 'service_provider']

    def __str__(self):
        return f"{self.user.username} - {self.service_provider.user.get_full_name()} - {self.rating}"

class ServiceVariation(models.Model):
    """
    Represents variations of a service, e.g., different durations or add-ons.
    """
    service = models.ForeignKey(Service, on_delete=models.CASCADE, related_name="variations")
    name = models.CharField(max_length=255)  # Variation name
    additional_price = models.DecimalField(max_digits=10, decimal_places=2, default=0.0, validators=[MinValueValidator(Decimal('0.00'))])
    additional_duration = models.DurationField(default=0)

    def __str__(self):
        return f"{self.service.name} - {self.name}"

class ServiceBundle(models.Model):
    """
    Represents a package of multiple services.
    """
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    services = models.ManyToManyField(Service, related_name="bundles")
    price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal('0.00'))])

    def __str__(self):
        return self.name

class GroupBooking(models.Model):
    """
    Represents a group booking that can include multiple users.
    """
    service_provider = models.ForeignKey(ServiceProvider, on_delete=models.CASCADE, related_name="group_bookings")
    service = models.ForeignKey(Service, on_delete=models.CASCADE, related_name="group_bookings")
    appointment_time = models.DateTimeField()
    max_participants = models.PositiveIntegerField()  # Max participants for the group booking
    current_participants = models.PositiveIntegerField(default=0)  # Current number of participants

    def __str__(self):
        return f"{self.service.name} - {self.appointment_time} ({self.current_participants}/{self.max_participants})"


class GroupParticipant(models.Model):
    """
    Represents a participant in a group booking.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="group_participations")
    group_booking = models.ForeignKey(GroupBooking, on_delete=models.CASCADE, related_name="participants")
    joined_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.get_full_name()} - {self.group_booking.service.name}"

class WaitingList(models.Model):
    service = models.ForeignKey(Service, on_delete=models.CASCADE, related_name='waiting_list')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)


class Favorite(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="favorites")
    service = models.ForeignKey(Service, on_delete=models.CASCADE, related_name="favorited_by")

    class Meta:
        unique_together = ('user', 'service')

    def __str__(self):
        return f"{self.user.username} - {self.service.name}"

@receiver(post_save, sender=Service)
def trigger_search_index_update(sender, instance, **kwargs):
    """
    Signal to trigger the search index update task when a Service is saved.
    """
    transaction.on_commit(lambda: update_search_index.delay(instance.id))

@receiver(post_delete, sender=Service)
def trigger_search_index_deletion(sender, instance, **kwargs):
    """
    Signal to trigger the search index cleanup task when a Service is deleted.
    """
    remove_from_search_index.delay(instance.id)

@receiver([post_save, post_delete], sender=ServiceProviderAvailability)
def clear_availability_cache(sender, instance, **kwargs):
    """
    Clear the cached availability data when it is updated or deleted.
    """
    cache_key = f"service_provider_{instance.service_provider_id}_availability"
    cache.delete(cache_key)

@receiver(post_save, sender=Review)
def update_provider_rating(sender, instance, created, **kwargs):
    if created:
        provider = instance.service_provider
        avg_rating = Review.objects.filter(service_provider=provider).aggregate(avg=Avg('rating'))['avg'] or 0
        provider.rating = avg_rating
        provider.save()