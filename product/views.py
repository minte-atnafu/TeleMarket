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

    # Handle media path
    if product.media_path:
        relative_path = product.media_path
        full_path = os.path.join(settings.MEDIA_ROOT, relative_path) if relative_path else None
        
        if not relative_path or not os.path.exists(full_path):
            relative_path = "photos/default.jpg"
        product.media_path = relative_path

    context = {
        'product': product,
        'MEDIA_URL': settings.MEDIA_URL,
        # These will now use the properties we defined in the model
        'average_rating': product.average_rating,
        'rating_count': product.rating_count,
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
            
        # Get product and save rating (example)
        product = Product.objects.get(id=product_id)
        Rating.objects.create(
            product=product,
            user=request.user,
            rating=rating_value
        )
        
        return JsonResponse({
            'success': True,
            'message': 'Rating saved successfully',
            'rating': rating_value
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

