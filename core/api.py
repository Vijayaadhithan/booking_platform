from rest_framework import viewsets, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def profile_view(request):
    """API endpoint for user profile.
    
    Returns basic user profile information for the authenticated user.
    """
    user = request.user
    data = {
        'id': user.id,
        'username': user.username,
        'email': user.email,
        'first_name': user.first_name,
        'last_name': user.last_name
    }
    return Response(data)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def services_list(request):
    """API endpoint for listing services.
    
    Returns a list of available services.
    """
    # Simple response for testing throttling
    return Response({'message': 'Services list endpoint'})