from django.shortcuts import render, redirect
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import login
from django.contrib.auth.forms import AuthenticationForm

from django.contrib.auth.models import User
from .forms import CustomSignupForm
from django.contrib import messages
from django.contrib.auth import authenticate

from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings
from django.contrib.sites.shortcuts import get_current_site
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.contrib.auth.tokens import default_token_generator
from django.http import HttpResponse

from django.core.cache import cache  # Add this import
import random
import time
from django.contrib.auth import get_user_model
from django.contrib.auth import login as auth_login  # Renamed to avoid conflict

# Create your views here.

def home(request):
    return render(request, 'base/home.html')

def signup(request):
    if request.method == 'POST':
        form = CustomSignupForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data['username']
            email = form.cleaned_data['email']
            password = form.cleaned_data['password1']

            # Create the user
            user = User.objects.create_user(username=username, email=email, password=password)

            # Log the user in immediately after creation
            login(request, user, backend='django.contrib.auth.backends.ModelBackend')

            # Send Welcome Email
            subject = "Welcome to Our Platform!"
            context = {'user': user}  # Pass user object to template
            
            # Corrected path to email template
            html_message = render_to_string('base/welcome_email.html', context)
            plain_message = strip_tags(html_message)  # Convert HTML to plain text
            
            
            result = send_mail(
                subject,
                plain_message,  # Plain text version
                settings.DEFAULT_FROM_EMAIL,
                [email],
                html_message=html_message,  # HTML version
                fail_silently=False,
            )
            print(f"Send mail result: {result}")

            # Redirect to home page or another page after successful signup
            return redirect('home')
        else:
            return render(request, 'base/signup.html', {'form': form})

    else:
        form = CustomSignupForm()

    return render(request, 'base/signup.html', {'form': form})

def user_login(request):
    if request.method == 'POST':
        email = request.POST.get('email')  # Get email from the form
        password = request.POST.get('password')  # Get password from the form

        # Validate email and password
        if not email or not password:
            messages.error(request, "Please provide both email and password.")
            return redirect('login')  # Redirect back to the login page

        try:
            # Find the user by email
            user = User.objects.get(email=email)
            
            # Authenticate the user using the username
            authenticated_user = authenticate(request, username=user.username, password=password)
            
            if authenticated_user is not None:
                # If authentication is successful, log the user in
                login(request, authenticated_user)
                return redirect('home')
            else:
                # If authentication fails, show an error message
                messages.error(request, "Invalid email or password.")
                return redirect('login')  # Redirect back to the login page
         
        except User.DoesNotExist:
            # If no user is found with the provided email
            messages.error(request, "No user found with this email.")
            return redirect('login')  # Redirect back to the login page
    
    else:
        # Render the login form for GET requests
        return render(request, 'base/login.html')





User = get_user_model()
CODE_EXPIRY = 300  # 5 minutes in seconds

def forgot_password_view(request):
    if request.method == 'POST':
        try:
            email = request.POST.get('email', '').lower().strip()
            
            if not email:
                messages.error(request, "Email is required.")
                return render(request, 'base/forgot_password.html')
            
            # Always return success message (security best practice)
            user_exists = User.objects.filter(email=email).exists()
            if not user_exists:
                print(f"Debug: Email {email} not found in database")  # Debug
                messages.success(request, "If this email exists, you'll receive a recovery code.")
                return redirect('forgot_password')
            
            # Generate and store code
            recovery_code = str(random.randint(100000, 999999))
            cache_key = f"pw_reset_{email}"
            
            # Store in cache
            cache.set(cache_key, {
                'code': recovery_code,
                'timestamp': time.time(),
                'attempts': 0
            }, CODE_EXPIRY)
            print(f"Debug: Code {recovery_code} cached for {email}")  # Debug
            
            # Store email in session
            request.session['reset_email'] = email
            request.session.modified = True
            print(f"Debug: Session set for {email}")  # Debug
            
            # Send email (with error handling)
            try:
                send_mail(
                    'Your Password Recovery Code',
                    f'Your verification code is: {recovery_code}',
                    settings.DEFAULT_FROM_EMAIL,
                    [email],
                    fail_silently=False,
                )
                print(f"Debug: Email sent to {email}")  # Debug
            except Exception as e:
                print(f"Error sending email: {e}")
                messages.error(request, "Failed to send email. Please try again.")
                return redirect('forgot_password')
            
            messages.success(request, "Recovery code sent! Check your email.")
            return redirect('recovery')  # This should be your recovery page
            
        except Exception as e:
            print(f"System error: {e}")
            messages.error(request, "A system error occurred. Please try again.")
            return redirect('forgot_password')
    
    # GET request - clear any existing session
    if 'reset_email' in request.session:
        del request.session['reset_email']
    return render(request, 'base/forgot_password.html')

def recovery_view(request):
    if 'reset_email' not in request.session:
        return redirect('forgot_password')
    
    email = request.session['reset_email']
    
    if request.method == 'POST':
        # Combine all code inputs
        code_entered = ''.join([
            request.POST.get('code1', ''),
            request.POST.get('code2', ''),
            request.POST.get('code3', ''),
            request.POST.get('code4', ''),
            request.POST.get('code5', ''),
            request.POST.get('code6', '')
        ])
        
        cache_key = f"pw_reset_{email}"
        stored_data = cache.get(cache_key)
        
        if stored_data and stored_data['code'] == code_entered:
            request.session['code_verified'] = True
            return redirect('set_password')
        else:
            messages.error(request, "Invalid or expired recovery code.")
    
    return render(request, 'base/recovery.html', {
        'email': request.session.get('reset_email', '')
    })
def set_password_view(request):
    # Verify proper flow
    if 'reset_email' not in request.session or not request.session.get('code_verified'):
        messages.error(request, "Please complete verification first.")
        return redirect('forgot_password')
    
    email = request.session['reset_email']
    
    if request.method == 'POST':
        new_password = request.POST.get('new_password')
        confirm_password = request.POST.get('confirm_password')
        
        # Basic password validation
        if new_password != confirm_password:
            messages.error(request, "Passwords don't match.")
        elif len(new_password) < 8:
            messages.error(request, "Password must be at least 8 characters.")
        else:
            try:
                user = User.objects.get(email=email)
                user.set_password(new_password)
                user.save()
                
                # Automatically log the user in
                auth_login(request, user, backend='django.contrib.auth.backends.ModelBackend')  # This logs them in
                
                # Clean up session and cache
                cache.delete(f"pw_reset_{email}")
                del request.session['reset_email']
                del request.session['code_verified']
                
                messages.success(request, "Password reset successfully!")
                return redirect('home')  # Now redirects to home page
            except User.DoesNotExist:
                messages.error(request, "User not found.")
    
    return render(request, 'base/set_password.html')
# def forgot_password_view(request):
#     return render(request, 'base/forgot_password.html')

# def recovery_view(request):
#     return render(request, 'base/recovery.html')

# def set_password_view(request):
#     return render(request, 'base/set_password.html')