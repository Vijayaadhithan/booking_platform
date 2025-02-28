# test_search_and_metrics.py

from django.test import TestCase
from django.utils.timezone import now, timedelta
from unittest.mock import patch, MagicMock
from decimal import Decimal

from .models import User, Service, ServiceProvider, Booking, ServiceCategory
from .documents import ServiceDocument
from .analytics import get_top_providers, analyze_feedback

class SearchIntegrationTest(TestCase):
    """
    Tests Elasticsearch integration for service indexing.
    """
    def setUp(self):
        self.category = ServiceCategory.objects.create(name='Test Category')
        self.service = Service.objects.create(
            name='Test Service',
            description='Test Desc',
            category=self.category,
            base_price=Decimal('50.00'),
            unit_price=Decimal('25.00'),
            duration=timedelta(hours=1)
        )

    @patch('core.tasks.update_search_index.delay')
    def test_service_indexing(self, mock_index_task):
        self.service.save()
        mock_index_task.assert_called_once_with(self.service.id)

    @patch('core.documents.ServiceDocument.search')
    def test_service_search(self, mock_search):
        # mock the search call
        mock_search.return_value = MagicMock()
        ServiceDocument.search().query('match', name='test')
        mock_search.assert_called_once()


class MetricsTest(TestCase):
    """
    Tests for user/provider analytics using analytics.py functions.
    """
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='testpass123')
        self.provider_user = User.objects.create_user(username='provider', password='pass123')
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

        # Completed booking
        self.booking = Booking.objects.create(
            user=self.user,
            service_provider=self.provider,
            service=self.service,
            appointment_time=now() - timedelta(days=1),
            status='completed',
            payment_status='paid',
            total_price=Decimal('75.00')
        )

    def test_get_top_providers(self):
        providers = get_top_providers(limit=5, period_days=30)
        self.assertIn(self.provider, providers)
        self.assertGreaterEqual(len(providers), 1)

    def test_analyze_feedback(self):
        from core.models import Review
        review = Review.objects.create(
            user=self.user,
            service_provider=self.provider,
            rating=5,
            booking=self.booking
        )
        result = analyze_feedback(provider_id=self.provider.id, period_days=30)
        self.assertEqual(result['avg_rating'], 5)
        self.assertEqual(result['total_reviews'], 1)
