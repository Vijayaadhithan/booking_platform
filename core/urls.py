from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    UserViewSet, MembershipViewSet, ServiceProviderViewSet,
    ServiceViewSet, BookingViewSet, ReviewViewSet, ServiceCategoryViewSet
)
from . import views

router = DefaultRouter()
router.register(r'users', UserViewSet)
router.register(r'memberships', MembershipViewSet)
router.register(r'service-providers', ServiceProviderViewSet)
router.register(r'services', ServiceViewSet)
router.register(r'bookings', BookingViewSet)
router.register(r'reviews', ReviewViewSet)
router.register(r'service-categories', ServiceCategoryViewSet)  # Add service categories

urlpatterns = [
    path('', include(router.urls)),
    path('services/', views.services, name='services'),
    path('bookings/', views.bookings, name='bookings'),
    path('favorites/', views.favorites, name='favorites'),
    path('user/metrics/', views.user_metrics, name='user-metrics'), # User metrics endpoint
    path('provider/metrics/', views.provider_metrics, name='provider-metrics'), # Provider metrics endpoint
]