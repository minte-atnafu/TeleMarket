from django.contrib import admin
from .models import Product,Rating  # Ensure this import exists
# Register your models here.

admin.site.register(Product)  # Ensure the model is registered

class RatingAdmin(admin.ModelAdmin):
    list_display = ('product', 'user', 'rating', 'created_at')
    list_filter = ('rating', 'created_at')
    search_fields = ('product__product_name', 'user__username')
    date_hierarchy = 'created_at'
admin.site.register(Rating, RatingAdmin)
