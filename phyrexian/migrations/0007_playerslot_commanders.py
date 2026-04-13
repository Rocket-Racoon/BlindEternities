from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('phyrexian', '0006_add_commander_taxes'),
    ]

    operations = [
        migrations.AddField(
            model_name='playerslot',
            name='commanders',
            field=models.JSONField(blank=True, default=list),
        ),
    ]
