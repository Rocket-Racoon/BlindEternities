from django.db import migrations, models
import django.db.models.deletion


def clear_cover_cards(apps, schema_editor):
    """Null out cover_card values since they reference Card, not CardPrint."""
    Collection = apps.get_model("tolarian", "Collection")
    Deck = apps.get_model("tolarian", "Deck")
    Collection.objects.filter(cover_card__isnull=False).update(cover_card=None)
    Deck.objects.filter(cover_card__isnull=False).update(cover_card=None)


class Migration(migrations.Migration):

    dependencies = [
        ("tolarian", "0001_initial"),
        ("multiverse", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(clear_cover_cards, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="collection",
            name="cover_card",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="+",
                to="multiverse.cardprint",
            ),
        ),
        migrations.AlterField(
            model_name="deck",
            name="cover_card",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="+",
                to="multiverse.cardprint",
            ),
        ),
    ]
