from django.db import models
from django.contrib.auth.models import User
from django.urls import reverse
from core.models import BaseModel
from core.utils import avatar_upload_path
from core.constants import MAGIC_FORMATS

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
        choices=MAGIC_FORMATS,
        blank=True,
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