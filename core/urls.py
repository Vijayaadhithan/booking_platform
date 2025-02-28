# core/urls.py

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    UserViewSet, MembershipViewSet, ServiceProviderViewSet,
    ServiceProviderAvailabilityViewSet, AvailabilityExceptionViewSet,
    CheckAvailabilityView, FavoritesView, 
    ServiceViewSet, BookingViewSet, ReviewViewSet,
    ServiceCategoryViewSet, ServiceVariationViewSet, ServiceBundleViewSet,
    GroupBookingViewSet, # <-- keep only the classes that exist
    services, bookings, favorites, user_metrics, provider_metrics, # <-- function-based
    check_availability, UserLoginView, UserRegistrationView, UserLogoutView
    # ^ Notice we removed UserMetricsView, ProviderMetricsView
    # if they don't exist anymore
)
from .product_views import ProductViewSet, ProductCategoryViewSet, OrderViewSet
from .password_reset import (
    RequestPasswordResetView, VerifyPasswordResetTokenView, ResetPasswordView
)

router = DefaultRouter()
router.register(r'users', UserViewSet)
router.register(r'memberships', MembershipViewSet)
router.register(r'service-providers', ServiceProviderViewSet)
router.register(r'services', ServiceViewSet, basename='service')
router.register(r'bookings', BookingViewSet)
router.register(r'reviews', ReviewViewSet)
router.register(r'service-categories', ServiceCategoryViewSet, basename='service-category')
router.register(r'service-variations', ServiceVariationViewSet, basename='service-variation')
router.register(r'service-bundles', ServiceBundleViewSet, basename='service-bundle')
router.register(r'availabilities', ServiceProviderAvailabilityViewSet, basename='availability')
router.register(r'exceptions', AvailabilityExceptionViewSet, basename='exception')
router.register(r'group-bookings', GroupBookingViewSet, basename='group-booking')

# Product management
router.register(r'products', ProductViewSet, basename='product')
router.register(r'product-categories', ProductCategoryViewSet, basename='product-category')
router.register(r'orders', OrderViewSet, basename='order')

urlpatterns = [
    path('', include(router.urls)),
    path('services/', services, name='services'),
    path('bookings/', bookings, name='bookings'),
    path('favorites/', favorites, name='favorites'),

    # If you are using function-based metrics endpoints
    path('user/metrics/', user_metrics, name='user-metrics'),
    path('provider/metrics/', provider_metrics, name='provider-metrics'),

    # Or if you prefer the class-based approach, you would re-introduce them in views.py
    # path('user/metrics/', UserMetricsView.as_view(), name='user-metrics'),
    # path('provider/metrics/', ProviderMetricsView.as_view(), name='provider-metrics'),

    path('bookings/check-availability-fbv/', check_availability, name='bookings/check-availability-fbv/'),
    path('register/', UserRegistrationView.as_view(), name='user-register'),
    path('login/', UserLoginView.as_view(), name='login'),
    path('logout/', UserLogoutView.as_view(), name='logout'),
    path('bookings/check-availability/', CheckAvailabilityView.as_view(), name='check-availability'),

    # Password reset endpoints
    path('password/reset/', RequestPasswordResetView.as_view(), name='password-reset-request'),
    path('password/reset/<str:uidb64>/<str:token>/', VerifyPasswordResetTokenView.as_view(), name='password-reset-verify'),
    path('password/reset/confirm/<str:uidb64>/<str:token>/', ResetPasswordView.as_view(), name='password-reset-confirm'),
]
