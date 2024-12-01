from rest_framework.viewsets import ModelViewSet
from .models import User, Membership, ServiceProvider, Service
from .serializers import UserSerializer, MembershipSerializer, ServiceProviderSerializer, ServiceSerializer

class UserViewSet(ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer

class MembershipViewSet(ModelViewSet):
    queryset = Membership.objects.all()
    serializer_class = MembershipSerializer

class ServiceProviderViewSet(ModelViewSet):
    queryset = ServiceProvider.objects.all()
    serializer_class = ServiceProviderSerializer

class ServiceViewSet(ModelViewSet):
    queryset = Service.objects.all()
    serializer_class = ServiceSerializer

