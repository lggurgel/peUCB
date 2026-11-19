from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from accounts.forms import ProfileForm, SignupForm


@require_http_methods(["GET", "POST"])
def signup(request):
    if request.user.is_authenticated:
        return redirect("home")
    form = SignupForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        profile = form.save()
        login(request, profile.user)
        return redirect("home")
    return render(request, "accounts/signup.html", {"form": form})


@login_required
@require_http_methods(["GET", "POST"])
def profile_edit(request):
    profile = request.user.profile
    form = ProfileForm(request.POST or None, instance=profile)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Perfil salvo.")
        return redirect("profile")
    return render(request, "accounts/profile.html", {"form": form})
