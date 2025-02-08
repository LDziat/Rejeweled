from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.http import JsonResponse

def signup_view(request):
    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")
        
        if User.objects.filter(username=username).exists():
            return JsonResponse({"error": "Username already taken"}, status=400)
        
        user = User.objects.create_user(username=username, password=password)
        login(request, user)
        return redirect("game_home")        #JsonResponse({"message": "Signup successful", "username": user.username})
    
    return render(request, "account/signup.html")  # Render signup form

def login_view(request):
    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")
        user = authenticate(request, username=username, password=password)
        
        if user:
            login(request, user)
            return redirect("game_home")
        else:
            return redirect("login")

    return render(request, "account/login.html")  # Render login form

@login_required
def logout_view(request):
    logout(request)
    return redirect("game_home")

#@login_required
def index(request):
    return render(request, "game/index.html", {"username": request.user.username})

