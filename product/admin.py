from django.contrib import admin
from .models import Product  # Ensure this import exists
# Register your models here.

admin.site.register(Product)  # Ensure the model is registered
