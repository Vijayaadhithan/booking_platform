from rest_framework.viewsets import ModelViewSet
from rest_framework.permissions import IsAuthenticatedOrReadOnly, IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from .models import User, Membership, ServiceProvider, Service, Booking, Review, ServiceCategory, Address, Favorite, ServiceProviderAvailability
from .serializers import (
    UserSerializer, MembershipSerializer, ServiceProviderSerializer, AddressSerializer,
    ServiceSerializer, BookingSerializer, ReviewSerializer, ServiceCategorySerializer, FavoriteSerializer, ServiceProviderAvailabilitySerializer
)
from celery.exceptions import CeleryError
from geopy.distance import distance
from .permissions import IsOwnerOrReadOnly, IsProvider # Assuming you create this permission
from elasticsearch_dsl.connections import connections
from elasticsearch_dsl import Search, Q as ES_Q
from .documents import ServiceDocument
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes, action
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from datetime import datetime, timedelta
from rest_framework import viewsets, generics, status
from rest_framework.authtoken.views import ObtainAuthToken
from rest_framework.authtoken.models import Token
from rest_framework.views import APIView
from django_elasticsearch_dsl_drf.filter_backends import (
    FilteringFilterBackend,
    OrderingFilterBackend,
    SearchFilterBackend,
)
from rest_framework import viewsets, generics, status
from rest_framework.versioning import NamespaceVersioning 
from django_elasticsearch_dsl_drf.viewsets import DocumentViewSet
from django_elasticsearch_dsl_drf.filter_backends import (
    FilteringFilterBackend,
    CompoundSearchFilterBackend
)
from .tasks import send_booking_confirmation_email_gmail
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

class APIv1NamespaceVersioning(NamespaceVersioning):
    default_version = 'v1'
    allowed_versions = ['v1']
    namespace = 'api/v1'  # URL namespace for v1

class ServiceProviderViewSet(ModelViewSet):
    queryset = ServiceProvider.objects.all().select_related('user', 'address')  # Include address
    serializer_class = ServiceProviderSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['service_type', 'address__city', 'rating']  # Filter by address fields

    def get_queryset(self):
        queryset = super().get_queryset()
        # Filter by distance (example - requires latitude and longitude in request)
        latitude = self.request.query_params.get('latitude')
        longitude = self.request.query_params.get('longitude')
        radius = self.request.query_params.get('radius')
        if latitude and longitude and radius:
            user_location = (float(latitude), float(longitude))
            radius = float(radius)
            queryset = [
                sp for sp in queryset
                if sp.address and distance(user_location, (sp.address.latitude, sp.address.longitude)).km <= radius
            ]
        # Filter by service offered
        service_id = self.request.query_params.get('service_id')
        if service_id:
            queryset = queryset.filter(services_offered=service_id)
        return queryset

class ServiceViewSet(ModelViewSet):
    queryset = Service.objects.all().select_related('category')  # Optimize query
    document = ServiceDocument
    serializer_class = ServiceSerializer
    permission_classes = [IsProvider]
    filter_backends = [
        DjangoFilterBackend,
        FilteringFilterBackend,
        OrderingFilterBackend,
        SearchFilterBackend,
    ]
    filterset_fields = ['name', 'category', 'base_price', 'unit_price']
    pagination_class = PageNumberPagination  # Add pagination

    # Define search fields
    search_fields = (
        'name',
        'description',
        'category.name',  # Search in related category name
    )
    # Define filtering fields
    filter_fields = {
        'name': 'name',
        'description': 'description',
        'category': 'category.name',
        'base_price': {
            'field': 'base_price',
            'lookups': [
                'gte',  # greater than or equal to
                'lte',  # less than or equal to
                'gt',   # greater than 
                'lt',   # less than
            ],
        },
    }
    # Define ordering fields
    ordering_fields = {
        'name': 'name',
        'base_price': 'base_price',
    }
    # Specify default ordering
    ordering = ('name',) 

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        # Elasticsearch search
        q = request.GET.get('q')
        if q:
            search = ServiceDocument.search().query(
                ES_Q("multi_match", query=q, fields=['name', 'description'])
            )
            search = search.execute()
            queryset = [Service.objects.get(pk=hit.meta.id) for hit in search]
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
    
    def get_queryset(self):
        queryset = super().get_queryset()
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) |
                Q(description__icontains=search)
            )
        return queryset

class BookingViewSet(ModelViewSet):
    queryset = Booking.objects.all().select_related(
        'user', 'service_provider', 'service', 'service_provider__address'
    )  # Include address
    serializer_class = BookingSerializer
    permission_classes = [IsAuthenticated, IsOwnerOrReadOnly]
    versioning_class = APIv1NamespaceVersioning  # Add versioning class

    def get_queryset(self):
        queryset = super().get_queryset()
        if not self.request.user.is_staff:  # If not staff, only show user's bookings
            queryset = queryset.filter(user=self.request.user)
        
        # Add filtering for status and date range
        status = self.request.query_params.get('status')
        if status:
            queryset = queryset.filter(status=status)

        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')
        if start_date and end_date:
            queryset = queryset.filter(date__range=[start_date, end_date])

        # Add search and filter_by parameters
        search = self.request.query_params.get('search')
        filter_by = self.request.query_params.get('filter')
        if search:
            queryset = queryset.filter(
                Q(user__first_name__icontains=search) |
                Q(user__last_name__icontains=search) |
                Q(service__name__icontains=search)
            )
        if filter_by:
            queryset = queryset.filter(status=filter_by)

        return queryset

    def perform_create(self, serializer):
        booking = serializer.save(user=self.request.user)

        # Prepare email details
        booking_details = {
            'user_name': booking.user.get_full_name(),
            'service_name': booking.service.name,
            'date': booking.appointment_time.date(),
            'time': booking.appointment_time.time(),
        }   
        # Trigger the Celery task to send an email
        try:
            send_booking_confirmation_email_gmail.delay(booking.user.email, booking_details)
        except CeleryError as e:
            # Log the error or handle it as needed
            print(f"Error sending email: {e}")
        
    # Add actions for updating and canceling bookings
    @action(detail=True, methods=['patch'])
    def update_booking(self, request, pk=None):
        booking = self.get_object()
        serializer = self.get_serializer(booking, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    @action(detail=True, methods=['patch'])
    def cancel_booking(self, request, pk=None):
        booking = self.get_object()
        booking.status = 'canceled'  # Assuming 'status' is a field in the Booking model
        booking.save()
        return Response({'status': 'booking canceled'})

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)
    
class ReviewViewSet(ModelViewSet):
    queryset = Review.objects.all().select_related('user', 'service_provider')
    serializer_class = ReviewSerializer
    permission_classes = [IsAuthenticated, IsOwnerOrReadOnly]

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

class UserRegistrationView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = UserSerializer

class UserLoginView(ObtainAuthToken):
    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(data=request.data,
                                           context={'request': request})
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']
        token, created = Token.objects.get_or_create(user=user)
        return Response({
            'token': token.key,
            'user_id': user.pk,
            'email': user.email
        })

class UserLogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        request.user.auth_token.delete()
        return Response(status=status.HTTP_200_OK)

# Service Views
@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def services(request):
    if request.method == 'GET':
        services = Service.objects.all()
        serializer = ServiceSerializer(services, many=True)
        return Response(serializer.data)
    elif request.method == 'POST':
        serializer = ServiceSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(provider=request.user)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

# Booking Views
@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def bookings(request):
    if request.method == 'GET':
        user_bookings = Booking.objects.filter(user=request.user)
        serializer = BookingSerializer(user_bookings, many=True)
        return Response(serializer.data)
    elif request.method == 'POST':
        serializer = BookingSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(user=request.user)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

# Favorites Views
@api_view(['GET', 'POST', 'DELETE'])
@permission_classes([IsAuthenticated])
def favorites(request):
    if request.method == 'GET':
        user_favorites = Favorite.objects.filter(user=request.user)
        serializer = FavoriteSerializer(user_favorites, many=True)
        return Response(serializer.data)
    elif request.method == 'POST':
        serializer = FavoriteSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(user=request.user)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    elif request.method == 'DELETE':
        try:
            favorite = Favorite.objects.get(user=request.user, service=request.data['service'])
            favorite.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Favorite.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)
        
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def user_metrics(request):
    user = request.user
    
    # Calculate total spend
    total_spend = sum(booking.price for booking in Booking.objects.filter(user=user, payment_status='paid'))
    
    # Calculate total bookings
    total_bookings = Booking.objects.filter(user=user).count()
    
    # Calculate membership duration (in days)
    duration = (datetime.now() - user.date_joined).days if user.date_joined else 0
    
    # Generate activity graph data (example)
    today = datetime.now()
    one_month_ago = today - timedelta(days=30)
    bookings_last_month = Booking.objects.filter(
        user=user,
        appointment_time__gte=one_month_ago,
        appointment_time__lte=today
    )
    activity_graph = {
        'labels': [day.strftime('%Y-%m-%d') for day in (today - timedelta(days=x) for x in range(30, -1, -1))],  # Last 30 days
        'values': [bookings_last_month.filter(appointment_time__date=day).count() for day in (today - timedelta(days=x) for x in range(30, -1, -1))]
    }
    
    # Favorite Services
    favorite_services = [favorite.service for favorite in Favorite.objects.filter(user=user)]
    
    metrics = {
        'totalSpend': total_spend,
        'totalBookings': total_bookings,
        'duration': duration,
        'activityGraph': activity_graph,
        'favoriteServices': favorite_services,  # Include favorite services
    }
    return Response(metrics)

@api_view(['GET'])
@permission_classes([IsProvider])
def provider_metrics(request):
    provider = request.user.serviceprovider  # Access the ServiceProvider instance
    
    # Calculate total revenue
    total_revenue = sum(booking.price for booking in Booking.objects.filter(
        service_provider=provider,
        payment_status='paid'
    ))
    
    # Calculate total bookings
    total_bookings = Booking.objects.filter(service_provider=provider).count()
    
    # Calculate the number of active services
    active_services = provider.services_offered.count()  # Access the services offered
    
    metrics = {
        'revenue': total_revenue,
        'totalBookings': total_bookings,
        'activeServices': active_services
    }
    return Response(metrics)