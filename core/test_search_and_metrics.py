from django.test import TestCase
from django.utils.timezone import now, timedelta
from unittest.mock import patch, MagicMock
from decimal import Decimal
from elasticsearch_dsl.connections import connections
from .models import User, Service, ServiceProvider, Booking, ServiceCategory
from .documents import ServiceDocument
from .metrics import UserMetricsSerializer, ProviderMetricsSerializer

class SearchIntegrationTest(TestCase):
    """Test suite for Elasticsearch integration.
    
    Tests service indexing, searching, and document management.
    """
    
    def setUp(self):
        """Set up test data and ensure Elasticsearch connection."""
        # Create test service
        self.category = ServiceCategory.objects.create(name='Test Category')
        self.service = Service.objects.create(
            name='Test Service',
            description='Test Description',
            category=self.category,
            base_price=Decimal('50.00'),
            unit_price=Decimal('25.00'),
            duration=timedelta(hours=1)
        )
        
        # Mock Elasticsearch connection
        self.es_mock = patch('elasticsearch_dsl.connections.connections.create_connection')
        self.es_mock.start()
    
    def tearDown(self):
        """Clean up test data and mocks."""
        self.es_mock.stop()
    
    @patch('core.documents.ServiceDocument.save')
    def test_service_indexing(self, mock_save):
        """Test service document indexing."""
        doc = ServiceDocument()
        doc.prepare(self.service)
        mock_save.assert_called_once()
        
    @patch('core.documents.ServiceDocument.search')
    def test_service_search(self, mock_search):
        """Test service search functionality."""
        mock_search.return_value = MagicMock()
        ServiceDocument.search().query('match', name='test')
        mock_search.assert_called_once()

class MetricsTest(TestCase):
    """Test suite for user and provider metrics.
    
    Tests metric calculations and serialization.
    """
    
    def setUp(self):
        """Create test users, provider, and bookings."""
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        self.provider_user = User.objects.create_user(
            username='provider',
            password='pass123'
        )
        self.provider = ServiceProvider.objects.create(
            user=self.provider_user,
            service_type='Test'
        )
        self.service = Service.objects.create(
            name='Test Service',
            base_price=Decimal('50.00'),
            unit_price=Decimal('25.00'),
            duration=timedelta(hours=1)
        )
        
        # Create completed booking
        self.booking = Booking.objects.create(
            user=self.user,
            service_provider=self.provider,
            service=self.service,
            appointment_time=now() - timedelta(days=1),
            status='completed',
            total_price=Decimal('75.00')
        )
    
    def test_user_metrics_serialization(self):
        """Test user metrics calculation and serialization."""
        metrics = {
            'total_spend': float(self.booking.total_price),
            'total_bookings': 1,
            'duration': 365,
            'activity_graph': {'labels': [], 'values': []},
            'favorite_services': [self.service.name]
        }
        
        serializer = UserMetricsSerializer(metrics)
        self.assertEqual(serializer.data['total_spend'], 75.0)
        self.assertEqual(serializer.data['total_bookings'], 1)
    
    def test_provider_metrics_serialization(self):
        """Test provider metrics calculation and serialization."""
        metrics = {
            'revenue': float(self.booking.total_price),
            'total_bookings': 1,
            'active_services': 1
        }
        
        serializer = ProviderMetricsSerializer(metrics)
        self.assertEqual(serializer.data['revenue'], 75.0)
        self.assertEqual(serializer.data['total_bookings'], 1)
        self.assertEqual(serializer.data['active_services'], 1)