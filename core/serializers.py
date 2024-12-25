from rest_framework import serializers
from .models import User, Membership, ServiceProvider, Service, Booking, Review, ServiceCategory, Address

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
    class Meta:
        model = Booking
        fields = '__all__'
        read_only_fields = ('user',)  # Prevent user from modifying the user field

class ReviewSerializer(serializers.ModelSerializer):
    class Meta:
        model = Review
        fields = '__all__'
        read_only_fields = ('user', 'created_at')