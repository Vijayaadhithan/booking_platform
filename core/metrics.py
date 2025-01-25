from rest_framework import serializers

class UserMetricsSerializer(serializers.Serializer):
    total_spend = serializers.FloatField()
    total_bookings = serializers.IntegerField()
    duration = serializers.IntegerField()
    activity_graph = serializers.DictField()
    favorite_services = serializers.ListField(child=serializers.CharField())

class ProviderMetricsSerializer(serializers.Serializer):
    revenue = serializers.FloatField()
    total_bookings = serializers.IntegerField()
    active_services = serializers.IntegerField()
