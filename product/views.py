from django.shortcuts import render, get_object_or_404
from .models import Product
# Create your views here.

def product_list(request):
    products=Product.objects.all()
    rating_range = range(1, 6)
    context={'products':products, 'rating_rage':rating_range}
    return render(request, 'product/product_list.html',context)

# single product detail shown here

def product_detail(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    context={'product': product}
    return render(request, 'product/product_detail.html',context)