from rest_framework import serializers
from .inventory_models import ProductVariation, InventoryTransaction, StockAlert
from .payment_models import RazorpayPayment, MembershipSubscription, PaymentWebhookLog
from .product_models import Product

class ProductVariationSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)

    class Meta:
        model = ProductVariation
        fields = ['id', 'product', 'product_name', 'name', 'value', 'sku',
                 'price_adjustment', 'stock_quantity', 'is_active']

class InventoryTransactionSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)

    class Meta:
        model = InventoryTransaction
        fields = ['id', 'product', 'product_name', 'variation', 'transaction_type',
                 'quantity', 'reference_number', 'notes', 'created_at']

class StockAlertSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)

    class Meta:
        model = StockAlert
        fields = ['id', 'product', 'product_name', 'variation', 'threshold',
                 'is_active', 'last_triggered', 'email_notifications']

class RazorpayPaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = RazorpayPayment
        fields = ['id', 'user', 'order_id', 'payment_id', 'amount', 'currency',
                 'status', 'created_at', 'updated_at']
        read_only_fields = ('user', 'created_at', 'updated_at')

class MembershipSubscriptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = MembershipSubscription
        fields = ['id', 'user', 'membership', 'start_date', 'end_date',
                 'trial_end_date', 'is_trial', 'auto_renew', 'status',
                 'last_payment']
        read_only_fields = ('user', 'trial_end_date', 'is_trial')

class PaymentWebhookLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentWebhookLog
        fields = ['id', 'event_id', 'event_type', 'payment', 'payload',
                 'created_at']
        read_only_fields = ('created_at',)