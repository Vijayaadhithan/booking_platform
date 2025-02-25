from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    UserViewSet, MembershipViewSet, ServiceProviderViewSet,ServiceProviderAvailabilityViewSet, AvailabilityExceptionViewSet,CheckAvailabilityView, FavoritesView, UserMetricsView, ProviderMetricsView,
    ServiceViewSet, BookingViewSet, ReviewViewSet, ServiceCategoryViewSet, ServiceVariationViewSet,ServiceBundleViewSet,GroupBookingViewSet,check_availability,UserLoginView, UserRegistrationView,UserLogoutView
)
from .product_views import ProductViewSet, ProductCategoryViewSet, OrderViewSet
from .password_reset import RequestPasswordResetView, VerifyPasswordResetTokenView, ResetPasswordView
from . import views

router = DefaultRouter()
router.register(r'users', UserViewSet)
router.register(r'memberships', MembershipViewSet)
router.register(r'service-providers', ServiceProviderViewSet)
router.register(r'services', ServiceViewSet, basename='service')
router.register(r'bookings', BookingViewSet)
router.register(r'reviews', ReviewViewSet)
router.register(r'service-categories', ServiceCategoryViewSet, basename='service-category')  # Add service categories
router.register(r'service-variations', ServiceVariationViewSet, basename='service-variation')
router.register(r'service-bundles', ServiceBundleViewSet, basename='service-bundle')
router.register(r'availabilities', ServiceProviderAvailabilityViewSet, basename='availability')
router.register(r'exceptions', AvailabilityExceptionViewSet, basename='exception')
router.register(r'group-bookings', GroupBookingViewSet, basename='group-booking')

# Product management endpoints
router.register(r'products', ProductViewSet, basename='product')
router.register(r'product-categories', ProductCategoryViewSet, basename='product-category')
router.register(r'orders', OrderViewSet, basename='order')

urlpatterns = [
    path('', include(router.urls)),
    path('services/', views.services, name='services'),
    path('bookings/', views.bookings, name='bookings'),
    path('favorites/', views.favorites, name='favorites'),
    path('user/metrics/', views.user_metrics, name='user-metrics'),
    path('provider/metrics/', views.provider_metrics, name='provider-metrics'),
    path('bookings/check-availability-fbv/', check_availability, name='bookings/check-availability-fbv/'),
    path('register/', UserRegistrationView.as_view(), name='user-register'),
    path('login/', UserLoginView.as_view(), name='login'),
    path('logout/', UserLogoutView.as_view(), name='logout'),
    path('bookings/check-availability/', CheckAvailabilityView.as_view(), name='check-availability'),
    path('favorites/', FavoritesView.as_view(), name='favorites'),
    path('user/metrics/', UserMetricsView.as_view(), name='user-metrics'),
    path('provider/metrics/', ProviderMetricsView.as_view(), name='provider-metrics'),
    # Password reset endpoints
    path('password/reset/', RequestPasswordResetView.as_view(), name='password-reset-request'),
    path('password/reset/<str:uidb64>/<str:token>/', VerifyPasswordResetTokenView.as_view(), name='password-reset-verify'),
    path('password/reset/confirm/<str:uidb64>/<str:token>/', ResetPasswordView.as_view(), name='password-reset-confirm'),
]
