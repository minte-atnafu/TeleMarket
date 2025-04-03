from django.shortcuts import render, get_object_or_404
from .models import Product

def product_list(request):
    products = Product.objects.all()  # Fetch all products
    context = {'products': products}  # Pass products to the template
    return render(request, 'product/product_list.html', context)

def product_detail(request, product_id):
    product = get_object_or_404(Product, id=product_id)  # Fetch a single product by ID
    context = {'product': product}  # Pass the single product to the template
    return render(request, 'product/product_detail.html', context)
