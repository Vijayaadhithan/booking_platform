from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from rest_framework import status, generics
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny

from .models import User
from .tasks import send_password_reset_email

from .password_reset_serializers import (
    RequestPasswordResetSerializer,
    VerifyPasswordResetTokenSerializer,
    ResetPasswordSerializer
)

class RequestPasswordResetView(generics.GenericAPIView):
    permission_classes = [AllowAny]
    serializer_class = RequestPasswordResetSerializer

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data['email']

        try:
            user = User.objects.get(email=email)
            token = default_token_generator.make_token(user)
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            reset_url = f"/reset-password/{uid}/{token}/"

            # Async send using Celery
            send_password_reset_email.delay(email, reset_url)
            return Response({'message': 'Password reset email has been sent.'})

        except User.DoesNotExist:
            return Response({'error': 'No user found with this email address'}, status=status.HTTP_404_NOT_FOUND)


class VerifyPasswordResetTokenView(generics.GenericAPIView):
    permission_classes = [AllowAny]
    serializer_class = VerifyPasswordResetTokenSerializer

    def get(self, request, uidb64, token):
        try:
            uid = force_str(urlsafe_base64_decode(uidb64))
            user = User.objects.get(pk=uid)

            if default_token_generator.check_token(user, token):
                return Response({'message': 'Token is valid'})
            else:
                return Response({'error': 'Token is invalid or expired'}, status=status.HTTP_400_BAD_REQUEST)

        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            return Response({'error': 'Invalid reset link'}, status=status.HTTP_400_BAD_REQUEST)


class ResetPasswordView(generics.GenericAPIView):
    permission_classes = [AllowAny]
    serializer_class = ResetPasswordSerializer

    def post(self, request, uidb64, token):
        try:
            uid = force_str(urlsafe_base64_decode(uidb64))
            user = User.objects.get(pk=uid)

            if not default_token_generator.check_token(user, token):
                return Response({'error': 'Token is invalid or expired'}, status=status.HTTP_400_BAD_REQUEST)

            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            password = serializer.validated_data['password']

            user.set_password(password)
            user.save()
            return Response({'message': 'Password has been reset successfully'})

        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            return Response({'error': 'Invalid reset link'}, status=status.HTTP_400_BAD_REQUEST)
