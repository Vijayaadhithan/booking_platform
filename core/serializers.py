from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field
from drf_spectacular.types import OpenApiTypes
from .models import (
    User, Membership, ServiceProvider, Service, Booking, Review, ServiceCategory, Recurrence,GroupParticipant,GroupBooking,
    Address, Favorite, ServiceProviderAvailability, ServiceVariation,ServiceBundle,AvailabilityException
)
from .product_models import ProductCategory, Product, Order, OrderItem
from .payment_models import RazorpayPayment, MembershipSubscription
from .inventory_models import ProductVariation, InventoryTransaction, StockAlert
class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'first_name', 'last_name', 'email', 'phone_number',
                  'membership_status', 'profile_picture', 'date_joined']

class MembershipSerializer(serializers.ModelSerializer):
    class Meta:
        model = Membership
        fields = '__all__'

class ServiceProviderAvailabilitySerializer(serializers.ModelSerializer):
    class Meta:
        model = ServiceProviderAvailability
        fields = ['id', 'day_of_week', 'start_time', 'end_time']

class AvailabilityExceptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = AvailabilityException
        fields = ['id', 'date', 'reason']

class ServiceCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ServiceCategory
        fields = ['id', 'name', 'description']

class AddressSerializer(serializers.ModelSerializer):  # Add serializer for Address
    class Meta:
        model = Address
        fields = '__all__'

class ServiceVariationSerializer(serializers.ModelSerializer):
    class Meta:
        model = ServiceVariation
        fields = ['id', 'name', 'additional_price', 'additional_duration']

class ServiceSerializer(serializers.ModelSerializer):
    category = ServiceCategorySerializer()
    variations = ServiceVariationSerializer(many=True)  # Include variations
    class Meta:
        model = Service
        fields = ['id', 'name', 'description', 'category', 'base_price', 'duration', 'is_active', 'variations']

class ServiceBundleSerializer(serializers.ModelSerializer):
    services = ServiceSerializer(many=True)

    class Meta:
        model = ServiceBundle
        fields = ['id', 'name', 'description', 'services', 'price']

class ServiceProviderSerializer(serializers.ModelSerializer):
    user = UserSerializer()
    address = AddressSerializer()  # Include address details
    services_offered = ServiceSerializer(many=True)  # Include services offered
    class Meta:
        model = ServiceProvider
        fields = '__all__'

class BookingSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)  # Nested serializer for user
    service = ServiceSerializer()  # Nested serializer for service
    customer_name = serializers.SerializerMethodField()  # Add customer_name field
    service_name = serializers.SerializerMethodField()  # Add service_name field
    total_price = serializers.SerializerMethodField()  # Add total_price field

    class Meta:
        model = Booking
        fields = [
            'id',
            'user',
            'service',
            'service_provider',
            'appointment_time',
            'status',
            'payment_status',
            'customer_name',
            'service_name',
            'total_price',
            'recurrence',
            'duration',
            'notes'
        ]
        read_only_fields = ('status', 'payment_status', 'total_price')

    def validate_appointment_time(self, value):
        """Validate that appointment time is in the future"""
        if value < now():
            raise serializers.ValidationError("Appointment time must be in the future")
        return value

    def validate(self, data):
        """Validate booking data"""
        if data['service'].is_active is False:
            raise serializers.ValidationError("This service is currently not available")

        # Check if service provider offers this service
        if data['service'] not in data['service_provider'].services_offered.all():
            raise serializers.ValidationError("This service provider does not offer this service")

        return data

    def create(self, validated_data):
        """Create booking with current user"""
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)

    @extend_schema_field(str)  # Explicitly define the schema type for OpenAPI
    def get_customer_name(self, obj: Booking) -> str:
        return obj.user.get_full_name()

    @extend_schema_field(str)
    def get_service_name(self, obj: Booking) -> str:
        return obj.service.name

    @extend_schema_field(float)
    def get_total_price(self, obj: Booking) -> float:
        return obj.calculate_price() 

class BookingListSerializer(serializers.ModelSerializer):
    # Include only necessary fields for listing bookings
    class Meta:
        model = Booking
        fields = ['id', 'service_provider', 'service', 'appointment_time', 'status']  # Example fields


class ReviewSerializer(serializers.ModelSerializer):
    class Meta:
        model = Review
        fields = '__all__'
        read_only_fields = ('user', 'created_at')

class FavoriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Favorite
        fields = '__all__'

class RecurrenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Recurrence
        fields = ['frequency', 'interval', 'end_date']

class GroupParticipantSerializer(serializers.ModelSerializer):
    class Meta:
        model = GroupParticipant
        fields = ['id', 'user', 'joined_at']

class AvailabilitySerializer(serializers.Serializer):
    available = serializers.BooleanField()
    reason = serializers.CharField()
    
class GroupBookingSerializer(serializers.ModelSerializer):
    participants = GroupParticipantSerializer(many=True, read_only=True)

    class Meta:
        model = GroupBooking
        fields = ['id', 'service_provider', 'service', 'appointment_time', 
                  'max_participants', 'current_participants', 'participants']

class ProductCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductCategory
        fields = ['id', 'name', 'description']

class ProductSerializer(serializers.ModelSerializer):
    category = serializers.StringRelatedField()

    class Meta:
        model = Product
        fields = ['id', 'name', 'description', 'category', 'price', 'stock_quantity', 'sku', 'is_active']
        read_only_fields = ['created_at', 'updated_at']

class OrderItemSerializer(serializers.ModelSerializer):
    product = ProductSerializer()

    class Meta:
        model = OrderItem
        fields = ['id', 'product', 'quantity', 'price_at_time']

class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, source='orderitem_set')
    total_amount = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = ['id', 'user', 'items', 'status', 'created_at', 'total_amount']

    @extend_schema_field(OpenApiTypes.FLOAT)
    def get_total_amount(self, obj) -> float:
        #return sum(item.price * item.quantity for item in obj.orderitem_set.all())
        return sum(item.price_at_time * item.quantity for item in obj.orderitem_set.all())