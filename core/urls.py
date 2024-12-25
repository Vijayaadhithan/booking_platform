from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    UserViewSet, MembershipViewSet, ServiceProviderViewSet,
    ServiceViewSet, BookingViewSet, ReviewViewSet, ServiceCategoryViewSet
)

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
]