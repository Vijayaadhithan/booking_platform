from rest_framework.viewsets import ModelViewSet
from rest_framework.permissions import IsAuthenticatedOrReadOnly, IsAuthenticated
from rest_framework import viewsets, permissions, status
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes, action
from rest_framework.exceptions import ValidationError
from rest_framework.generics import GenericAPIView, ListCreateAPIView, DestroyAPIView
from rest_framework.versioning import NamespaceVersioning
from rest_framework.pagination import PageNumberPagination
from rest_framework.filters import SearchFilter
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Sum, Count, Q
from django.db import transaction
from django.utils.timezone import now
from datetime import timedelta
from django.utils.dateparse import parse_datetime
import logging

from drf_spectacular.utils import extend_schema, extend_schema_view
from django_elasticsearch_dsl_drf.filter_backends import (
    FilteringFilterBackend,
    OrderingFilterBackend,
    CompoundSearchFilterBackend,
)

from .models import (
    User, Membership, ServiceProvider, Service, Booking, Review,
    ServiceCategory, Recurrence, GroupBooking, Address, Favorite,
    ServiceProviderAvailability, ServiceVariation, ServiceBundle,
    AvailabilityException, WaitingList
)
from .serializers import (
    UserSerializer, MembershipSerializer, ServiceProviderSerializer,
    AddressSerializer, ServiceVariationSerializer, ServiceBundleSerializer,
    AvailabilityExceptionSerializer, AvailabilitySerializer,
    ServiceSerializer, BookingSerializer, ReviewSerializer,
    ServiceCategorySerializer, FavoriteSerializer,
    ServiceProviderAvailabilitySerializer, GroupBookingSerializer
)
from .permissions import IsOwnerOrReadOnly, IsProvider
from .tasks import (
    send_booking_confirmation_email_gmail, generate_invoice,
    sync_booking_to_google_calendar
)
from .documents import ServiceDocument  # For Elasticsearch
from .metrics import UserMetricsSerializer, ProviderMetricsSerializer
from rest_framework.authtoken.models import Token


logger = logging.getLogger(__name__)


# -----------------------------------------------------------------------------
# Pagination
# -----------------------------------------------------------------------------
class StandardResultsSetPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100


# -----------------------------------------------------------------------------
# User Login Serializer (for custom login view)
# -----------------------------------------------------------------------------
from rest_framework import serializers
class UserLoginSerializer(serializers.Serializer):
    identifier = serializers.CharField()
    password = serializers.CharField()


# -----------------------------------------------------------------------------
# User ViewSets
# -----------------------------------------------------------------------------
class UserViewSet(ModelViewSet):
    queryset = User.objects.all().order_by('-date_joined')
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]


class UserProfileViewSet(viewsets.ModelViewSet):
    """
    Retrieves/updates the current user's profile information.
    """
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user

    def list(self, request, *args, **kwargs):
        serializer = self.get_serializer(self.get_object())
        return Response(serializer.data)


# -----------------------------------------------------------------------------
# Membership ViewSet
# -----------------------------------------------------------------------------
class MembershipViewSet(ModelViewSet):
    queryset = Membership.objects.all().order_by('-id')
    serializer_class = MembershipSerializer
    permission_classes = [IsAuthenticated]


# -----------------------------------------------------------------------------
# ServiceCategory ViewSet
# -----------------------------------------------------------------------------
class ServiceCategoryViewSet(ModelViewSet):
    """
    ViewSet for managing service categories.
    Supports filtering by name, and custom endpoints for category_type & emergency availability.
    """
    queryset = ServiceCategory.objects.all().order_by('-id')
    serializer_class = ServiceCategorySerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['name']  # basic filtering by name

    @action(detail=False, methods=['get'])
    def emergency_services(self, request):
        """
        Get categories that offer emergency services (is_emergency_available=True).
        """
        emergency_categories = self.get_queryset().filter(is_emergency_available=True)
        serializer = self.get_serializer(emergency_categories, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def medical_services(self, request):
        """
        Get categories with category_type='medical'.
        """
        medical_categories = self.get_queryset().filter(category_type='medical')
        serializer = self.get_serializer(medical_categories, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def home_services(self, request):
        """
        Get categories with category_type='home'.
        """
        home_categories = self.get_queryset().filter(category_type='home')
        serializer = self.get_serializer(home_categories, many=True)
        return Response(serializer.data)


# -----------------------------------------------------------------------------
# ServiceBundle ViewSet
# -----------------------------------------------------------------------------
class ServiceBundleViewSet(ModelViewSet):
    queryset = ServiceBundle.objects.all().order_by('-id')
    serializer_class = ServiceBundleSerializer


# -----------------------------------------------------------------------------
# Service Provider ViewSet
# -----------------------------------------------------------------------------
class ServiceProviderViewSet(ModelViewSet):
    queryset = ServiceProvider.objects.select_related('user', 'address').order_by('-id')
    serializer_class = ServiceProviderSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    filter_backends = [CompoundSearchFilterBackend, DjangoFilterBackend]
    filterset_fields = ['service_type', 'address__city', 'rating']
    search_fields = ('user__first_name', 'user__last_name', 'service_type')

    def get_queryset(self):
        queryset = super().get_queryset()

        # Optional distance-based filter
        latitude = self.request.query_params.get('latitude')
        longitude = self.request.query_params.get('longitude')
        radius = self.request.query_params.get('radius')

        if latitude and longitude and radius:
            try:
                from geopy.distance import distance
                user_location = (float(latitude), float(longitude))
                radius = float(radius)
                # Filter in Python because GeoDjango isn't used
                filtered_providers = []
                for sp in queryset:
                    if sp.address and sp.address.latitude and sp.address.longitude:
                        sp_location = (sp.address.latitude, sp.address.longitude)
                        if distance(user_location, sp_location).km <= radius:
                            filtered_providers.append(sp)
                queryset = filtered_providers
            except ValueError:
                pass

        # Filter by a specific service offered
        service_id = self.request.query_params.get('service_id')
        if service_id:
            queryset = [sp for sp in queryset if sp.services_offered.filter(id=service_id).exists()]

        # If we end up with a list due to custom filtering, return it as-is
        return queryset


# -----------------------------------------------------------------------------
# Service ViewSet
# -----------------------------------------------------------------------------
@extend_schema_view(
    list=extend_schema(
        summary="List Services",
        description="Get a list of all services with optional filtering and search.",
    ),
    retrieve=extend_schema(
        summary="Retrieve Service",
        description="Get details of a specific service.",
    ),
    create=extend_schema(
        summary="Create Service",
        description="Create a new service.",
    ),
    update=extend_schema(
        summary="Update Service",
        description="Update an existing service.",
    ),
    destroy=extend_schema(
        summary="Delete Service",
        description="Delete a service.",
    )
)
class ServiceViewSet(ModelViewSet):
    """
    ViewSet for managing services.
    Provides CRUD with optional Elasticsearch searching.
    """
    queryset = Service.objects.select_related('category').order_by('-id')
    serializer_class = ServiceSerializer
    permission_classes = [IsProvider]
    pagination_class = StandardResultsSetPagination
    filter_backends = [
        DjangoFilterBackend,
        FilteringFilterBackend,
        OrderingFilterBackend,
        CompoundSearchFilterBackend,
    ]
    filterset_fields = ['name', 'category', 'base_price', 'unit_price']
    ordering_fields = ['name', 'base_price']
    ordering = ('name',)

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())

        # Optional Elasticsearch search
        q = request.GET.get('q')
        if q:
            # Searching in Elasticsearch indexes for Service
            search = ServiceDocument.search().query("multi_match", query=q, fields=['name', 'description'])
            es_response = search.execute()
            es_ids = [hit.meta.id for hit in es_response]
            # Filter the Django queryset by these IDs
            queryset = Service.objects.filter(pk__in=es_ids)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    def get_queryset(self):
        qs = super().get_queryset()
        search_param = self.request.query_params.get('search')
        category_id = self.request.query_params.get('category_id')

        if category_id:
            qs = qs.filter(category_id=category_id)
        elif search_param:
            qs = qs.filter(Q(name__icontains=search_param) | Q(description__icontains=search_param))
        return qs


# -----------------------------------------------------------------------------
# Service Variation ViewSet
# -----------------------------------------------------------------------------
class ServiceVariationViewSet(ModelViewSet):
    queryset = ServiceVariation.objects.all().order_by('-id')
    serializer_class = ServiceVariationSerializer

    def get_queryset(self):
        service_id = self.request.query_params.get('service_id')
        if service_id:
            return self.queryset.filter(service_id=service_id)
        return super().get_queryset()


# -----------------------------------------------------------------------------
# Booking ViewSet
# -----------------------------------------------------------------------------
class APIv1NamespaceVersioning(NamespaceVersioning):
    default_version = 'v1'
    allowed_versions = ['v1']
    namespace = 'api/v1'  # custom namespace if desired

class BookingViewSet(ModelViewSet):
    queryset = Booking.objects.select_related(
        'user', 'service_provider', 'service', 'service_provider__address'
    ).order_by('-appointment_time')
    serializer_class = BookingSerializer
    permission_classes = [IsAuthenticated, IsOwnerOrReadOnly]
    versioning_class = APIv1NamespaceVersioning

    def get_queryset(self):
        queryset = super().get_queryset()

        # Staff can see all bookings; non-staff see only theirs
        if not self.request.user.is_staff:
            queryset = queryset.filter(user=self.request.user)

        # Optional filter by status
        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)

        # Optional date range filter
        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')
        if start_date and end_date:
            queryset = queryset.filter(appointment_time__date__range=[start_date, end_date])

        # Basic search filter
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(user__first_name__icontains=search) |
                Q(user__last_name__icontains=search) |
                Q(service__name__icontains=search)
            )

        return queryset

    def perform_create(self, serializer):
        """
        Custom create logic:
         - Check buffer time overlap
         - Schedule Celery tasks (email, invoice, calendar sync)
         - Handle recurrence logic if needed
        """
        proposed_data = serializer.validated_data
        service = proposed_data['service']
        provider = proposed_data['service_provider']
        appointment_time = proposed_data['appointment_time']
        
        # Use utility function to check for booking overlap
        from .utils import check_booking_overlap
        if check_booking_overlap(provider, appointment_time, service):
            raise ValidationError("This time slot is unavailable due to buffer constraints.")

        try:
            with transaction.atomic():
                # Create the main booking
                booking = serializer.save(user=self.request.user)
                
                # Handle post-booking tasks (email, calendar, invoice) using utility function
                from .utils import handle_booking_tasks
                handle_booking_tasks(booking, logger)

                # Handle recurrence if specified
                self._handle_recurrence(booking, service, provider)
                
        except Exception as e:
            logger.error(f"Error creating booking: {str(e)}")
            raise
            
    def _handle_recurrence(self, booking, service, provider):
        """Helper method to handle recurring bookings"""
        recurrence_data = self.request.data.get('recurrence')
        if not recurrence_data:
            return
            
        from .models import Recurrence
        from .utils import check_booking_overlap
        
        # Extract recurrence parameters
        freq = recurrence_data.get('frequency')
        interval = int(recurrence_data.get('interval', 1))
        end_date = recurrence_data.get('end_date')
        
        if not end_date:
            raise ValidationError("Recurrence requires an end_date.")

        # Create recurrence record
        Recurrence.objects.create(
            booking=booking,
            frequency=freq,
            interval=interval,
            end_date=end_date
        )

        # Generate subsequent bookings
        current_time = booking.appointment_time
        from datetime import timedelta
        
        while current_time.date().isoformat() <= end_date:
            current_time += self.get_recurrence_delta(freq, interval)
            if current_time.date().isoformat() > end_date:
                break

            # Check overlap for each new occurrence
            if check_booking_overlap(provider, current_time, service, is_recurring=True):
                raise ValidationError("A recurring appointment conflicts with an existing booking.")

            # Create the recurring booking
            Booking.objects.create(
                user=booking.user,
                service_provider=provider,
                service=service,
                appointment_time=current_time
            )

    @staticmethod
    def get_recurrence_delta(frequency, interval):
        """
        Convert recurrence frequency and interval to a timedelta.
        """
        if frequency == 'daily':
            return timedelta(days=interval)
        elif frequency == 'weekly':
            return timedelta(weeks=interval)
        elif frequency == 'monthly':
            # Approximate each month as 30 days
            return timedelta(days=30 * interval)
        raise ValidationError("Invalid recurrence frequency.")

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
        booking.status = 'cancelled'
        booking.save()
        return Response({'status': 'booking cancelled'})

    @action(detail=True, methods=['patch'], url_path='reschedule')
    def reschedule_booking(self, request, pk=None):
        booking = self.get_object()
        new_time_str = request.data.get('appointment_time')
        if not new_time_str:
            return Response({"detail": "No appointment_time provided."}, status=status.HTTP_400_BAD_REQUEST)

        new_time = parse_datetime(new_time_str)
        if not new_time:
            return Response({"detail": "Invalid datetime format."}, status=status.HTTP_400_BAD_REQUEST)

        # Simple example: Just update the appointment_time
        booking.appointment_time = new_time
        booking.save()
        return Response({"detail": "Booking rescheduled successfully."})


# -----------------------------------------------------------------------------
# Review ViewSet
# -----------------------------------------------------------------------------
class ReviewViewSet(ModelViewSet):
    queryset = Review.objects.select_related('user', 'service_provider').order_by('-created_at')
    serializer_class = ReviewSerializer
    permission_classes = [IsAuthenticated, IsOwnerOrReadOnly]

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


# -----------------------------------------------------------------------------
# ServiceProviderAvailability ViewSet
# -----------------------------------------------------------------------------
class ServiceProviderAvailabilityViewSet(ModelViewSet):
    queryset = ServiceProviderAvailability.objects.all().order_by('-id')
    serializer_class = ServiceProviderAvailabilitySerializer

    def get_queryset(self):
        provider_id = self.request.query_params.get('provider_id')
        if provider_id:
            return self.queryset.filter(service_provider_id=provider_id)
        return super().get_queryset()


# -----------------------------------------------------------------------------
# AvailabilityException ViewSet
# -----------------------------------------------------------------------------
class AvailabilityExceptionViewSet(ModelViewSet):
    queryset = AvailabilityException.objects.all().order_by('-id')
    serializer_class = AvailabilityExceptionSerializer

    def get_queryset(self):
        provider_id = self.request.query_params.get('provider_id')
        if provider_id:
            return self.queryset.filter(service_provider_id=provider_id)
        return super().get_queryset()


# -----------------------------------------------------------------------------
# CheckAvailabilityView (Class-based)
# -----------------------------------------------------------------------------
@extend_schema_view(
    get=extend_schema(
        summary="Check Provider Availability",
        description="Returns availability status for a given provider/time.",
        responses={200: AvailabilitySerializer},
    )
)
class CheckAvailabilityView(GenericAPIView):
    serializer_class = AvailabilitySerializer
    permission_classes = [IsAuthenticated]

    def get(self, request):
        provider_id = request.query_params.get('provider_id')
        service_id = request.query_params.get('service_id')
        appointment_time_str = request.query_params.get('appointment_time')

        from .utils import check_provider_availability, format_availability_response
        
        is_available, reason, status_code, _, _ = check_provider_availability(
            provider_id, service_id, appointment_time_str
        )
        
        return format_availability_response(is_available, reason, status_code)


# -----------------------------------------------------------------------------
# UserRegistrationView
# -----------------------------------------------------------------------------
from rest_framework import generics
class UserRegistrationView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = UserSerializer


# -----------------------------------------------------------------------------
# UserLoginView
# -----------------------------------------------------------------------------
from rest_framework.views import APIView

@extend_schema(request=UserLoginSerializer, responses={200: None})
class UserLoginView(APIView):
    """
    Custom login view that allows auth using username or email.
    """
    def post(self, request, *args, **kwargs):
        identifier = request.data.get('identifier')
        password = request.data.get('password')

        if not identifier or not password:
            return Response(
                {'error': 'Both identifier (username/email) and password are required.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        user = None
        # Try email
        try:
            user = User.objects.get(email=identifier)
        except User.DoesNotExist:
            # Then try username
            try:
                user = User.objects.get(username=identifier)
            except User.DoesNotExist:
                return Response({'error': 'Invalid credentials.'}, status=status.HTTP_401_UNAUTHORIZED)

        # Check password
        if not user.check_password(password):
            return Response({'error': 'Invalid credentials.'}, status=status.HTTP_401_UNAUTHORIZED)

        token, created = Token.objects.get_or_create(user=user)
        return Response({
            'token': token.key,
            'user_id': user.pk,
            'username': user.username,
            'email': user.email,
        }, status=status.HTTP_200_OK)


# -----------------------------------------------------------------------------
# FavoritesView (function-based or class-based)
# -----------------------------------------------------------------------------
class FavoritesView(ListCreateAPIView, DestroyAPIView):
    """
    Manages Favorite objects for the authenticated user.
    """
    serializer_class = FavoriteSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Favorite.objects.filter(user=self.request.user)

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    def delete(self, request, *args, **kwargs):
        service_id = request.data.get('service')
        if not service_id:
            return Response({"detail": "No service specified."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            favorite = Favorite.objects.get(user=request.user, service_id=service_id)
            favorite.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Favorite.DoesNotExist:
            return Response({"detail": "Favorite not found."}, status=status.HTTP_404_NOT_FOUND)


# -----------------------------------------------------------------------------
# UserLogoutView
# -----------------------------------------------------------------------------
class UserLogoutView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(request=None, responses={200: None})
    def post(self, request):
        try:
            request.user.auth_token.delete()
            return Response({"detail": "Logged out successfully."}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


# -----------------------------------------------------------------------------
# GroupBooking ViewSet
# -----------------------------------------------------------------------------
class GroupBookingViewSet(ModelViewSet):
    queryset = GroupBooking.objects.select_related('service_provider', 'service').order_by('-appointment_time')
    serializer_class = GroupBookingSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]

    @action(detail=True, methods=['post'], url_path='join')
    def join_group(self, request, pk=None):
        """
        Allow a user to join a group booking if not full.
        """
        group_booking = self.get_object()
        if group_booking.current_participants >= group_booking.max_participants:
            return Response({"detail": "This group booking is full."}, status=400)

        from .models import GroupParticipant
        GroupParticipant.objects.create(
            user=request.user,
            group_booking=group_booking
        )
        group_booking.current_participants += 1
        group_booking.save()
        return Response({"detail": "You have successfully joined the group booking."})


# -----------------------------------------------------------------------------
# Simple function-based "services" view (optional)
# -----------------------------------------------------------------------------
@extend_schema(
    request=None,
    responses={200: ServiceSerializer(many=True)},
)
@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def services(request):
    if request.method == 'GET':
        all_services = Service.objects.all()
        serializer = ServiceSerializer(all_services, many=True)
        return Response(serializer.data)
    elif request.method == 'POST':
        serializer = ServiceSerializer(data=request.data)
        if serializer.is_valid():
            service_obj = serializer.save()
            # Associate newly created service with the requesting user's ServiceProvider, if any
            try:
                provider = ServiceProvider.objects.get(user=request.user)
                provider.services_offered.add(service_obj)
            except ServiceProvider.DoesNotExist:
                pass  # or raise an error if you want only providers to create
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# -----------------------------------------------------------------------------
# Simple function-based "bookings" view (optional)
# -----------------------------------------------------------------------------
@extend_schema(
    request=None,
    responses={200: BookingSerializer(many=True)},
)
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


# -----------------------------------------------------------------------------
# Simple function-based "favorites" view (optional)
# -----------------------------------------------------------------------------
@extend_schema(
    request=FavoriteSerializer,
    responses={200: FavoriteSerializer(many=True)},
)
@api_view(['GET', 'POST', 'DELETE'])
@permission_classes([IsAuthenticated])
def favorites(request):
    if request.method == 'GET':
        favs = Favorite.objects.filter(user=request.user)
        serializer = FavoriteSerializer(favs, many=True)
        return Response(serializer.data)
    elif request.method == 'POST':
        serializer = FavoriteSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(user=request.user)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    elif request.method == 'DELETE':
        service_id = request.data.get('service')
        if not service_id:
            return Response({"detail": "No service specified."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            favorite = Favorite.objects.get(user=request.user, service_id=service_id)
            favorite.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Favorite.DoesNotExist:
            return Response({"detail": "Favorite not found."}, status=status.HTTP_404_NOT_FOUND)


# -----------------------------------------------------------------------------
# user_metrics (function-based) - Basic example
# -----------------------------------------------------------------------------
@extend_schema(
    request=None,
    responses={200: None},
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def user_metrics(request):
    """
    Example user metrics endpoint. Adjust as desired.
    """
    user = request.user

    # total spend on completed or paid bookings
    total_spend = Booking.objects.filter(
        user=user,
        payment_status='paid'
    ).aggregate(total_spend=Sum('total_price'))['total_spend'] or 0.0

    # total bookings
    total_bookings = Booking.objects.filter(user=user).count()

    # membership duration
    # if using user.date_joined or membership start
    from datetime import datetime
    duration = (datetime.now() - user.date_joined).days if user.date_joined else 0

    # activity graph (last 30 days)
    today = now()
    one_month_ago = today - timedelta(days=30)
    bookings_last_month = Booking.objects.filter(
        user=user,
        appointment_time__gte=one_month_ago,
        appointment_time__lte=today
    )
    # Just a simple daily count
    days_list = [one_month_ago + timedelta(days=i) for i in range(31)]
    labels = [day.strftime('%Y-%m-%d') for day in days_list]
    values = [
        bookings_last_month.filter(appointment_time__date=day.date()).count()
        for day in days_list
    ]
    activity_graph = {
        'labels': labels,
        'values': values,
    }

    # favorite services by frequency
    favorite_services = [fav.service.name for fav in Favorite.objects.filter(user=user)]

    metrics = {
        'totalSpend': float(total_spend),
        'totalBookings': total_bookings,
        'duration': duration,
        'activityGraph': activity_graph,
        'favoriteServices': favorite_services,
    }
    return Response(metrics)


# -----------------------------------------------------------------------------
# provider_metrics (function-based) - Basic example
# -----------------------------------------------------------------------------
@extend_schema(
    request=None,
    responses={200: None},
)
@api_view(['GET'])
@permission_classes([IsProvider])
def provider_metrics(request):
    """
    Example provider metrics endpoint. Adjust as needed.
    """
    provider = request.user.serviceprovider

    # total revenue from completed or paid bookings
    total_revenue = Booking.objects.filter(
        service_provider=provider,
        payment_status='paid'
    ).aggregate(revenue=Sum('total_price'))['revenue'] or 0.0

    # total bookings
    total_bookings = Booking.objects.filter(service_provider=provider).count()

    # active services
    active_services_count = provider.services_offered.filter(is_active=True).count()

    metrics = {
        'revenue': float(total_revenue),
        'totalBookings': total_bookings,
        'activeServices': active_services_count
    }
    return Response(metrics)


# -----------------------------------------------------------------------------
# service_provider_availability function-based
# -----------------------------------------------------------------------------
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def service_provider_availability(request, provider_id):
    """
    Endpoint to retrieve service provider availability, with caching if desired.
    """
    from django.core.cache import cache
    cache_key = f"service_provider_{provider_id}_availability"
    availability = cache.get(cache_key)

    if availability is None:
        availabilities = ServiceProviderAvailability.objects.filter(service_provider_id=provider_id)
        availability = [
            {
                "day_of_week": av.day_of_week,
                "start_time": av.start_time.strftime('%H:%M'),
                "end_time": av.end_time.strftime('%H:%M'),
            } for av in availabilities
        ]
        cache.set(cache_key, availability, timeout=3600)  # cache for 1 hour

    return Response(availability)


# -----------------------------------------------------------------------------
# join_waiting_list / leave_waiting_list
# -----------------------------------------------------------------------------
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


# -----------------------------------------------------------------------------
# Function-based check_availability (already have a class-based version above)
# -----------------------------------------------------------------------------
@extend_schema(
    request=None,
    responses={200: AvailabilitySerializer},
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def check_availability(request):
    """
    Endpoint to check real-time availability of a service provider (function-based).
    Uses the same utility function as CheckAvailabilityView for consistency.
    """
    provider_id = request.query_params.get('provider_id')
    service_id = request.query_params.get('service_id')
    appointment_time_str = request.query_params.get('appointment_time')

    from .utils import check_provider_availability, format_availability_response
    
    is_available, reason, status_code, _, _ = check_provider_availability(
        provider_id, service_id, appointment_time_str
    )
    
    return format_availability_response(is_available, reason, status_code)
