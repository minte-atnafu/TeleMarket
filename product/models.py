from django.db import models # type: ignore


class Product(models.Model):
    id = models.CharField(max_length=255, primary_key=True)  # Match DB column type
    product_name = models.CharField(max_length=255)  # Match DB column
    price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    username = models.CharField(max_length=255, null=True, blank=True)
    location = models.CharField(max_length=255, null=True, blank=True)
    media_path = models.TextField(null=True, blank=True)  # Match DB column

    class Meta:
        db_table = 'TeleMarket'  # Make sure it matches the existing table name
        app_label = 'product'  # Needed for the database router
