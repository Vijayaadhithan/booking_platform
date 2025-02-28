import datetime
from decimal import Decimal
from datetime import timedelta
from django.utils import timezone
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.validators import MaxValueValidator, MinValueValidator
from django.conf import settings
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.core.cache import cache
from django.utils.timezone import now
from django.db import transaction

from rest_framework.authtoken.models import Token
from geopy.geocoders import Nominatim
from django.db.models import Avg

#from .tasks import remove_from_search_index, update_search_index


# ------------------------------------------------
# Signal: Automatically generate token for new user
# ------------------------------------------------
@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_auth_token(sender, instance=None, created=False, **kwargs):
    if created:
        Token.objects.create(user=instance)


# ------------------------------------------------
# User Model
# ------------------------------------------------
class User(AbstractUser):
    first_name = models.CharField(max_length=255, default='')
    last_name = models.CharField(max_length=255, default='')
    phone_number = models.CharField(max_length=15, unique=True, blank=True, null=True)
    membership_status = models.ForeignKey(
        'Membership',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="users"
    )
    profile_picture = models.ImageField(upload_to='profile_pictures/', blank=True, null=True)

    # Override groups and permissions to set a related_name
    groups = models.ManyToManyField(
        'auth.Group',
        related_name='core_users',  # Changed default from 'user_set'
        blank=True,
        help_text='The groups this user belongs to.',
        verbose_name='groups',
    )
    user_permissions = models.ManyToManyField(
        'auth.Permission',
        related_name='core_users',  # Changed default from 'user_set'
        blank=True,
        help_text='Specific permissions for this user.',
        verbose_name='user permissions',
    )

    def __str__(self):
        # Show a nicer representation in admin
        return f"{self.first_name} {self.last_name}"


# ------------------------------------------------
# Membership Model
# ------------------------------------------------
class Membership(models.Model):
    name = models.CharField(max_length=100)
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    duration = models.PositiveIntegerField()  # in days
    benefits = models.TextField()

    def __str__(self):
        return self.name


# ------------------------------------------------
# Address Model
# ------------------------------------------------
class Address(models.Model):
    street_address = models.CharField(max_length=255)
    city = models.CharField(max_length=255)
    state = models.CharField(max_length=255)
    zip_code = models.CharField(max_length=20)
    country = models.CharField(max_length=255)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)

    def save(self, *args, **kwargs):
        # Use geopy to get lat/long from address
        geolocator = Nominatim(user_agent="booking_platform")
        location = geolocator.geocode(
            f"{self.street_address}, {self.city}, {self.state}, {self.zip_code}, {self.country}"
        )
        if location:
            self.latitude = location.latitude
            self.longitude = location.longitude
        super().save(*args, **kwargs)

    def __str__(self):
        return (f"{self.street_address}, {self.city}, {self.state}, "
                f"{self.zip_code}, {self.country}")


# ------------------------------------------------
# ServiceProvider Model
# ------------------------------------------------
class ServiceProvider(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    service_type = models.CharField(max_length=255)  # e.g. "Plumber", "Doctor"
    address = models.ForeignKey(Address, on_delete=models.SET_NULL, null=True)
    rating = models.FloatField(default=0)
    profile_picture = models.ImageField(upload_to='provider_pictures/', blank=True, null=True)
    certifications = models.TextField(blank=True, null=True)
    services_offered = models.ManyToManyField('Service', related_name='providers')

    def __str__(self):
        return self.user.get_full_name()


# ------------------------------------------------
# ServiceProviderAvailability
# ------------------------------------------------
class ServiceProviderAvailability(models.Model):
    service_provider = models.ForeignKey(
        'ServiceProvider',
        on_delete=models.CASCADE,
        related_name='availabilities'
    )
    day_of_week = models.CharField(max_length=10)  # e.g., 'Monday'
    start_time = models.TimeField()
    end_time = models.TimeField()

    def __str__(self):
        return (f"{self.service_provider.user.get_full_name()} - {self.day_of_week} "
                f"{self.start_time} to {self.end_time}")


# ------------------------------------------------
# AvailabilityException
# ------------------------------------------------
class AvailabilityException(models.Model):
    service_provider = models.ForeignKey(
        ServiceProvider,
        on_delete=models.CASCADE,
        related_name='exceptions'
    )
    date = models.DateField()
    reason = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.service_provider.user.get_full_name()} - {self.date} (Exception)"


# ------------------------------------------------
# Recurrence
# ------------------------------------------------
class Recurrence(models.Model):
    """
    Model to store recurrence rules for bookings.
    """
    FREQUENCY_CHOICES = [
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
    ]

    booking = models.OneToOneField(
        'Booking',
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='recurrence'
    )
    group_booking = models.OneToOneField(
        'GroupBooking',
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='recurrence'
    )
    frequency = models.CharField(max_length=10, choices=FREQUENCY_CHOICES)
    interval = models.PositiveIntegerField(default=1)
    end_date = models.DateField()

    def __str__(self):
        if self.booking:
            return f"{self.booking.service.name} - {self.frequency} x {self.interval}"
        elif self.group_booking:
            return f"{self.group_booking.service.name} - {self.frequency} x {self.interval}"
        return "Recurrence rule"


# ------------------------------------------------
# ServiceCategory
# ------------------------------------------------
class ServiceCategory(models.Model):
    """
    Category to group services (e.g., 'Plumbing', 'Healthcare').
    """
    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True, null=True)

    # Added fields to match references in views.py
    is_emergency_available = models.BooleanField(default=False)
    category_type = models.CharField(max_length=50, blank=True, null=True)

    def __str__(self):
        return self.name


# ------------------------------------------------
# Service Model
# ------------------------------------------------
class Service(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField()
    category = models.ForeignKey(
        ServiceCategory,
        on_delete=models.SET_NULL,
        null=True,
        related_name="services"
    )
    base_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    unit_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    duration = models.DurationField(default=timedelta(hours=1))
    buffer_time = models.DurationField(default=timedelta(minutes=0))  # No buffer by default
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ('name', 'category')

    def __str__(self):
        return self.name

    def get_total_duration(self):
        """Calculate total duration including buffer time."""
        return self.duration + self.buffer_time

    def calculate_price(self, duration=None):
        """Calculate service price based on base price and duration."""
        if duration is None:
            duration = self.duration
        duration_hours = Decimal(duration.total_seconds()) / Decimal(3600)
        return self.base_price + (self.unit_price * duration_hours)

    def is_available(self, provider, start_time):
        """
        Check if service is available with the given provider at start_time,
        considering existing bookings that might overlap.
        """
        if not self.is_active:
            return False

        # Check if the provider offers this service
        if not provider.services_offered.filter(id=self.id).exists():
            return False

        # Overlapping check
        end_time = start_time + self.get_total_duration()
        existing_bookings = Booking.objects.filter(
            service_provider=provider,
            appointment_time__lt=end_time,
            appointment_time__gt=start_time - self.get_total_duration()
        )
        return not existing_bookings.exists()

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.unit_price < Decimal('0.00'):
            raise ValidationError({'unit_price': 'Unit price cannot be negative.'})
        if self.base_price < Decimal('0.00'):
            raise ValidationError({'base_price': 'Base price cannot be negative.'})
        if self.duration.total_seconds() <= 0:
            raise ValidationError({'duration': 'Duration must be positive.'})
        if self.buffer_time.total_seconds() < 0:
            raise ValidationError({'buffer_time': 'Buffer time cannot be negative.'})

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)


# ------------------------------------------------
# Booking Model
# ------------------------------------------------
class Booking(models.Model):
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
    time_slot = models.ForeignKey('ServiceProviderAvailability', on_delete=models.SET_NULL, null=True, blank=True)
    #completed_at = models.DateTimeField(default=timezone.now, null=True, blank=True)
    confirmation_sent = models.BooleanField(default=False)
    reminder_sent = models.BooleanField(default=False)

    duration = models.DurationField(default=None, null=True, blank=True)
    total_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.00,
        validators=[MinValueValidator(Decimal('0.00'))]
    )

    appointment_time = models.DateTimeField()
    date = models.DateField(null=True, blank=True)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    payment_status = models.CharField(
        max_length=20,
        choices=PAYMENT_STATUS_CHOICES,
        default='pending'
    )

    # Additional info
    notes = models.TextField(blank=True)
    payment_method = models.CharField(max_length=50, blank=True)
    transaction_id = models.CharField(max_length=100, blank=True)

    # Added for analytics or filtering by creation time
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['appointment_time']

    def calculate_price(self):
        base_price = Decimal(self.service.base_price)
        unit_price = Decimal(self.service.unit_price)

        # Use the booking's duration if set; otherwise the service's duration
        if self.duration is not None:
            duration = self.duration
        else:
            duration = self.service.duration if self.service.duration else timedelta(0)

        duration_hours = Decimal(duration.total_seconds()) / Decimal(3600)
        return base_price + (unit_price * duration_hours)

    def save(self, *args, **kwargs):
        if not self.duration:
            self.duration = self.service.duration  # fallback to service duration
        if not self.date:
            self.date = self.appointment_time.date()
        self.total_price = self.calculate_price()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.user.username} - {self.service.name} - {self.appointment_time}"


# ------------------------------------------------
# Review Model
# ------------------------------------------------
class Review(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    service_provider = models.ForeignKey(ServiceProvider, on_delete=models.CASCADE)
    rating = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    comment = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    booking = models.OneToOneField(Booking, on_delete=models.CASCADE, null=True, blank=True)

    class Meta:
        unique_together = ['user', 'service_provider']

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.booking:
            if self.booking.status != 'completed':
                raise ValidationError({
                    'booking': f'Cannot review a booking with status "{self.booking.status}". '
                               'Booking must be completed.'
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
        ).aggregate(Avg('rating'))['rating__avg'] or 0
        self.service_provider.rating = avg_rating
        self.service_provider.save()

    def __str__(self):
        return (f"{self.user.username} - "
                f"{self.service_provider.user.get_full_name()} - {self.rating}")


# ------------------------------------------------
# ServiceVariation Model
# ------------------------------------------------
class ServiceVariation(models.Model):
    """
    Variations of a service (e.g., extended durations, add-ons).
    """
    service = models.ForeignKey(Service, on_delete=models.CASCADE, related_name="variations")
    name = models.CharField(max_length=255)
    additional_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.0,
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    additional_duration = models.DurationField(default=timedelta(0))

    def __str__(self):
        return f"{self.service.name} - {self.name}"


# ------------------------------------------------
# ServiceBundle Model
# ------------------------------------------------
class ServiceBundle(models.Model):
    """
    A package of multiple services.
    """
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    services = models.ManyToManyField(Service, related_name="bundles")
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))]
    )

    def __str__(self):
        return self.name


# ------------------------------------------------
# GroupBooking Model
# ------------------------------------------------
class GroupBooking(models.Model):
    service_provider = models.ForeignKey(
        ServiceProvider,
        on_delete=models.CASCADE,
        related_name="group_bookings"
    )
    service = models.ForeignKey(Service, on_delete=models.CASCADE, related_name="group_bookings")
    appointment_time = models.DateTimeField()
    max_participants = models.PositiveIntegerField()
    current_participants = models.PositiveIntegerField(default=0)

    def __str__(self):
        return (f"{self.service.name} - {self.appointment_time} "
                f"({self.current_participants}/{self.max_participants})")


# ------------------------------------------------
# GroupParticipant Model
# ------------------------------------------------
class GroupParticipant(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="group_participations")
    group_booking = models.ForeignKey(GroupBooking, on_delete=models.CASCADE, related_name="participants")
    joined_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.get_full_name()} - {self.group_booking.service.name}"


# ------------------------------------------------
# WaitingList Model
# ------------------------------------------------
class WaitingList(models.Model):
    service = models.ForeignKey(Service, on_delete=models.CASCADE, related_name='waiting_list')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Waiting: {self.user.username} for {self.service.name}"


# ------------------------------------------------
# Favorite Model
# ------------------------------------------------
class Favorite(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="favorites")
    service = models.ForeignKey(Service, on_delete=models.CASCADE, related_name="favorited_by")

    class Meta:
        unique_together = ('user', 'service')

    def __str__(self):
        return f"{self.user.username} - {self.service.name}"


# ------------------------------------------------
# Signals for Elasticsearch Indexing
# ------------------------------------------------
@receiver(post_save, sender=Service)
def trigger_search_index_update(sender, instance, **kwargs):
    """
    Signal to trigger the search index update task when a Service is saved.
    """
    from .tasks import update_search_index
    transaction.on_commit(lambda: update_search_index.delay(instance.id))


@receiver(post_delete, sender=Service)
def trigger_search_index_deletion(sender, instance, **kwargs):
    """
    Signal to trigger search index cleanup when a Service is deleted.
    """
    from .tasks import remove_from_search_index
    remove_from_search_index.delay(instance.id)


@receiver([post_save, post_delete], sender=ServiceProviderAvailability)
def clear_availability_cache(sender, instance, **kwargs):
    """
    Clear the cached availability data when it's created/updated/deleted.
    """
    cache_key = f"service_provider_{instance.service_provider_id}_availability"
    cache.delete(cache_key)


@receiver(post_save, sender=Review)
def update_provider_rating(sender, instance, created, **kwargs):
    """
    Redundant if we're already updating on `save()`, but if needed:
    """
    if created:
        provider = instance.service_provider
        avg_rating = Review.objects.filter(
            service_provider=provider
        ).aggregate(avg=Avg('rating'))['avg'] or 0
        provider.rating = avg_rating
        provider.save()
