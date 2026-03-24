from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404
from .models import Collection, Deck

class CollectionOwnerMixin(LoginRequiredMixin):
    """Verifica que el usuario es dueño de la colección."""
    def get_collection(self):
        return get_object_or_404(Collection, pk=self.kwargs["pk"])

    def dispatch(self, request, *args, **kwargs):
        collection = self.get_collection()
        if collection.user != request.user:
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)


class DeckOwnerMixin(LoginRequiredMixin):
    """Verifica que el usuario es dueño del deck."""
    def get_deck(self):
        return get_object_or_404(Deck, pk=self.kwargs["pk"])

    def dispatch(self, request, *args, **kwargs):
        deck = self.get_deck()
        if deck.user != request.user:
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)