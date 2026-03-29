from django.db.models.signals import post_save
from django.contrib.auth.models import User
from django.dispatch import receiver
from .models import Profile


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)

        from tolarian.models import Collection, CollectionType
        defaults = [
            (CollectionType.BINDER,    "Mi Binder"),
            (CollectionType.WISHLIST,  "Mi Wishlist"),
            (CollectionType.TRADELIST, "Mi Trade List"),
            (CollectionType.LOANLIST,  "Mi Loan List"),
        ]
        Collection.objects.bulk_create([
            Collection(user=instance, name=name, collection_type=ctype)
            for ctype, name in defaults
        ])


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    if hasattr(instance, 'profile'):
        instance.profile.save()
