# Convert DeckCard.category FK to DeckCard.categories M2M

from django.db import migrations, models


def copy_fk_to_m2m(apps, schema_editor):
    """Copy existing FK category values into the new M2M relationship."""
    DeckCard = apps.get_model("tolarian", "DeckCard")
    for card in DeckCard.objects.filter(category__isnull=False).select_related("category"):
        card.categories.add(card.category)


class Migration(migrations.Migration):

    dependencies = [
        ("tolarian", "0005_deck_categories_and_game_changer"),
    ]

    operations = [
        # 1. Add M2M field
        migrations.AddField(
            model_name="deckcard",
            name="categories",
            field=models.ManyToManyField(
                blank=True, related_name="cards", to="tolarian.deckcategory"
            ),
        ),
        # 2. Copy FK data to M2M
        migrations.RunPython(copy_fk_to_m2m, migrations.RunPython.noop),
        # 3. Remove old FK
        migrations.RemoveField(
            model_name="deckcard",
            name="category",
        ),
    ]
