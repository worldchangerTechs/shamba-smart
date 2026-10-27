import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0001_initial"),
        ("farms", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="consent_sms_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="farmer",
            name="main_crop",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="preferred_by_farmers",
                to="farms.crop",
            ),
        ),
        migrations.CreateModel(
            name="FailedLoginCounter",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "identity_type",
                    models.CharField(
                        choices=[("PHONE", "Phone"), ("IP", "IP address")],
                        max_length=5,
                    ),
                ),
                ("identity_hash", models.CharField(max_length=64)),
                ("failures", models.PositiveSmallIntegerField(default=0)),
                ("window_started_at", models.DateTimeField()),
            ],
            options={
                "constraints": [
                    models.UniqueConstraint(
                        fields=("identity_type", "identity_hash"),
                        name="unique_failed_login_identity",
                    )
                ],
            },
        ),
    ]
