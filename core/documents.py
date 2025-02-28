from django_elasticsearch_dsl import Document, fields
from django_elasticsearch_dsl.registries import registry
from django.conf import settings

from .models import Service

@registry.register_document
class ServiceDocument(Document):
    """
    Document class for indexing Service model in Elasticsearch.
    """
    name = fields.TextField(analyzer='standard')
    description = fields.TextField(analyzer='standard')
    base_price = fields.FloatField()
    unit_price = fields.FloatField()
    category = fields.KeywordField(attr='category.name')
    is_active = fields.BooleanField()
    duration = fields.LongField()  # Duration in milliseconds

    class Index:
        name = 'services'
        settings = {
            'number_of_shards': 1,
            'number_of_replicas': 0
        }

    class Django:
        model = Service
        fields = [
            'id',
        ]

    def prepare_duration(self, instance):
        """
        Convert Django DurationField to milliseconds for Elasticsearch.
        """
        if instance.duration:
            return int(instance.duration.total_seconds() * 1000)
        return None