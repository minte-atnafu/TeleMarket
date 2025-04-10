from django.shortcuts import render, get_object_or_404
from .models import Product
import os
from django.conf import settings

def product_list(request):
    products = Product.objects.all()

    for product in products:
        # Use the media_path column directly from the database
        relative_path = product.media_path
        full_path = os.path.join(settings.MEDIA_ROOT, relative_path) if relative_path else None

        if not relative_path or not os.path.exists(full_path):
            # If media_path is missing or the file doesn't exist, set a default image
            relative_path = "photos/default.jpg"

        product.media_path = relative_path  # Ensure media_path is set correctly

    context = {'products': products}
    return render(request, 'product/product_list.html', context)


def product_detail(request, product_id):
    product = get_object_or_404(Product, id=product_id)

    # Debugging: Print the media path and full path
    if product.media_path:
        relative_path = product.media_path
        full_path = os.path.join(settings.MEDIA_ROOT, product.media_path)
        print(f"Media Path: {product.media_path}")
        print(f"Full Path: {full_path}")
        if not os.path.exists(full_path):
            product.media_path = "photos/default.jpg"

    context = {'product': product}
    return render(request, 'product/product_detail.html', context)