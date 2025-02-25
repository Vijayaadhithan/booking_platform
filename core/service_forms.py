from django.db import models
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from .models import Service, ServiceCategory

class ServiceFormField(models.Model):
    """Model to define custom fields for service-specific forms."""
    service = models.ForeignKey(Service, on_delete=models.CASCADE, related_name='form_fields')
    field_name = models.CharField(max_length=100)
    field_type = models.CharField(
        max_length=20,
        choices=[
            ('text', 'Text Input'),
            ('number', 'Number Input'),
            ('file', 'File Upload'),
            ('select', 'Select Options'),
            ('date', 'Date Input'),
            ('time', 'Time Input')
        ]
    )
    required = models.BooleanField(default=False)
    options = models.JSONField(null=True, blank=True)  # For select fields
    validation_rules = models.JSONField(null=True, blank=True)
    help_text = models.TextField(blank=True)
    order = models.IntegerField(default=0)
    
    class Meta:
        ordering = ['order']

    def clean(self):
        if self.field_type == 'select' and not self.options:
            raise ValidationError({
                'options': _('Options are required for select fields')
            })

class ServiceFormSubmission(models.Model):
    """Model to store form submissions for services."""
    service = models.ForeignKey(Service, on_delete=models.CASCADE)
    booking = models.OneToOneField('Booking', on_delete=models.CASCADE)
    form_data = models.JSONField()
    files = models.JSONField(null=True, blank=True)  # Store file paths
    submitted_at = models.DateTimeField(auto_now_add=True)
    
    def validate_submission(self):
        """Validate form submission against field requirements."""
        required_fields = self.service.form_fields.filter(required=True)
        for field in required_fields:
            if field.field_name not in self.form_data:
                raise ValidationError(f'{field.field_name} is required')
            
            # Validate field type constraints
            value = self.form_data[field.field_name]
            if field.validation_rules:
                self._validate_field(field, value)
    
    def _validate_field(self, field, value):
        """Apply validation rules to a specific field value."""
        rules = field.validation_rules
        
        if field.field_type == 'number':
            try:
                num_value = float(value)
                if 'min' in rules and num_value < rules['min']:
                    raise ValidationError(f'{field.field_name} must be at least {rules["min"]}')
                if 'max' in rules and num_value > rules['max']:
                    raise ValidationError(f'{field.field_name} must be at most {rules["max"]}')
            except ValueError:
                raise ValidationError(f'{field.field_name} must be a number')
        
        elif field.field_type == 'text':
            if 'min_length' in rules and len(value) < rules['min_length']:
                raise ValidationError(f'{field.field_name} must be at least {rules["min_length"]} characters')
            if 'max_length' in rules and len(value) > rules['max_length']:
                raise ValidationError(f'{field.field_name} must be at most {rules["max_length"]} characters')
        
        elif field.field_type == 'select' and value not in field.options:
            raise ValidationError(f'Invalid option for {field.field_name}')

def get_form_config(service_id):
    """Get the form configuration for a specific service."""
    service = Service.objects.get(id=service_id)
    fields = service.form_fields.all()
    
    return {
        'service_name': service.name,
        'fields': [{
            'name': field.field_name,
            'type': field.field_type,
            'required': field.required,
            'options': field.options,
            'help_text': field.help_text,
            'validation_rules': field.validation_rules
        } for field in fields]
    }