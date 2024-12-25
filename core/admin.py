# core/admin.py
from django.contrib import admin
from .models import User, Membership, ServiceCategory, ServiceProvider, Service, Booking, Review, Address

@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ('username', 'first_name', 'last_name', 'email', 'phone_number', 'membership_status')
    list_filter = ('membership_status', 'is_staff', 'is_active')
    search_fields = ('username', 'first_name', 'last_name', 'email')

@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = ('name', 'price', 'duration', 'benefits')

@admin.register(ServiceCategory)
class ServiceCategoryAdmin(admin.ModelAdmin):
    list_display = ('name',)

@admin.register(Address)
class AddressAdmin(admin.ModelAdmin):
    list_display = ('street_address', 'city', 'state', 'zip_code', 'country')
    list_filter = ('city', 'state', 'country')
    search_fields = ('street_address', 'city', 'state', 'zip_code')

@admin.register(ServiceProvider)
class ServiceProviderAdmin(admin.ModelAdmin):
    list_display = ('user', 'service_type', 'rating', 'get_address', 'get_services_offered')
    list_filter = ('service_type', 'rating')
    search_fields = ('user__username', 'user__first_name', 'user__last_name', 'address__city')

    def get_address(self, obj):
        return obj.address
    get_address.short_description = 'Address'

    def get_services_offered(self, obj):
        return ", ".join([service.name for service in obj.services_offered.all()])
    get_services_offered.short_description = 'Services Offered'

@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'base_price', 'unit_price', 'duration')
    list_filter = ('category',)
    search_fields = ('name', 'description')

@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ('user', 'service_provider', 'service', 'appointment_time', 'status', 'payment_status')
    list_filter = ('status', 'payment_status')
    search_fields = ('user__username', 'service_provider__user__username', 'service__name')

@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ('user', 'service_provider', 'rating', 'comment', 'created_at')
    list_filter = ('rating',)
    search_fields = ('user__username', 'service_provider__user__username', 'comment')