# nexus/views.py
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.models import User
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db import models
from django.db.models import Count, Sum, Q
from django.http import HttpResponseBadRequest, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from django.views.generic import TemplateView, UpdateView, View
from django.urls import reverse, reverse_lazy
from tolarian.models import Collection, Deck, DeckZone
from .models import Friendship, Profile
from .forms import ProfileForm


def _visible_decks(profile_user, viewer):
    qs = (
        Deck.objects
        .filter(user=profile_user, is_active=True)
        .annotate(card_count=Sum("cards__quantity", filter=~Q(cards__zone=DeckZone.EXTRAS)))
        .select_related("cover_card__cardset", "cover_card__card")
        .order_by("-updated_at")
    )
    if viewer != profile_user:
        qs = qs.filter(is_public=True)
    return qs


def _visible_collections(profile_user, viewer):
    qs = (
        Collection.objects
        .filter(user=profile_user, is_active=True)
        .annotate(
            item_count=Count("items"),
            total_qty=Sum("items__quantity"),
        )
        .select_related("cover_card__cardset", "cover_card__card")
        .order_by("collection_type", "name")
    )
    if viewer != profile_user:
        qs = qs.filter(is_public=True)
    return qs


def _get_profile_context(request, username):
    """Helper compartido para vistas de perfil."""
    user = get_object_or_404(User, username=username)
    profile = get_object_or_404(Profile, user=user)
    if not profile.is_public and request.user != user:
        raise PermissionDenied
    state, friendship = profile.friendship_with(request.user)
    ctx = {
        "profile":      profile,
        "profile_user": user,
        "is_owner":     request.user == user,
        "friend_state": state,
        "friendship":   friendship,
    }
    if request.user == user:
        ctx["incoming_requests"] = (
            Friendship.objects.filter(to_user=user, accepted=False)
            .select_related("from_user__profile")
            .order_by("-created_at")
        )
        ctx["friends_list"] = profile.friends().select_related("profile")
    return ctx


class HomeView(TemplateView):
    template_name = "nexus/home.html"


class ProfileDetailView(TemplateView):
    template_name = "nexus/profile_detail.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(_get_profile_context(self.request, self.kwargs["username"]))
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


# --- Friend actions ---
@login_required
@require_POST
def friend_action(request, username, action):
    target = get_object_or_404(User, username=username)
    if target == request.user:
        return HttpResponseBadRequest("Cannot befriend yourself.")

    profile = get_object_or_404(Profile, user=target)
    state, friendship = profile.friendship_with(request.user)

    if action == "send":
        if state != "none":
            return HttpResponseBadRequest("Friendship already exists.")
        Friendship.objects.create(from_user=request.user, to_user=target)
        messages.success(request, f"Friend request sent to {profile.name}.")

    elif action == "cancel":
        if state != "pending_sent":
            return HttpResponseBadRequest("No pending request to cancel.")
        friendship.delete()
        messages.info(request, "Request cancelled.")

    elif action == "accept":
        if state != "pending_received":
            return HttpResponseBadRequest("No pending request to accept.")
        friendship.accepted = True
        friendship.save(update_fields=["accepted", "updated_at"])
        messages.success(request, f"You and {profile.name} are now friends.")

    elif action == "reject":
        if state != "pending_received":
            return HttpResponseBadRequest("No pending request to reject.")
        friendship.delete()
        messages.info(request, "Request rejected.")

    elif action == "remove":
        if state != "friends":
            return HttpResponseBadRequest("Not friends.")
        friendship.delete()
        messages.info(request, f"Removed {profile.name} from friends.")

    else:
        return HttpResponseBadRequest("Unknown action.")

    if request.headers.get("HX-Request"):
        # Re-render the Friends card (used on the viewer's own profile) or the
        # single button partial (used on the target's profile header).
        if request.POST.get("return") == "card":
            return render(
                request,
                "nexus/partials/friends_card.html",
                {
                    "profile_user": request.user,
                    "incoming_requests": (
                        Friendship.objects.filter(to_user=request.user, accepted=False)
                        .select_related("from_user__profile")
                        .order_by("-created_at")
                    ),
                    "friends_list": request.user.profile.friends().select_related("profile"),
                },
            )
        new_state, new_fs = profile.friendship_with(request.user)
        return render(
            request,
            "nexus/partials/friend_action.html",
            {
                "profile": profile,
                "profile_user": target,
                "friend_state": new_state,
                "friendship": new_fs,
            },
        )
    return redirect("nexus:profile-detail", username=target.username)


# --- API JSON ---
class FriendSearchJSON(LoginRequiredMixin, View):
    """Return friends matching a name query for autocomplete."""

    def get(self, request):
        q = request.GET.get("q", "").strip()
        if len(q) < 1:
            return JsonResponse([], safe=False)

        friends = request.user.profile.friends()
        matches = friends.filter(
            models.Q(username__icontains=q)
            | models.Q(profile__display_name__icontains=q)
        ).select_related("profile")[:10]

        results = [
            {
                "id": u.pk,
                "username": u.username,
                "display_name": u.profile.name if hasattr(u, "profile") else u.username,
                "avatar": u.profile.avatar.url if hasattr(u, "profile") and u.profile.avatar else "",
            }
            for u in matches
        ]
        return JsonResponse(results, safe=False)


class UserDecksJSON(LoginRequiredMixin, View):
    """Return active decks for a user. Own decks always; friend's public decks only."""

    def get(self, request, user_id):
        from tolarian.models import Deck

        target = get_object_or_404(User, pk=user_id)
        qs = Deck.objects.filter(user=target, is_active=True).order_by("name")
        if target != request.user:
            qs = qs.filter(is_public=True)

        results = [
            {
                "id": str(d.pk),
                "name": d.name,
                "format": d.get_format_display(),
            }
            for d in qs
        ]
        return JsonResponse(results, safe=False)


# --- Parciales HTMX ---
class UserOverviewPartialView(TemplateView):
    template_name = "nexus/partials/overview.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(_get_profile_context(self.request, self.kwargs["username"]))
        profile_user = ctx["profile_user"]
        viewer = self.request.user
        ctx["deck_count"] = _visible_decks(profile_user, viewer).count()
        ctx["collection_count"] = _visible_collections(profile_user, viewer).count()
        return ctx


class UserDecksPartialView(TemplateView):
    template_name = "nexus/partials/decks.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(_get_profile_context(self.request, self.kwargs["username"]))
        ctx["decks"] = _visible_decks(ctx["profile_user"], self.request.user)
        return ctx


class UserCollectionPartialView(TemplateView):
    template_name = "nexus/partials/collection.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(_get_profile_context(self.request, self.kwargs["username"]))
        ctx["collections"] = _visible_collections(ctx["profile_user"], self.request.user)
        return ctx