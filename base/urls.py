from django.urls import path
from .views import (
    home, 
    signup, 
    user_login, 
    forgot_password_view, 
    recovery_view,
    set_password_view,
    contact_view,
    logout_view
)

urlpatterns = [
    # Core auth URLs
    path('', home, name='home'),
    path('signup/', signup, name='signup'),
    path('login/', user_login, name='login'),
    path('contact/', contact_view, name='contact'),
    path('logout/',logout_view, name='logout' ),

    
    # Custom Password Reset Flow
    path('forgot-password/', forgot_password_view, name='forgot_password'),
    path('recovery/', recovery_view, name='recovery'),  # Code verification
    path('set-password/', set_password_view, name='set_password'),
]