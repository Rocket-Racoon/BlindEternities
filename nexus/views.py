# nexus/views.py
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.models import User
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect
from django.views.generic import TemplateView, UpdateView, View
from django.urls import reverse_lazy
from .models import Profile
from .forms import ProfileForm


class HomeView(TemplateView):
    template_name = "nexus/home.html"


class ProfileDetailView(TemplateView):
    template_name = "nexus/profile_detail.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = get_object_or_404(User, username=self.kwargs["username"])
        profile = get_object_or_404(Profile, user=user)

        # Bloquea perfiles privados a visitantes
        if not profile.is_public and self.request.user != user:
            from django.core.exceptions import PermissionDenied
            raise PermissionDenied

        ctx["profile"] = profile
        ctx["profile_user"] = user
        ctx["is_owner"] = self.request.user == user
        return ctx


class ProfileEditView(LoginRequiredMixin, UpdateView):
    model         = Profile
    form_class    = ProfileForm
    template_name = "nexus/profile_edit.html"
    success_url   = reverse_lazy("nexus:profile-edit")

    def get_object(self, queryset=None):
        return self.request.user.profile

    def form_valid(self, form):
        messages.success(self.request, "Perfil actualizado correctamente.")
        return super().form_valid(form)


class AvatarUploadView(LoginRequiredMixin, View):
    def post(self, request):
        profile = request.user.profile
        if "avatar" in request.FILES:
            profile.avatar = request.FILES["avatar"]
            profile.save(update_fields=["avatar", "updated_at"])
            messages.success(request, "Avatar actualizado.")
        return redirect("nexus:profile-edit")


class UserDecksView(TemplateView):
    template_name = "nexus/user_decks.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = get_object_or_404(User, username=self.kwargs["username"])
        profile = get_object_or_404(Profile, user=user)
        if not profile.is_public and self.request.user != user:
            from django.core.exceptions import PermissionDenied
            raise PermissionDenied
        ctx["profile"] = profile
        ctx["profile_user"] = user
        ctx["is_owner"] = self.request.user == user
        return ctx


class UserCollectionView(TemplateView):
    template_name = "nexus/user_collection.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = get_object_or_404(User, username=self.kwargs["username"])
        profile = get_object_or_404(Profile, user=user)
        if not profile.is_public and self.request.user != user:
            from django.core.exceptions import PermissionDenied
            raise PermissionDenied
        ctx["profile"] = profile
        ctx["profile_user"] = user
        ctx["is_owner"] = self.request.user == user
        return ctx