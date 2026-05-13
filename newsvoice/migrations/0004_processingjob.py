from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("newsvoice", "0003_newsaudio"),
    ]

    operations = [
        migrations.CreateModel(
            name="ProcessingJob",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("job_type", models.CharField(choices=[("summary", "Summary"), ("audio", "Audio"), ("news_fetch", "News Fetch")], max_length=20)),
                ("status", models.CharField(choices=[("queued", "Queued"), ("processing", "Processing"), ("completed", "Completed"), ("failed", "Failed")], default="queued", max_length=20)),
                ("payload", models.JSONField(blank=True, default=dict)),
                ("result", models.JSONField(blank=True, default=dict)),
                ("error_message", models.TextField(blank=True)),
                ("started_at", models.DateTimeField(blank=True, null=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("article", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="processing_jobs", to="newsvoice.newsarticle")),
                ("audio", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="processing_jobs", to="newsvoice.newsaudio")),
            ],
            options={
                "ordering": ["created_at"],
                "indexes": [models.Index(fields=["status", "job_type", "created_at"], name="newsvoice_p_status_78df08_idx")],
            },
        ),
    ]
