from django.db import models
from django.core.validators import MinValueValidator
from decimal import Decimal
from .product_models import Product

class ProductVariation(models.Model):
    """
    Model for storing product variations (e.g., size, color, etc.)
    """
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='variations')
    name = models.CharField(max_length=255)  # e.g., "Size", "Color"
    value = models.CharField(max_length=255)  # e.g., "Large", "Red"
    sku = models.CharField(max_length=50, unique=True)
    price_adjustment = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text='Amount to add/subtract from base product price'
    )
    stock_quantity = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.product.name} - {self.name}: {self.value}"

class InventoryTransaction(models.Model):
    """
    Model for tracking inventory movements
    """
    TRANSACTION_TYPES = [
        ('in', 'Stock In'),
        ('out', 'Stock Out'),
        ('adjustment', 'Adjustment'),
        ('return', 'Return')
    ]

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='inventory_transactions')
    variation = models.ForeignKey(ProductVariation, on_delete=models.CASCADE, null=True, blank=True)
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPES)
    quantity = models.IntegerField(help_text='Positive for stock in, negative for stock out')
    reference_number = models.CharField(max_length=100, blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if self.variation:
            self.variation.stock_quantity += self.quantity
            self.variation.save()
        else:
            self.product.stock_quantity += self.quantity
            self.product.save()
        super().save(*args, **kwargs)

class StockAlert(models.Model):
    """
    Model for setting up stock alerts
    """
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='stock_alerts')
    variation = models.ForeignKey(ProductVariation, on_delete=models.CASCADE, null=True, blank=True)
    threshold = models.PositiveIntegerField(help_text='Alert when stock falls below this number')
    is_active = models.BooleanField(default=True)
    last_triggered = models.DateTimeField(null=True, blank=True)
    email_notifications = models.BooleanField(default=True)

    def __str__(self):
        base = f"Alert for {self.product.name}"
        if self.variation:
            return f"{base} ({self.variation.name}: {self.variation.value})"
        return base