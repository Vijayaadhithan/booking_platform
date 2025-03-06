from rest_framework.viewsets import ModelViewSet
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from rest_framework.decorators import action
from django_filters.rest_framework import DjangoFilterBackend
from .product_models import ProductCategory, Product, Order, OrderItem
from .serializers import ProductCategorySerializer, ProductSerializer, OrderSerializer, OrderItemSerializer
from .permissions import IsOwnerOrReadOnly
from django.db import transaction

class ProductCategoryViewSet(ModelViewSet):
    """
    ViewSet for managing product categories.
    Supports CRUD operations for product categories.
    """
    queryset = ProductCategory.objects.all().order_by('-id')
    serializer_class = ProductCategorySerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['parent']

class ProductViewSet(ModelViewSet):
    """
    ViewSet for managing products.
    Supports CRUD operations and filtering by category.
    """
    queryset = Product.objects.all().order_by('-created_at')
    serializer_class = ProductSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['category', 'is_active']

    @action(detail=True, methods=['post'])
    def update_stock(self, request, pk=None):
        product = self.get_object()
        quantity = request.data.get('quantity')
        if quantity is None:
            return Response(
                {'error': 'Quantity is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        product.stock_quantity = quantity
        product.save()
        return Response({'status': 'stock updated'})

class OrderViewSet(ModelViewSet):
    """
    ViewSet for managing orders.
    Supports order creation, status updates, and filtering.
    """
    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticated, IsOwnerOrReadOnly]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['status']

    def get_queryset(self):
        if self.request.user.is_staff:
            return Order.objects.all().order_by('-created_at')
        return Order.objects.filter(user=self.request.user).order_by('-created_at')

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @action(detail=True, methods=['patch'])
    def update_status(self, request, pk=None):
        order = self.get_object()
        order_status = request.data.get('status')
        if order_status not in dict(Order.STATUS_CHOICES):
            return Response(
                {'error': 'Invalid status'},
                status=status.HTTP_400_BAD_REQUEST
            )
        order.status = order_status
        order.save()
        return Response({'status': 'order status updated'})

class OrderItemViewSet(ModelViewSet):
    """
    ViewSet for managing order items.
    Supports CRUD operations for items within an order.
    """
    queryset = OrderItem.objects.all()
    serializer_class = OrderItemSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        order_id = self.request.query_params.get('order_id')
        if order_id:
            return self.queryset.filter(order_id=order_id)
        return self.queryset
    
    @transaction.atomic
    def perform_create(self, serializer):
        """
        Creates an OrderItem, ensures there's enough stock,
        logs an InventoryTransaction, and updates the order total.
        """
        # The validated data is still in serializer.validated_data, but we’ll do it manually:
        product_id = serializer.validated_data['product'].id
        quantity = serializer.validated_data['quantity']

        # 1) Lock the product row
        product = Product.objects.select_for_update().get(pk=product_id)

        # 2) Check stock
        if product.stock_quantity < quantity:
            raise ValidationError("Not enough stock available.")

        # 3) Deduct stock
        product.stock_quantity -= quantity
        product.save()

        # 4) OPTIONAL: Create an InventoryTransaction
        # Only if you want to track each change in inventory:
        InventoryTransaction.objects.create(
            product=product,
            transaction_type='out',
            quantity=-quantity,
            reference_number=f"OrderItem creation",
            notes=f"Auto-deduct on order item create for product {product.id}"
        )

        # 5) Now create the OrderItem
        order_item = serializer.save()

        # 6) Recalc the order total
        order_item.order.recalc_total()

    @transaction.atomic
    def perform_update(self, serializer):
    # existing = self.get_object()  # the old instance
        old_quantity = serializer.instance.quantity

    # 1) Lock product
        product = Product.objects.select_for_update().get(pk=serializer.instance.product_id)

    # 2) Figure out difference
        new_quantity = serializer.validated_data.get('quantity', old_quantity)
        diff = new_quantity - old_quantity  # how many more (or fewer) items

    # 3) If increasing quantity, check stock
        if diff > 0:
            if product.stock_quantity < diff:
                raise ValidationError("Not enough stock for that quantity update.")
            product.stock_quantity -= diff
            product.save()
        # create an InventoryTransaction for the difference if you want
            InventoryTransaction.objects.create(
                product=product,
                transaction_type='out',
                quantity=-diff,
                reference_number=f"OrderItem update",
                notes=f"Auto-deduct on quantity update"
            )
        elif diff < 0:
        # returning some items to stock
            product.stock_quantity += abs(diff)
            product.save()
            InventoryTransaction.objects.create(
                product=product,
                transaction_type='in',
                quantity=abs(diff),
                reference_number=f"OrderItem update",
                notes=f"Auto-restock on quantity update"
            )

    # 4) Proceed with updating the item
        order_item = serializer.save()
    # 5) Recalc the total
        order_item.order.recalc_total()


    def perform_destroy(self, instance):
        order = instance.order
        super().perform_destroy(instance)
        order.recalc_total()
