from django.shortcuts import render, get_object_or_404
from .models import Product
import os
from django.conf import settings
from django.utils.text import slugify

def product_list(request):
    products = Product.objects.all()

    for product in products:
        # Try by product ID first
        image_name = f"{product.id}.jpg"
        relative_path = f"product/photos/{image_name}"
        full_path = os.path.join(settings.MEDIA_ROOT, relative_path)

        if not os.path.exists(full_path):
            # Try slugified product name
            image_name = f"{slugify(product.product_name)}.jpg"
            relative_path = f"product/photos/{image_name}"
            full_path = os.path.join(settings.MEDIA_ROOT, relative_path)

            if not os.path.exists(full_path):
                relative_path = None  # image not found

        product.media_path = relative_path  # attach it either way

    context = {'products': products}
    return render(request, 'product/product_list.html', context)


def product_detail(request, product_id):
    product = get_object_or_404(Product, id=product_id)  # Fetch a single product by ID
    context = {'product': product}  # Pass the single product to the template
    return render(request, 'product/product_detail.html', context)
