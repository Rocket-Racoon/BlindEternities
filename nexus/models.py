from django.db import models
from django.contrib.auth.models import User
from django.urls import reverse
from core.models import BaseModel
from core.utils import avatar_upload_path
from core.constants import MagicFormat

class Friendship(BaseModel):
    """Bidirectional friendship between two users."""
    from_user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="friendships_sent",
    )
    to_user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="friendships_received",
    )
    accepted = models.BooleanField(default=False)

    class Meta:
        verbose_name = "friendship"
        verbose_name_plural = "friendships"
        constraints = [
            models.UniqueConstraint(
                fields=["from_user", "to_user"],
                name="unique_friendship",
            )
        ]

    def __str__(self):
        status = "accepted" if self.accepted else "pending"
        return f"{self.from_user.username} → {self.to_user.username} ({status})"


class Profile(BaseModel):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="profile",
    )
    display_name = models.CharField(max_length=60, blank=True)
    avatar      = models.ImageField(
        upload_to=avatar_upload_path,
        blank=True,
        null=True,
    )
    bio              = models.TextField(max_length=500, blank=True)
    location         = models.CharField(max_length=100, blank=True)
    preferred_format = models.CharField(
        max_length=20,
        choices=MagicFormat.choices,
        blank=True,
        verbose_name='Preferred Format'
    )
    is_public = models.BooleanField(default=True)

    class Meta:
        verbose_name = "profile"
        verbose_name_plural = "profiles"

    def __str__(self):
        return f"{self.user.username} — profile"

    def get_absolute_url(self):
        return reverse("nexus:profile-detail", kwargs={"username": self.user.username})

    @property
    def name(self):
        return self.display_name or self.user.username

    def friends(self):
        """Return a queryset of Users who are accepted friends."""
        from django.db.models import Q
        friend_ids = Friendship.objects.filter(
            Q(from_user=self.user) | Q(to_user=self.user),
            accepted=True,
        ).values_list("from_user", "to_user")
        ids = set()
        for from_id, to_id in friend_ids:
            ids.add(from_id if from_id != self.user_id else to_id)
        return User.objects.filter(pk__in=ids)

    def friendship_with(self, other):
        """Return (state, friendship) for the pair (self.user, other).

        state ∈ {"self", "none", "pending_sent", "pending_received", "friends"}.
        """
        if other is None or not other.is_authenticated:
            return ("none", None)
        if other == self.user:
            return ("self", None)
        from django.db.models import Q
        fs = Friendship.objects.filter(
            Q(from_user=self.user, to_user=other)
            | Q(from_user=other, to_user=self.user)
        ).first()
        if fs is None:
            return ("none", None)
        if fs.accepted:
            return ("friends", fs)
        # Pending — direction is from the viewer's perspective (other).
        return ("pending_sent" if fs.from_user == other else "pending_received", fs)