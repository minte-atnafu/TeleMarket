from django.shortcuts import render

# Create your views here.
from django.contrib.auth.decorators import login_required
from django.shortcuts import render

@login_required
def profile_view(request):
    user = request.user
    context = {
        'user': user,
        'date_joined': user.date_joined.strftime("%B %d, %Y"),
    }
    return render(request, 'users/profile.html', context)  # Note template path