from django.db.models import Count, Avg, Sum, F, ExpressionWrapper, fields, Q
from django.utils.timezone import now
from django.db.models.functions import ExtractHour
from datetime import timedelta
from collections import Counter

from .models import ServiceProvider, Booking, Service, Review

def get_top_providers(limit=10, period_days=30):
    """
    Rank service providers based on average rating, number of bookings, and revenue.
    """
    cutoff_date = now() - timedelta(days=period_days)
    # Adjust 'bookings' if your related_name is different (e.g., 'booking_set')
    return ServiceProvider.objects.annotate(
        recent_bookings=Count(
            'booking', 
            filter=Q(booking__appointment_time__gte=cutoff_date)
        ),
        recent_revenue=Sum(
            'booking__total_price',
            filter=Q(
                booking__status='completed',
                booking__appointment_time__gte=cutoff_date
            )
        ),
        avg_rating=Avg('booking__review__rating'),  # or 'reviews' if you have a different related_name
        # Weighted scoring example
        score=ExpressionWrapper(
            (F('avg_rating') * 0.4) +
            (F('recent_bookings') * 0.3) +
            (F('recent_revenue') * 0.3),
            output_field=fields.FloatField()
        )
    ).order_by('-score')[:limit]


def analyze_booking_efficiency(provider_id=None, period_days=30):
    """
    Analyze booking efficiency metrics (avg completion time, conflicts, cancellation rate).
    """
    cutoff_date = now() - timedelta(days=period_days)
    bookings = Booking.objects.filter(appointment_time__gte=cutoff_date)

    if provider_id:
        bookings = bookings.filter(service_provider_id=provider_id)

    # For average completion time, we need a 'completed_at' field or similar.
    # If you do not have it, you might skip or change this metric.
    completed_bookings = bookings.filter(status='completed').exclude(
        # If you store actual completion_time in your DB,
        # or skip if not applicable
        # e.g., no 'completed_at' in your model
    )

    # We'll mock a small calculation, or just skip
    avg_completion_time = None
    if hasattr(Booking, 'completed_at'):
        completed_bookings = bookings.filter(status='completed')
        avg_completion_time = completed_bookings.annotate(
            completion_time=F('completed_at') - F('appointment_time')
        ).aggregate(avg=Avg('completion_time'))['avg']

    # Overlapping conflicts example: requires a custom approach if you store them
    # We'll define "conflict" as any booking overlapping in time.
    conflicts = 0
    # We might do a naive approach: check each booking against the next for overlap.

    # Simple cancellation rate
    total_count = bookings.count()
    cancelled_count = bookings.filter(status='cancelled').count()
    cancellation_rate = (cancelled_count / total_count) if total_count else 0

    return {
        'avg_completion_time': avg_completion_time,
        'conflicts': conflicts,
        'cancellation_rate': cancellation_rate
    }


def analyze_provider_availability(provider_id, period_days=30):
    """
    Analyze provider availability, e.g., cancellation rate, no-show rate, peak hours.
    """
    cutoff_date = now() - timedelta(days=period_days)
    bookings = Booking.objects.filter(
        service_provider_id=provider_id,
        appointment_time__gte=cutoff_date
    )

    total_count = bookings.count()
    cancellations = bookings.filter(status='cancelled').count()
    no_shows = bookings.filter(status='no_show').count() if hasattr(Booking, 'status') else 0

    # Peak hours: group by hour
    peak_hours = bookings.annotate(
        hour=ExtractHour('appointment_time')
    ).values('hour').annotate(count=Count('id')).order_by('-count')[:3]

    return {
        'cancellation_rate': (cancellations / total_count) if total_count else 0,
        'no_show_rate': (no_shows / total_count) if total_count else 0,
        'peak_hours': list(peak_hours)
    }


def analyze_feedback(provider_id=None, period_days=30):
    """
    Analyze reviews over a time period, including average rating and common themes.
    """
    cutoff_date = now() - timedelta(days=period_days)
    reviews = Review.objects.filter(created_at__gte=cutoff_date)
    if provider_id:
        reviews = reviews.filter(service_provider_id=provider_id)

    avg_rating = reviews.aggregate(r=Avg('rating'))['r'] or 0
    total_reviews = reviews.count()

    # Example: analyzing text for common keywords (not implemented).
    # You'd parse each review.comment, then gather frequencies in a Counter.
    keywords = Counter()
    for rev in reviews:
        if rev.comment:
            # naive splitting by space
            for word in rev.comment.lower().split():
                keywords[word] += 1

    common_themes = keywords.most_common(5)

    return {
        'avg_rating': avg_rating,
        'total_reviews': total_reviews,
        'common_themes': common_themes
    }
