from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.validators import MaxValueValidator, MinValueValidator
from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver
from rest_framework.authtoken.models import Token
import datetime

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
    price = models.DecimalField(max_digits=10, decimal_places=2)
    duration = models.PositiveIntegerField()  # in days
    benefits = models.TextField()

    def __str__(self):
        return self.name

class Address(models.Model):  # Add Address model
    street_address = models.CharField(max_length=255)
    city = models.CharField(max_length=255)
    state = models.CharField(max_length=255)
    zip_code = models.CharField(max_length=20)
    country = models.CharField(max_length=255)

    def __str__(self):
        return f"{self.street_address}, {self.city}, {self.state}, {self.zip_code}, {self.country}"

class ServiceProvider(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    service_type = models.CharField(max_length=255)  # Consider using ServiceCategory as a ForeignKey
    address = models.ForeignKey(Address, on_delete=models.SET_NULL, null=True)  # Use Address model
    availability = models.JSONField()  # Consider a more robust solution
    rating = models.FloatField(default=0)
    profile_picture = models.ImageField(upload_to='provider_pictures/', blank=True, null=True)
    certifications = models.TextField(blank=True, null=True)
    services_offered = models.ManyToManyField(
        'Service', related_name='providers'
    )  # Add services_offered

    def __str__(self):
        return self.user.get_full_name()


class ServiceCategory(models.Model):
    name = models.CharField(max_length=255)

    def __str__(self):
        return self.name

# Service Model
class Service(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField()
    category = models.ForeignKey(ServiceCategory, on_delete=models.SET_NULL, null=True)
    base_price = models.DecimalField(max_digits=10, decimal_places=2)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    duration = models.DurationField(default=datetime.timedelta(hours=1))

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

    # Date/Time fields
    appointment_time = models.DateTimeField()
    date = models.DateField(null=True, blank=True)

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

    def __str__(self):
        return f"{self.user.username} - {self.service.name} - {self.appointment_time}"

    
# Review Model
class Review(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    service_provider = models.ForeignKey(ServiceProvider, on_delete=models.CASCADE)
    rating = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    comment = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['user', 'service_provider']

    def __str__(self):
        return f"{self.user.username} - {self.service_provider.user.get_full_name()} - {self.rating}"

class Favorite(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="favorites")
    service = models.ForeignKey(Service, on_delete=models.CASCADE, related_name="favorited_by")

    class Meta:
        unique_together = ('user', 'service')

    def __str__(self):
        return f"{self.user.username} - {self.service.name}"