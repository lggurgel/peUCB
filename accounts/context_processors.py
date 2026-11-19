def account(request):
    profile = None
    user = getattr(request, "user", None)
    if user is not None and user.is_authenticated:
        profile = getattr(user, "profile", None)
    return {"profile": profile}
