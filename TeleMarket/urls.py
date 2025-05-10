"""
URL configuration for TeleMarket project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path,include
from django.conf import settings
from django.conf.urls.static import static
from django.http import HttpResponse

def show_urls(request):
    from django.urls import get_resolver
    urls = []
    for url_pattern in get_resolver().url_patterns:
        urls.append(str(url_pattern))
    return HttpResponse('<pre>' + '\n'.join(urls) + '</pre>')




urlpatterns = [
    path('urls-debug/', show_urls),  # Add this temporary route
    path('admin/', admin.site.urls),
    path('product/', include('product.urls')),
    path('', include('base.urls')),
    path("accounts/", include("allauth.urls")),
     path('users/', include('users.urls')),
   
    # path('accounts/', include('django.contrib.auth.urls')),  # Make sure this is included
]


urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
