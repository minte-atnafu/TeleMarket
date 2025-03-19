from django.urls import path
from .views import product_list,product_detail

urlpatterns = [
    path('', product_list, name='product_list'),
    path('<int:product_id>/', product_detail, name='product_detail'),
]
