# core/models.py
import uuid
from django.db import models


class BaseModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        abstract = True
        ordering = ["-created_at"]

    def soft_delete(self):
        self.is_active = False
        self.save(update_fields=["is_active", "updated_at"])

    def restore(self):
        self.is_active = True
        self.save(update_fields=["is_active", "updated_at"])


class ActiveManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(is_active=True)
    
    
class CreatureType(BaseModel):
    """
    Catálogo dinámico de subtipos de criatura.
    Se sincroniza vía Scryfall /catalog/creature-types
    para evitar mantenimiento manual.
    """
    name = models.CharField(max_length=100, unique=True, db_index=True)

    class Meta:
        ordering        = ["name"]
        verbose_name    = "creature type"
        verbose_name_plural = "creature types"

    def __str__(self):
        return self.name