# core/admin.py
from django.contrib import admin
from .models import (
    User, Membership, ServiceCategory, ServiceProvider, Service, Booking, Review, 
    Address, ServiceProviderAvailability, ServiceVariation, ServiceBundle, 
    GroupBooking, GroupParticipant, WaitingList, Favorite, AvailabilityException
)
from .product_models import ProductCategory, Product, Order, OrderItem
from .payment_models import RazorpayPayment, MembershipSubscription, PaymentWebhookLog
from .inventory_models import ProductVariation, InventoryTransaction, StockAlert

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

@admin.register(ServiceVariation)
class ServiceVariationAdmin(admin.ModelAdmin):
    list_display = ('service', 'name', 'additional_price', 'additional_duration')
    list_filter = ('service',)

@admin.register(ServiceBundle)
class ServiceBundleAdmin(admin.ModelAdmin):
    list_display = ('name', 'price')
    filter_horizontal = ('services',)

@admin.register(GroupBooking)
class GroupBookingAdmin(admin.ModelAdmin):
    list_display = ('service', 'appointment_time', 'max_participants', 'current_participants')
    list_filter = ('service', 'appointment_time')

@admin.register(GroupParticipant)
class GroupParticipantAdmin(admin.ModelAdmin):
    list_display = ('user', 'group_booking', 'joined_at')
    list_filter = ('group_booking', 'joined_at')

@admin.register(WaitingList)
class WaitingListAdmin(admin.ModelAdmin):
    list_display = ('user', 'service', 'created_at')
    list_filter = ('service', 'created_at')

@admin.register(Favorite)
class FavoriteAdmin(admin.ModelAdmin):
    list_display = ('user', 'service')
    list_filter = ('service',)

@admin.register(AvailabilityException)
class AvailabilityExceptionAdmin(admin.ModelAdmin):
    list_display = ('service_provider', 'date', 'reason')
    list_filter = ('date',)

@admin.register(ServiceProviderAvailability)
class ServiceProviderAvailabilityAdmin(admin.ModelAdmin):
    list_display = ('service_provider', 'day_of_week', 'start_time', 'end_time')
    list_filter = ('day_of_week',)

# Product Models Registration
@admin.register(ProductCategory)
class ProductCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'description')
    search_fields = ('name',)

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'price', 'stock_quantity', 'is_active')
    list_filter = ('category', 'is_active')
    search_fields = ('name', 'description')

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('user', 'status', 'total_amount', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('user__username',)

@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ('order', 'product', 'quantity', 'price_at_time')
    list_filter = ('order', 'product')

# Inventory Models Registration
@admin.register(ProductVariation)
class ProductVariationAdmin(admin.ModelAdmin):
    list_display = ('product', 'name', 'value', 'price_adjustment', 'stock_quantity', 'is_active')
    list_filter = ('product', 'is_active')
    search_fields = ('name', 'value')

@admin.register(InventoryTransaction)
class InventoryTransactionAdmin(admin.ModelAdmin):
    list_display = ('product', 'transaction_type', 'quantity', 'created_at')
    list_filter = ('transaction_type', 'created_at')
    search_fields = ('product__name', 'reference_number')

@admin.register(StockAlert)
class StockAlertAdmin(admin.ModelAdmin):
    list_display = ('product', 'threshold', 'is_active', 'last_triggered')
    list_filter = ('is_active', 'last_triggered')

# Payment Models Registration
@admin.register(RazorpayPayment)
class RazorpayPaymentAdmin(admin.ModelAdmin):
    list_display = ('user', 'order_id', 'amount', 'status', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('user__username', 'order_id', 'payment_id')

@admin.register(MembershipSubscription)
class MembershipSubscriptionAdmin(admin.ModelAdmin):
    list_display = ('user', 'membership', 'status', 'start_date', 'end_date', 'is_trial')
    list_filter = ('status', 'is_trial', 'auto_renew')
    search_fields = ('user__username',)

@admin.register(PaymentWebhookLog)
class PaymentWebhookLogAdmin(admin.ModelAdmin):
    list_display = ('event_id', 'event_type', 'created_at')
    list_filter = ('event_type', 'created_at')
    search_fields = ('event_id', 'event_type')