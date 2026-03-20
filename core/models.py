# core/models.py
import uuid
from django.db import models
from django.utils.text import slugify
from core.constants import MechanicType

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
    name      = models.CharField(max_length=100, unique=True, db_index=True)
    slug      = models.SlugField(max_length=100, unique=True, db_index=True, blank=True, default="")
    synced_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering        = ["name"]
        verbose_name    = "creature type"
        verbose_name_plural = "creature types"

    def __str__(self):
        return self.name
    
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)
        

class Mechanic(BaseModel):
    """
    Mecánicas oficiales de Magic — keywords, actions, ability words y misc.
    Sincronizadas desde los catálogos de Scryfall.
    """
    name      = models.CharField(max_length=100, unique=True, db_index=True)
    slug      = models.SlugField(max_length=100, unique=True, db_index=True, blank=True)
    kind      = models.CharField(
        max_length=20,
        choices=MechanicType.choices,
        default=MechanicType.KEYWORD,
        db_index=True,
    )
    synced_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering        = ["kind", "name"]
        verbose_name    = "mechanic"
        verbose_name_plural = "mechanics"

    def __str__(self):
        return f"{self.name} ({self.get_kind_display()})"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)