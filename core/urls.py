from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import UserViewSet, MembershipViewSet, ServiceProviderViewSet, ServiceViewSet

router = DefaultRouter()
router.register(r'users', UserViewSet)
router.register(r'memberships', MembershipViewSet)
router.register(r'service-providers', ServiceProviderViewSet)
router.register(r'services', ServiceViewSet)

urlpatterns = [
    path('', include(router.urls)),
]
