from rest_framework.viewsets import ModelViewSet
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from rest_framework.decorators import action
from django.utils import timezone
from django.db import transaction
from django.conf import settings
import razorpay

from .inventory_models import ProductVariation, InventoryTransaction, StockAlert
from .payment_models import RazorpayPayment, MembershipSubscription, PaymentWebhookLog
from .serializers import (
    ProductVariationSerializer, InventoryTransactionSerializer, StockAlertSerializer,
    RazorpayPaymentSerializer, MembershipSubscriptionSerializer
)
from .permissions import IsOwnerOrReadOnly

class ProductVariationViewSet(ModelViewSet):
    queryset = ProductVariation.objects.all().order_by('-id')
    serializer_class = ProductVariationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        product_id = self.request.query_params.get('product_id')
        if product_id:
            return self.queryset.filter(product_id=product_id)
        return self.queryset

class InventoryTransactionViewSet(ModelViewSet):
    queryset = InventoryTransaction.objects.all().order_by('-created_at')
    serializer_class = InventoryTransactionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        product_id = self.request.query_params.get('product_id')
        if product_id:
            return self.queryset.filter(product_id=product_id)
        return self.queryset

class StockAlertViewSet(ModelViewSet):
    queryset = StockAlert.objects.all()
    serializer_class = StockAlertSerializer
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['get'])
    def active_alerts(self, request):
        alerts = self.queryset.filter(is_active=True)
        serializer = self.get_serializer(alerts, many=True)
        return Response(serializer.data)

class RazorpayPaymentViewSet(ModelViewSet):
    queryset = RazorpayPayment.objects.all().order_by('-created_at')
    serializer_class = RazorpayPaymentSerializer
    permission_classes = [IsAuthenticated, IsOwnerOrReadOnly]

    def get_queryset(self):
        if self.request.user.is_staff:
            return self.queryset
        return self.queryset.filter(user=self.request.user)

    @action(detail=False, methods=['post'])
    def create_order(self, request):
        amount = request.data.get('amount')
        if not amount:
            return Response({'error': 'Amount is required'}, status=status.HTTP_400_BAD_REQUEST)

        client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
        payment_data = {
            'amount': int(float(amount) * 100),  # Convert to paise
            'currency': 'INR',
            'payment_capture': '1'
        }

        order = client.order.create(data=payment_data)
        payment = RazorpayPayment.objects.create(
            user=request.user,
            order_id=order['id'],
            amount=amount
        )

        return Response({
            'order_id': order['id'],
            'amount': amount,
            'key': settings.RAZORPAY_KEY_ID
        })

    @action(detail=False, methods=['post'])
    def verify_payment(self, request):
        payment_id = request.data.get('payment_id')
        order_id = request.data.get('order_id')
        signature = request.data.get('signature')

        if not all([payment_id, order_id, signature]):
            return Response({'error': 'Missing payment details'}, status=status.HTTP_400_BAD_REQUEST)

        client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
        try:
            client.utility.verify_payment_signature({
                'razorpay_payment_id': payment_id,
                'razorpay_order_id': order_id,
                'razorpay_signature': signature
            })

            payment = RazorpayPayment.objects.get(order_id=order_id)
            payment.payment_id = payment_id
            payment.status = 'captured'
            payment.save()

            the_order = Order.objects.get(pk=some_order_id)  # or payment.order
            the_order.status = 'confirmed'
            the_order.save()

            return Response({'status': 'Payment verified successfully'})
        except:
            return Response({'error': 'Invalid payment signature'}, status=status.HTTP_400_BAD_REQUEST)

class MembershipSubscriptionViewSet(ModelViewSet):
    queryset = MembershipSubscription.objects.all().order_by('-start_date')
    serializer_class = MembershipSubscriptionSerializer
    permission_classes = [IsAuthenticated, IsOwnerOrReadOnly]

    def get_queryset(self):
        if self.request.user.is_staff:
            return self.queryset
        return self.queryset.filter(user=self.request.user)

    @action(detail=True, methods=['post'])
    def cancel_auto_renewal(self, request, pk=None):
        subscription = self.get_object()
        subscription.auto_renew = False
        subscription.save()
        return Response({'status': 'Auto-renewal cancelled'})

    @action(detail=True, methods=['post'])
    def activate_trial(self, request, pk=None):
        subscription = self.get_object()
        if subscription.is_trial:
            return Response({'error': 'Trial already activated'}, status=status.HTTP_400_BAD_REQUEST)

        subscription.is_trial = True
        subscription.trial_end_date = timezone.now() + timezone.timedelta(days=14)  # 14-day trial
        subscription.status = 'trial'
        subscription.save()
        return Response({'status': 'Trial activated successfully'})