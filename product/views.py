from django.shortcuts import render, get_object_or_404
from .models import Product
import os
from django.conf import settings
from django.db.models import Q 

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
        full_path = os.path.join(settings.MEDIA_ROOT, relative_path) if relative_path else None

        print(f"Media Path: {product.media_path}")
        print(f"Full Path: {full_path}")
       
        if not relative_path or not os.path.exists(full_path):
            # If media_path is missing or the file doesn't exist, set a default image
            relative_path = "photos/default.jpg"

        product.media_path = relative_path

    # ✅ Add MEDIA_URL to the context
    context = {
        'product': product,
        'MEDIA_URL': settings.MEDIA_URL,
    }

    return render(request, 'product/product_detail.html', context)

def product_search(request):
    query = request.GET.get('q', '')
    min_price = request.GET.get('min_price')
    max_price = request.GET.get('max_price')
    location = request.GET.get('location', '')
    
    products = Product.objects.all()
    
    if query:
        products = products.filter(
            Q(product_name__icontains=query) |
            Q(username__icontains=query) |
            Q(location__icontains=query)
        )
    
    # Handle price filtering safely
    try:
        if min_price:
            products = products.filter(price__gte=float(min_price))
    except (ValueError, TypeError):
        pass
    
    try:
        if max_price:
            products = products.filter(price__lte=float(max_price))
    except (ValueError, TypeError):
        pass
    
    if location:
        products = products.filter(location__icontains=location)
    
    context = {
        'products': products,
        'search_query': query,
        'min_price': min_price,
        'max_price': max_price,
        'location': location,
    }
    return render(request, 'product/search_results.html', context)
