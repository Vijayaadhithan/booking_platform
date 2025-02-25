from django.db import models
from django.core.validators import MinValueValidator
from decimal import Decimal
from django.utils import timezone
from .models import User, Membership

class RazorpayPayment(models.Model):
    """
    Model for storing Razorpay payment information
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='payments')
    order_id = models.CharField(max_length=100, unique=True)
    payment_id = models.CharField(max_length=100, unique=True, null=True, blank=True)
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    currency = models.CharField(max_length=3, default='INR')
    status = models.CharField(
        max_length=20,
        choices=[
            ('created', 'Created'),
            ('authorized', 'Authorized'),
            ('captured', 'Captured'),
            ('failed', 'Failed'),
            ('refunded', 'Refunded')
        ],
        default='created'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Payment {self.order_id} - {self.status}"

class MembershipSubscription(models.Model):
    """
    Model for managing membership subscriptions with trial periods and auto-renewal
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='subscriptions')
    membership = models.ForeignKey(Membership, on_delete=models.CASCADE)
    start_date = models.DateTimeField(default=timezone.now)
    end_date = models.DateTimeField()
    trial_end_date = models.DateTimeField(null=True, blank=True)
    is_trial = models.BooleanField(default=False)
    auto_renew = models.BooleanField(default=True)
    status = models.CharField(
        max_length=20,
        choices=[
            ('active', 'Active'),
            ('trial', 'Trial'),
            ('expired', 'Expired'),
            ('cancelled', 'Cancelled')
        ],
        default='trial'
    )
    last_payment = models.ForeignKey(
        RazorpayPayment,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='subscriptions'
    )

    def __str__(self):
        return f"{self.user.username}'s {self.membership.name} Subscription"

    def is_active(self):
        now = timezone.now()
        if self.status == 'cancelled':
            return False
        if self.is_trial and self.trial_end_date:
            return now <= self.trial_end_date
        return now <= self.end_date

class PaymentWebhookLog(models.Model):
    """
    Model for logging Razorpay webhook events
    """
    event_id = models.CharField(max_length=100, unique=True)
    event_type = models.CharField(max_length=100)
    payment = models.ForeignKey(RazorpayPayment, on_delete=models.CASCADE, null=True)
    payload = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Webhook {self.event_type} - {self.event_id}"