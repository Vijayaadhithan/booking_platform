from django.db import models

# User Model
class User(models.Model):
    username = models.CharField(max_length=255, unique=True)
    email = models.EmailField(unique=True)
    phone_number = models.CharField(max_length=15, unique=True)
    password = models.CharField(max_length=255)
    membership_status = models.ForeignKey('Membership', on_delete=models.SET_NULL, null=True, blank=True)
    profile_picture = models.ImageField(upload_to='profile_pictures/', blank=True, null=True)
    date_joined = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.username

# Membership Model
class Membership(models.Model):
    name = models.CharField(max_length=100)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    duration = models.PositiveIntegerField()  # in days
    benefits = models.TextField()

    def __str__(self):
        return self.name

# Service Provider Model
class ServiceProvider(models.Model):
    name = models.CharField(max_length=255)
    service_type = models.CharField(max_length=255)
    location = models.CharField(max_length=255)
    availability = models.JSONField()
    rating = models.FloatField(default=0)
    profile_picture = models.ImageField(upload_to='provider_pictures/', blank=True, null=True)
    certifications = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.name

# Service Model
class Service(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField()
    base_price = models.DecimalField(max_digits=10, decimal_places=2)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return self.name
