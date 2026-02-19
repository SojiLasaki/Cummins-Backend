from django.db import models
from apps.customers.models import CustomerProfile
import uuid

class Asset(models.Model):

    ASSET_TYPE = (
        ("engine", "Engine"),
        ("generator", "Generator"),
        ('other', 'Other'),
        ("vehicle", "Vehicle"),
    )

    customer = models.ForeignKey(CustomerProfile, on_delete=models.CASCADE)
    asset_type = models.CharField(max_length=50, choices=ASSET_TYPE)
    product_id = models.CharField(max_length=10, unique=True, editable=False)
    serial_number = models.CharField(max_length=100)
    model_number = models.CharField(max_length=100)
    id = models.AutoField(primary_key=True, unique=True, editable=False, default=uuid.uuid4)


    def save(self, *args, **kwargs):
        if not self.product_id:
            last = Asset.objects.all().order_by('id').last()
            if last:
                last_id = int(last.product_id.replace('PROD', ''))
                self.product_id = f'PROD{last_id + 1:04d}'
            else:
                self.product_id = 'PROD0001'
        super().save(*args, **kwargs)

    def __str__(self):
        return self.product_id
