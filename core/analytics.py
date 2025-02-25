from django.db.models import Count, Avg, F, ExpressionWrapper, fields, Q
from django.utils.timezone import now
from django.db.models.functions import ExtractHour
from datetime import timedelta
from collections import Counter
from .models import ServiceProvider, Booking, Service, Review

def get_top_providers(limit=10, period_days=30):
    """Rank service providers based on ratings, bookings, and revenue."""
    cutoff_date = now() - timedelta(days=period_days)
    
    return ServiceProvider.objects.annotate(
        recent_bookings=Count('booking', filter=Q(booking__created_at__gte=cutoff_date)),
        recent_revenue=Sum('booking__total_price', filter=Q(booking__status='completed', 
                                                          booking__created_at__gte=cutoff_date)),
        avg_rating=Avg('booking__rating__rating'),
        score=ExpressionWrapper(
            F('avg_rating') * 0.4 + 
            F('recent_bookings') * 0.3 + 
            F('recent_revenue') * 0.3,
            output_field=fields.FloatField()
        )
    ).order_by('-score')[:limit]

def analyze_booking_efficiency(provider_id=None, period_days=30):
    """Analyze booking efficiency metrics."""
    cutoff_date = now() - timedelta(days=period_days)
    bookings = Booking.objects.filter(created_at__gte=cutoff_date)
    
    if provider_id:
        bookings = bookings.filter(service_provider_id=provider_id)
    
    metrics = {
        'avg_completion_time': bookings.filter(status='completed')
            .annotate(completion_time=F('completed_at') - F('created_at'))
            .aggregate(avg=Avg('completion_time')),
        'conflicts': bookings.filter(
            appointment_time__overlap=F('appointment_time')
        ).count(),
        'cancellation_rate': bookings.filter(status='cancelled').count() / bookings.count()
            if bookings.count() > 0 else 0
    }
    
    return metrics

def analyze_provider_availability(provider_id, period_days=30):
    """Analyze provider availability and identify issues."""
    cutoff_date = now() - timedelta(days=period_days)
    bookings = Booking.objects.filter(
        service_provider_id=provider_id,
        created_at__gte=cutoff_date
    )
    
    metrics = {
        'cancellation_rate': bookings.filter(status='cancelled').count() / bookings.count()
            if bookings.count() > 0 else 0,
        'no_show_rate': bookings.filter(status='no_show').count() / bookings.count()
            if bookings.count() > 0 else 0,
        'peak_hours': bookings.annotate(
            hour=ExtractHour('appointment_time')
        ).values('hour').annotate(count=Count('id')).order_by('-count')[:3]
    }
    
    return metrics

def analyze_feedback(provider_id=None, period_days=30):
    """Analyze customer feedback and identify common themes."""
    cutoff_date = now() - timedelta(days=period_days)
    reviews = Review.objects.filter(created_at__gte=cutoff_date)
    
    if provider_id:
        reviews = reviews.filter(booking__service_provider_id=provider_id)
    
    # Analyze common keywords in reviews
    keywords = Counter()
    for review in reviews:
        # Add logic to extract and count keywords from review text
        pass
    
    return {
        'avg_rating': reviews.aggregate(avg=Avg('rating'))['avg'],
        'common_themes': keywords.most_common(5),
        'total_reviews': reviews.count()
    }