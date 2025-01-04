from rest_framework import serializers
from .models import User, Membership, ServiceProvider, Service, Booking, Review, ServiceCategory, Address, Favorite

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'first_name', 'last_name', 'email', 'phone_number',
                  'membership_status', 'profile_picture', 'date_joined']

class MembershipSerializer(serializers.ModelSerializer):
    class Meta:
        model = Membership
        fields = '__all__'

class ServiceCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ServiceCategory
        fields = '__all__'

class AddressSerializer(serializers.ModelSerializer):  # Add serializer for Address
    class Meta:
        model = Address
        fields = '__all__'

class ServiceSerializer(serializers.ModelSerializer):
    category = ServiceCategorySerializer()
    class Meta:
        model = Service
        fields = '__all__'

class ServiceProviderSerializer(serializers.ModelSerializer):
    user = UserSerializer()
    address = AddressSerializer()  # Include address details
    services_offered = ServiceSerializer(many=True)  # Include services offered
    class Meta:
        model = ServiceProvider
        fields = '__all__'

class BookingSerializer(serializers.ModelSerializer):
    user = UserSerializer()  # Nested serializer for user
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
            'appointment_time',
            'status',
            'payment_status',
            'customer_name',  # Include customer_name
            'service_name',  # Include service_name
            'total_price',  # Include total_price
        ]

    def get_customer_name(self, obj):
        return f"{obj.user.first_name} {obj.user.last_name}"

    def get_service_name(self, obj):
        return obj.service.name

    def get_total_price(self, obj):
        return obj.service.price  # You might need to adjust this based on your pricing logic


class ReviewSerializer(serializers.ModelSerializer):
    class Meta:
        model = Review
        fields = '__all__'
        read_only_fields = ('user', 'created_at')

class FavoriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Favorite
        fields = '__all__'