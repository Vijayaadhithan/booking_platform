from django_elasticsearch_dsl import Document
from django_elasticsearch_dsl.registries import registry
from .models import Service

@registry.register_document
class ServiceDocument(Document):
    class Index:
        name = 'services'
        settings = {'number_of_shards': 1,
                    'number_of_replicas': 0}

    class Django:
        model = Service
        fields = [
            'name',
            'description',
        ]