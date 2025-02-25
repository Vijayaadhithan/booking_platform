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
    recent_bookings = serializers.IntegerField()
    avg_rating = serializers.FloatField()
    score = serializers.FloatField()
    cancellation_rate = serializers.FloatField()
    no_show_rate = serializers.FloatField()
    peak_hours = serializers.ListField(child=serializers.DictField())
    avg_completion_time = serializers.DurationField()
    booking_conflicts = serializers.IntegerField()

class FeedbackAnalysisSerializer(serializers.Serializer):
    avg_rating = serializers.FloatField()
    total_reviews = serializers.IntegerField()
    common_themes = serializers.ListField(child=serializers.ListField())
