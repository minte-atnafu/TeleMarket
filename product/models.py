from django.db import models
from django.db.models import Avg
from django.contrib.auth.models import User

class Product(models.Model):
    # Your existing fields
    id = models.CharField(max_length=255, primary_key=True)
    product_name = models.CharField(max_length=255)
    price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    username = models.CharField(max_length=255, null=True, blank=True)
    location = models.CharField(max_length=255, null=True, blank=True)
    media_path = models.TextField(null=True, blank=True)

    @property
    def average_rating(self):
        return self.ratings.aggregate(Avg('rating'))['rating__avg'] or 0

    @property
    def rating_count(self):
        return self.ratings.count()

    class Meta:
        db_table = 'TeleMarket'  # Your existing table
        managed = False  # Important for existing tables

class Rating(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='ratings')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    rating = models.IntegerField(choices=[(1, '1'), (2, '2'), (3, '3'), (4, '4'), (5, '5')])
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'product_rating'  #
        unique_together = ('product', 'user')
        app_label = 'product'