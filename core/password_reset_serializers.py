from rest_framework import serializers

class RequestPasswordResetSerializer(serializers.Serializer):
    email = serializers.EmailField()

class VerifyPasswordResetTokenSerializer(serializers.Serializer):
    pass  # No fields needed as token and uid are passed in URL

class ResetPasswordSerializer(serializers.Serializer):
    password = serializers.CharField(write_only=True)