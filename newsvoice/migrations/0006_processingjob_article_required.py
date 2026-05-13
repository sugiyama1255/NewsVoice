from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("newsvoice", "0005_processingjob_nullable_article"),
    ]

    operations = [
        migrations.AlterField(
            model_name="processingjob",
            name="article",
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="processing_jobs", to="newsvoice.newsarticle"),
        ),
    ]
