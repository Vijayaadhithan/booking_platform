from rest_framework.viewsets import ModelViewSet
from rest_framework.permissions import IsAuthenticatedOrReadOnly, IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from .models import User, Membership, ServiceProvider, Service, Booking, Review, ServiceCategory, Address
from .serializers import (
    UserSerializer, MembershipSerializer, ServiceProviderSerializer,
    ServiceSerializer, BookingSerializer, ReviewSerializer, ServiceCategorySerializer
)
from .permissions import IsOwnerOrReadOnly  # Assuming you create this permission
from elasticsearch_dsl.connections import connections
from elasticsearch_dsl import Search, Q
from .documents import ServiceDocument

# Connect to Elasticsearch
connections.create_connection(hosts=[{'host': 'localhost', 'port': 9200, 'scheme': 'http'}], timeout=20)

class UserViewSet(ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]  # AllowAny for registration?

class MembershipViewSet(ModelViewSet):
    queryset = Membership.objects.all()
    serializer_class = MembershipSerializer
    permission_classes = [IsAuthenticated]

class ServiceCategoryViewSet(ModelViewSet):
    queryset = ServiceCategory.objects.all()
    serializer_class = ServiceCategorySerializer
    permission_classes = [IsAuthenticatedOrReadOnly]

class ServiceProviderViewSet(ModelViewSet):
    queryset = ServiceProvider.objects.all().select_related('user', 'address')  # Include address
    serializer_class = ServiceProviderSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['service_type', 'address__city', 'rating']  # Filter by address fields

class ServiceViewSet(ModelViewSet):
    queryset = Service.objects.all().select_related('category')  # Optimize query
    serializer_class = ServiceSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['name', 'category', 'base_price', 'unit_price']

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        # Elasticsearch search
        q = request.GET.get('q')
        if q:
            search = ServiceDocument.search().query(
                Q("multi_match", query=q, fields=['name', 'description'])
            )
            search = search.execute()
            queryset = [Service.objects.get(pk=hit.meta.id) for hit in search]
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

class BookingViewSet(ModelViewSet):
    queryset = Booking.objects.all().select_related(
        'user', 'service_provider', 'service', 'service_provider__address'
    )  # Include address
    serializer_class = BookingSerializer
    permission_classes = [IsAuthenticated, IsOwnerOrReadOnly]

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

class ReviewViewSet(ModelViewSet):
    queryset = Review.objects.all().select_related('user', 'service_provider')
    serializer_class = ReviewSerializer
    permission_classes = [IsAuthenticated, IsOwnerOrReadOnly]

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)