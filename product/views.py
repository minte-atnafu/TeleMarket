from django.shortcuts import render, get_object_or_404
from .models import Product
import os
from django.conf import settings
from django.db.models import Q 
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from .models import Rating, Product
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_protect
from django.http import JsonResponse
import json
from .utils.telegram_username_mapper import get_telegram_username  # Import the mapper
from django.core.files.storage import default_storage
import urllib.parse
from urllib.parse import urlparse

def is_absolute_url(path):
    """Check if the path is a full URL"""
    try:
        result = urlparse(path)
        return all([result.scheme, result.netloc])
    except:
        return False


def product_list(request):
    products = Product.objects.all()
    
    for product in products:
        # Handle media paths (both full URLs and relative paths)
        if product.media_path:
            if is_absolute_url(product.media_path):
                # Case 1: Full URL (https://telemarket.s3.amazonaws.com/...)
                product.media_url = product.media_path
            else:
                # Case 2: Relative path (photos/@phonehub27_10105.jpg)
                try:
                    # Generate proper S3 URL from relative path
                    product.media_url = default_storage.url(product.media_path)
                except:
                    # Fallback if URL generation fails
                    product.media_url = settings.STATIC_URL + 'default1.jpg'
        else:
            # No media path available
            product.media_url = settings.STATIC_URL + 'default1.jpg'
    
    context = {'products': products}
    return render(request, 'product/product_list.html', context)

def product_detail(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    
    # Handle both URL formats
    if product.media_path:
        if is_absolute_url(product.media_path):
            # Case 1: Already a full S3 URL (https://telemarket.s3.amazonaws.com/...)
            product.media_url = product.media_path
        else:
            # Case 2: Relative path (photos/@phonehub27_10105.jpg)
            try:
                # Generate proper S3 URL from relative path
                product.media_url = default_storage.url(product.media_path)
            except:
                # Fallback if URL generation fails
                product.media_url = settings.STATIC_URL + 'default1.jpg'
    else:
        # No media path available
        product.media_url = settings.STATIC_URL + 'default1.jpg'
    
    # Get Telegram username
    telegram_username = get_telegram_username(product.username)
    
    context = {
        'product': product,
        'average_rating': product.average_rating,
        'rating_count': product.rating_count,
        'telegram_username': telegram_username,
    }
    return render(request, 'product/product_detail.html', context)
@require_POST
@csrf_protect
@login_required
def rate_product(request, product_id):
    try:
        # Parse the JSON data
        data = json.loads(request.body)
        rating_value = int(data.get('rating'))

        # Validate rating (1-5)
        if not 1 <= rating_value <= 5:
            return JsonResponse({'error': 'Rating must be between 1 and 5'}, status=400)

        # Get product
        product = Product.objects.get(id=product_id)

        # Save or update rating
        Rating.objects.update_or_create(
            product=product,
            user=request.user,
            defaults={'rating': rating_value}
        )

        # Return full rating info
        return JsonResponse({
            'success': True,
            'message': 'Rating saved successfully',
            'average_rating': product.average_rating,
            'rating_count': product.rating_count
        })

    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON data'}, status=400)
    except Product.DoesNotExist:
        return JsonResponse({'error': 'Product not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

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

