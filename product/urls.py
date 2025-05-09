from django.urls import path
from .views import product_list,product_detail
from django.conf import settings
from django.conf.urls.static import static
from .views import product_search 
urlpatterns = [
    path('', product_list, name='product_list'),
    path('<int:product_id>/', product_detail, name='product_detail'),
    path('search/', product_search, name='product_search'),
]
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)