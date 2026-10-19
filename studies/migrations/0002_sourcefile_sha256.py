import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("studies", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="sourcefile",
            name="sha256",
            field=models.CharField(blank=True, db_index=True, max_length=64,
                                   verbose_name="sha256 do arquivo"),
        ),
    ]
