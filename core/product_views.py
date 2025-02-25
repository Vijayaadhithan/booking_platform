from rest_framework.viewsets import ModelViewSet
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from rest_framework.decorators import action
from django_filters.rest_framework import DjangoFilterBackend
from .product_models import ProductCategory, Product, Order, OrderItem
from .serializers import ProductCategorySerializer, ProductSerializer, OrderSerializer, OrderItemSerializer
from .permissions import IsOwnerOrReadOnly

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
        status = request.data.get('status')
        if status not in dict(Order.STATUS_CHOICES):
            return Response(
                {'error': 'Invalid status'},
                status=status.HTTP_400_BAD_REQUEST
            )
        order.status = status
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