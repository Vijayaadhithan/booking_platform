from rest_framework import permissions

class IsOwnerOrReadOnly(permissions.BasePermission):
    """
    Only allow owners of an object to edit it; read-only for others.
    """
    def has_object_permission(self, request, view, obj):
        # Read permissions are allowed to any request
        if request.method in permissions.SAFE_METHODS:
            return True
        # Write permissions only if obj.user == request.user
        return hasattr(obj, 'user') and (obj.user == request.user)


class IsProvider(permissions.BasePermission):
    """
    Allows access only to users that have a linked ServiceProvider profile.
    """
    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and hasattr(request.user, 'serviceprovider')
        )


class IsProviderOrReadOnly(permissions.BasePermission):
    """
    Allows access only to providers, or read-only for others.
    """
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return (
            request.user
            and request.user.is_authenticated
            and hasattr(request.user, 'serviceprovider')
        )


class CanUpdateAvailability(permissions.BasePermission):
    """
    Allows only a provider to update their own availability.
    """
    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        return (
            request.user.is_authenticated
            and hasattr(request.user, 'serviceprovider')
            and obj.service_provider == request.user.serviceprovider
        )


class CanCancelBooking(permissions.BasePermission):
    """
    Allows users to cancel their own bookings.
    """
    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        return hasattr(obj, 'user') and (obj.user == request.user)
