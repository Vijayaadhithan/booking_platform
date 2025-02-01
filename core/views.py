from rest_framework.viewsets import ModelViewSet
from rest_framework.permissions import IsAuthenticatedOrReadOnly, IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.generics import GenericAPIView
from .models import (
    User, Membership, ServiceProvider, Service, Booking, Review, ServiceCategory, Recurrence,GroupBooking,
    Address, Favorite, ServiceProviderAvailability, ServiceVariation,ServiceBundle,AvailabilityException,WaitingList
)
from django.db.models import Sum, Count
from django.utils.timezone import timedelta
from django.db.models.functions import ExtractMonth
from .serializers import (
    UserSerializer, MembershipSerializer, ServiceProviderSerializer, AddressSerializer,ServiceVariationSerializer,ServiceBundleSerializer,AvailabilityExceptionSerializer,AvailabilitySerializer,
    ServiceSerializer, BookingSerializer, ReviewSerializer, ServiceCategorySerializer, FavoriteSerializer, ServiceProviderAvailabilitySerializer,GroupBookingSerializer,FavoriteSerializer
)
from django.utils.timezone import now
from datetime import timedelta
from celery.exceptions import CeleryError
from geopy.distance import distance
from .permissions import IsOwnerOrReadOnly, IsProvider # Assuming you create this permission
from elasticsearch_dsl.connections import connections
from elasticsearch_dsl import Search, Q as ES_Q
from .documents import ServiceDocument
from django.core.cache import cache
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError
from rest_framework.decorators import api_view, permission_classes, action
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from datetime import datetime, timedelta
from rest_framework import viewsets, generics, status
from rest_framework.authtoken.views import ObtainAuthToken
from rest_framework.authtoken.models import Token
from rest_framework.views import APIView
from rest_framework.filters import SearchFilter
from django_elasticsearch_dsl_drf.filter_backends import (
    FilteringFilterBackend,
    OrderingFilterBackend,
    SearchFilterBackend,
    CompoundSearchFilterBackend,
)
from .metrics import UserMetricsSerializer, ProviderMetricsSerializer
from rest_framework.versioning import NamespaceVersioning 
from django_elasticsearch_dsl_drf.viewsets import DocumentViewSet
from .tasks import send_booking_confirmation_email_gmail, generate_invoice, sync_booking_to_google_calendar, send_booking_confirmation
# Connect to Elasticsearch
connections.create_connection(hosts=[{'host': 'localhost', 'port': 9200, 'scheme': 'http'}], timeout=20)

class UserViewSet(ModelViewSet):
    queryset = User.objects.all().order_by('-date_joined')
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]  # AllowAny for registration?

class MembershipViewSet(ModelViewSet):
    queryset = Membership.objects.all().order_by('-id')
    serializer_class = MembershipSerializer
    permission_classes = [IsAuthenticated]

class StandardResultsSetPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100

class ServiceCategoryViewSet(ModelViewSet):
    """
    ViewSet for managing service categories.
    """
    queryset = ServiceCategory.objects.all().order_by('-id')
    serializer_class = ServiceCategorySerializer
    permission_classes = [IsAuthenticatedOrReadOnly]

class ServiceBundleViewSet(ModelViewSet):
    queryset = ServiceBundle.objects.all().order_by('-id')
    serializer_class = ServiceBundleSerializer

class APIv1NamespaceVersioning(NamespaceVersioning):
    default_version = 'v1'
    allowed_versions = ['v1']
    namespace = 'api/v1'  # URL namespace for v1

class ServiceProviderViewSet(ModelViewSet):
    queryset = ServiceProvider.objects.all().select_related('user', 'address').order_by('-id')  # Include address
    serializer_class = ServiceProviderSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    filter_backends = [CompoundSearchFilterBackend, DjangoFilterBackend]
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
    """
    ViewSet for managing services.
    """
    queryset = Service.objects.all().select_related('category').order_by('-id')  # Optimize query
    document = ServiceDocument
    serializer_class = ServiceSerializer
    permission_classes = [IsProvider]
    filter_backends = [
        DjangoFilterBackend,
        FilteringFilterBackend,
        OrderingFilterBackend,
        CompoundSearchFilterBackend,
    ]
    filterset_fields = ['name', 'category', 'base_price', 'unit_price']
    pagination_class = StandardResultsSetPagination  # Add pagination

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
        category_id = self.request.query_params.get('category_id')
        if category_id:
            return self.queryset.filter(category_id=category_id)
        elif search:
            queryset = queryset.filter(
                Q(name__icontains=search) |
                Q(description__icontains=search)
            )
            return queryset
        return self.queryset

class ServiceVariationViewSet(ModelViewSet):
    """
    ViewSet for managing service variations.
    """
    queryset = ServiceVariation.objects.all().order_by('-id')
    serializer_class = ServiceVariationSerializer

    def get_queryset(self):
        # Optionally filter by service
        service_id = self.request.query_params.get('service_id')
        if service_id:
            return self.queryset.filter(service_id=service_id)
        return self.queryset

class BookingViewSet(ModelViewSet):
    queryset = Booking.objects.all().select_related(
        'user', 'service_provider', 'service', 'service_provider__address'
    ).order_by('-appointment_time')
    serializer_class = BookingSerializer
    permission_classes = [IsAuthenticated,IsOwnerOrReadOnly]
    versioning_class = APIv1NamespaceVersioning
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
            queryset = queryset.filter(appointment_time__date__range=[start_date, end_date])

        # Add search and filter_by parameters
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(user__first_name__icontains=search) |
                Q(user__last_name__icontains=search) |
                Q(service__name__icontains=search)
            )

        return queryset

    def perform_create(self, serializer):
        # Save the booking instance
        booking = serializer.save(user=self.request.user)

        # Prepare buffer time and overlapping booking validation
        service = booking.service
        provider = booking.service_provider
        appointment_time = booking.appointment_time
        buffer_time = service.buffer_time
        booking = serializer.save(user=self.request.user)
        send_booking_confirmation.delay(booking.id)
        # Calculate buffer window
        buffer_start = appointment_time - buffer_time
        buffer_end = appointment_time + buffer_time + service.duration

        # Check for overlapping bookings
        overlapping_bookings = Booking.objects.filter(
            service_provider=provider,
            appointment_time__range=(buffer_start, buffer_end)
        )
        if overlapping_bookings.exists():
            raise ValidationError("This time slot is unavailable due to buffer time constraints.")

        # Prepare email details
        booking_details = {
            'user_name': booking.user.get_full_name(),
            'service_name': booking.service.name,
            'date': booking.appointment_time.date(),
            'time': booking.appointment_time.time(),
        }

        # Trigger Celery tasks
        try:
            send_booking_confirmation_email_gmail.delay(booking.user.email, booking_details)
            #send_booking_confirmation.delay(booking.id)
        except Exception as e:
            print(f"Error sending email for booking {booking.id}: {e}")

        try:
            sync_booking_to_google_calendar.delay(booking.id)
        except Exception as e:
            print(f"Error syncing booking {booking.id} to Google Calendar: {e}")

        try:
            invoice_details = {
                'customer_name': booking.user.get_full_name(),
                'service_name': booking.service.name,
                'date': booking.appointment_time.date(),
                'time': booking.appointment_time.time(),
                'total_price': booking.calculate_price(),
            }
            generate_invoice.delay(booking.id, invoice_details)
        except Exception as e:
            print(f"Error generating invoice for booking {booking.id}: {e}")
        
        if isinstance(booking, GroupBooking):
            if booking.current_participants >= booking.max_participants:
                raise ValidationError("Recurring group booking exceeds maximum participants.")
            
        # Handle recurrence if specified
        recurrence_data = self.request.data.get('recurrence')
        if recurrence_data:
            frequency = recurrence_data.get('frequency')
            interval = recurrence_data.get('interval', 1)
            end_date = recurrence_data.get('end_date')

            # Create recurrence entry
            Recurrence.objects.create(
                booking=booking,
                frequency=frequency,
                interval=interval,
                end_date=end_date,
            )

            # Generate additional bookings based on recurrence
            while appointment_time.date() <= end_date:
                appointment_time += self.get_recurrence_delta(frequency, interval)

                # Skip if new appointment time exceeds the end_date
                if appointment_time.date() > end_date:
                    break

                # Check for conflicts
                if Booking.objects.filter(
                    service_provider=provider,
                    appointment_time__range=(
                        appointment_time - buffer_time,
                        appointment_time + service.duration + buffer_time,
                    )
                ).exists():
                    raise ValidationError("Recurring appointments conflict with existing bookings.")

                # Create recurring booking
                Booking.objects.create(
                    user=booking.user,
                    service_provider=provider,
                    service=service,
                    appointment_time=appointment_time,
                )

    @staticmethod
    def get_recurrence_delta(frequency, interval):
        """
        Calculate the time delta for recurrence based on frequency and interval.
        """
        if frequency == 'daily':
            return timedelta(days=interval)
        elif frequency == 'weekly':
            return timedelta(weeks=interval)
        elif frequency == 'monthly':
            return timedelta(days=30 * interval)  # Approximation for months
        raise ValidationError("Invalid recurrence frequency.")
    
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
    
    @action(detail=True, methods=['patch'], url_path='reschedule')
    def reschedule_booking(self, request, pk=None):
        booking = self.get_object()
        new_time = request.data.get('appointment_time')
        # Validate and update booking...
        booking.appointment_time = new_time
        booking.save()
        return Response({"detail": "Booking rescheduled successfully."})
    
class ReviewViewSet(ModelViewSet):
    queryset = Review.objects.all().select_related('user', 'service_provider').order_by('-created_at')
    serializer_class = ReviewSerializer
    permission_classes = [IsAuthenticated, IsOwnerOrReadOnly]

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

class ServiceProviderAvailabilityViewSet(ModelViewSet):
    queryset = ServiceProviderAvailability.objects.all().order_by('-id')
    serializer_class = ServiceProviderAvailabilitySerializer

    def get_queryset(self):
        provider_id = self.request.query_params.get('provider_id')
        if provider_id:
            return self.queryset.filter(service_provider_id=provider_id)
        return self.queryset

class CheckAvailabilityView(GenericAPIView):
    serializer_class = AvailabilitySerializer

    def get(self, request):
        # Your availability check logic...
        data = {"available": True, "reason": "Time slot available"}
        serializer = self.get_serializer(data)
        return Response(serializer.data)

class UserMetricsView(GenericAPIView):
    serializer_class = UserMetricsSerializer

    def get(self, request):
        user = request.user

        # Total spend calculation
        total_spend = Booking.objects.filter(user=user, status='completed').aggregate(
            total_spend=Sum('total_price')
        )['total_spend'] or 0.0

        # Total bookings calculation
        total_bookings = Booking.objects.filter(user=user).count()

        last_year = now().date() - timedelta(days=365)
        bookings_by_month = (
            Booking.objects.filter(user=user, appointment_time__date__gte=last_year)
            .annotate(month=ExtractMonth('appointment_time'))
            .values('month')
            .annotate(count=Count('id'))
            .order_by('month')
        )
        activity_graph = {
            'labels': [f"Month {b['month']}" for b in bookings_by_month],
            'values': [b['count'] for b in bookings_by_month],
        }

        # Favorite services (based on booking count)
        favorite_services = (
            Service.objects.filter(bookings__user=user)
            .annotate(bookings_count=Count('bookings'))
            .order_by('-bookings_count')[:5]
            .values_list('name', flat=True)
        )

        metrics = {
            'total_spend': total_spend,
            'total_bookings': total_bookings,
            'duration': 365,
            'activity_graph': activity_graph,
            'favorite_services': list(favorite_services),
        }

        serializer = self.get_serializer(metrics)
        return Response(serializer.data)

class ProviderMetricsView(GenericAPIView):
    serializer_class = ProviderMetricsSerializer

    def get(self, request):
        provider = request.user.serviceprovider

        # Total revenue calculation
        revenue = Booking.objects.filter(
            service_provider=provider, status='completed'
        ).aggregate(revenue=Sum('total_price'))['revenue'] or 0.0

        # Total bookings calculation
        total_bookings = Booking.objects.filter(service_provider=provider).count()

        # Active services
        active_services = Service.objects.filter(service_provider=provider, is_active=True).count()

        metrics = {
            'revenue': revenue,
            'total_bookings': total_bookings,
            'active_services': active_services,
        }

        serializer = self.get_serializer(metrics)
        return Response(serializer.data)

class AvailabilityExceptionViewSet(ModelViewSet):
    queryset = AvailabilityException.objects.all().order_by('-id')
    serializer_class = AvailabilityExceptionSerializer

    def get_queryset(self):
        provider_id = self.request.query_params.get('provider_id')
        if provider_id:
            return self.queryset.filter(service_provider_id=provider_id)
        return self.queryset


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

class FavoritesView(GenericAPIView):
    serializer_class = FavoriteSerializer

    def get(self, request):
        user_favorites = Favorite.objects.filter(user=request.user)
        serializer = self.get_serializer(user_favorites, many=True)
        return Response(serializer.data)

class UserLogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        request.user.auth_token.delete()
        return Response(status=status.HTTP_200_OK)


class GroupBookingViewSet(ModelViewSet):
    queryset = GroupBooking.objects.all().select_related('service_provider', 'service').order_by('-appointment_time')
    serializer_class = GroupBookingSerializer

    @action(detail=True, methods=['post'], url_path='join')
    def join_group(self, request, pk=None):
        """
        Allow a user to join a group booking.
        """
        group_booking = self.get_object()

        # Check if the group booking is full
        if group_booking.current_participants >= group_booking.max_participants:
            return Response({"detail": "This group booking is full."}, status=400)

        # Add the user to the group booking
        GroupParticipant.objects.create(user=request.user, group_booking=group_booking)
        group_booking.current_participants += 1
        group_booking.save()

        return Response({"detail": "You have successfully joined the group booking."})
    
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

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def service_provider_availability(request, provider_id):
    """
    Endpoint to retrieve service provider availability, with caching.
    """
    # Check if the data is in the cache
    cache_key = f"service_provider_{provider_id}_availability"
    availability = cache.get(cache_key)

    if availability is None:
        # Data is not in the cache, fetch from the database
        availabilities = ServiceProviderAvailability.objects.filter(service_provider_id=provider_id)
        availability = [
            {
                "day_of_week": availability.day_of_week,
                "start_time": availability.start_time.strftime('%H:%M'),
                "end_time": availability.end_time.strftime('%H:%M'),
            }
            for availability in availabilities
        ]

        # Store the data in the cache for 1 hour (3600 seconds)
        cache.set(cache_key, availability, timeout=3600)

    return Response(availability)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def join_waiting_list(request, service_id):
    WaitingList.objects.create(service_id=service_id, user=request.user)
    return Response({"detail": "Added to waiting list."})

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def leave_waiting_list(request, service_id):
    WaitingList.objects.filter(service_id=service_id, user=request.user).delete()
    return Response({"detail": "Removed from waiting list."})

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def check_availability(request):
    """
    Endpoint to check the real-time availability of a service provider.
    """
    provider_id = request.query_params.get('provider_id')
    service_id = request.query_params.get('service_id')
    appointment_time = request.query_params.get('appointment_time')

    if not all([provider_id, service_id, appointment_time]):
        return Response({"detail": "Missing required parameters."}, status=400)

    # Convert appointment_time to datetime
    from django.utils.dateparse import parse_datetime
    appointment_time = parse_datetime(appointment_time)
    if not appointment_time:
        return Response({"detail": "Invalid appointment_time format."}, status=400)

    # Check availability
    # 1. Check provider availability
    day_of_week = appointment_time.strftime('%A')
    availability = ServiceProviderAvailability.objects.filter(
        service_provider_id=provider_id,
        day_of_week=day_of_week,
        start_time__lte=appointment_time.time(),
        end_time__gte=appointment_time.time()
    ).exists()

    if not availability:
        return Response({"available": False, "reason": "Service provider is unavailable during this time."})

    # 2. Check for overlapping bookings
    buffer_time = Booking.objects.get(service_id=service_id).service.buffer_time
    buffer_start = appointment_time - buffer_time
    buffer_end = appointment_time + buffer_time

    overlapping_bookings = Booking.objects.filter(
        service_provider_id=provider_id,
        appointment_time__range=(buffer_start, buffer_end)
    )

    if overlapping_bookings.exists():
        return Response({"available": False, "reason": "Time slot overlaps with an existing booking."})

    return Response({"available": True, "reason": "Time slot is available."})