from django_elasticsearch_dsl import Document, fields
from django_elasticsearch_dsl.registries import registry
from django.conf import settings
from .models import Service
from drf_spectacular.utils import extend_schema_field
from drf_spectacular.types import OpenApiTypes

@registry.register_document
class ServiceDocument(Document):
    """Document class for indexing Service model in Elasticsearch."""
    name = fields.TextField(attr='name', analyzer='standard')
    description = fields.TextField(attr='description', analyzer='standard')
    base_price = fields.FloatField(attr='base_price')
    unit_price = fields.FloatField(attr='unit_price')
    category = fields.KeywordField(attr='category.name')
    languages = fields.KeywordField(multi=True)
    is_active = fields.BooleanField(attr='is_active')
    duration = fields.LongField(attr='duration')  # Map duration field as long (milliseconds)
    
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
        
    def prepare_languages(self, instance):
        """Prepare available languages for the service."""
        return instance.available_languages if hasattr(instance, 'available_languages') else [settings.LANGUAGE_CODE]

    def prepare_duration(self, instance):
        """Convert Django DurationField to milliseconds for Elasticsearch."""
        if instance.duration:
            return int(instance.duration.total_seconds() * 1000)
        return None