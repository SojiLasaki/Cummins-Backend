from django.db import models
import uuid
# Create your models here.

class Component(models.Model):
    GROUPS = (
        ('engine', 'ENGINE'),
        ('generators', 'GENERATORS'),
        ('electrical', 'ELECTRICAL'),
        ('transmissions', 'TRANSMISSIONS'),
    )
    group = models.CharField(max_length=50, choices=GROUPS)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    def __str__(self):
        return self.name
    

class Part(models.Model):
    STATUS = (
        ('in_stock', 'In Stock'),
        ('out_of_stock', 'Out of Stock'),
        ('discontinued', 'Discontinued'),
        ('backordered', 'Backordered'),
    )
    CATEGORY = (
        ('engine', 'ENGINE'),
        ('generators', 'GENERATORS'),
        ('electrical', 'ELECTRICAL'),
        ('transmissions', 'TRANSMISSIONS'),
        ('other', 'OTHER'),
    )
    component = models.ForeignKey(Component, on_delete=models.CASCADE, related_name='parts')
    part_number = models.CharField(max_length=100, unique=True)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    quantity_available = models.IntegerField(default=0)
    reorder_threshold = models.IntegerField(default=5)
    category = models.CharField(max_length=50, choices=CATEGORY, default='other')
    weight_kg = models.IntegerField(null=True, blank=True) 
    cost_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    resale_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS, default='in_stock')
    supplier = models.CharField(max_length=255)
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    inventory_deducted = models.BooleanField(default=False)

    def __str__(self):
        return self.part_number + " - " + self.name


class InventoryTransaction(models.Model):

    TRANSACTION_TYPE = (
        ("addition", "Addition"),
        ("removal", "Removal"),
    )

    part = models.ForeignKey(Part, on_delete=models.CASCADE)
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPE)
    quantity = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    def __str__(self):
        return f"{self.transaction_type} of {self.quantity} for {self.part.part_number}"
    