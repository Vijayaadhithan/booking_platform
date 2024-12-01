from django.contrib import admin
from .models import User, Membership, ServiceProvider, Service

@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ('username', 'email', 'phone_number', 'date_joined')
    search_fields = ('username', 'email', 'phone_number')

@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = ('name', 'price', 'duration')

@admin.register(ServiceProvider)
class ServiceProviderAdmin(admin.ModelAdmin):
    list_display = ('name', 'service_type', 'location', 'rating')
    search_fields = ('name', 'service_type', 'location')

@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ('name', 'base_price', 'unit_price')
    search_fields = ('name',)
