# core/mixins.py
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse


class OwnerRequiredMixin(LoginRequiredMixin):
    owner_field = "user"

    def dispatch(self, request, *args, **kwargs):
        obj = self.get_object()
        owner = getattr(obj, self.owner_field)
        if owner != request.user:
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)


class PublicProfileMixin:
    def dispatch(self, request, *args, **kwargs):
        profile = self.get_profile()
        if not profile.is_public and profile.user != request.user:
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def get_profile(self):
        raise NotImplementedError


class AjaxResponseMixin:
    def render_to_response(self, context, **kwargs):
        if self.request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse(self.get_ajax_data(context))
        return super().render_to_response(context, **kwargs)

    def get_ajax_data(self, context):
        raise NotImplementedError