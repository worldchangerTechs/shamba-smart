from django.db import migrations


BUILTIN_RULES = [
    (
        "HEAVY_RAIN_STEEP",
        "erosion",
        "HIGH",
        {"rain_forecast_24h": {"over": 25}, "slope_class": "STEEP"},
        24,
    ),
    (
        "COOL_WET_TOMATO_BLIGHT",
        "pests",
        "HIGH",
        {"temp": {"under": 20}, "humidity": {"over": 85}, "days": 2, "crop": "tomato"},
        48,
    ),
    (
        "OUTBREAK_NEARBY",
        "pests",
        "HIGH",
        {"confirmed_reports": 3, "days": 7},
        24,
    ),
    ("SPRAY_LOGGED", "ppe", "MEDIUM", {}, 0),
    ("LOW_PH", "soil", "LOW", {}, 168),
    ("DRY_SPELL_MULCH", "climate", "MEDIUM", {"days": 7}, 24),
    ("PRICE_SPIKE", "market", "MEDIUM", {"increase_percent": 20}, 24),
    ("WASTE_REMINDER", "waste", "LOW", {"days": 7}, 0),
]


def seed_rules(apps, schema_editor):
    Rule = apps.get_model("alerts", "Rule")
    for code, problem_tag, severity, conditions, cooldown in BUILTIN_RULES:
        Rule.objects.update_or_create(
            code=code,
            defaults={
                "problem_tag": problem_tag,
                "severity": severity,
                "condition_json": conditions,
                "message_templates": {},
                "cooldown_hours": cooldown,
                "active": True,
            },
        )


class Migration(migrations.Migration):
    dependencies = [("alerts", "0002_rulewardpriority_alert_priority_alert_source_key_and_more")]

    operations = [migrations.RunPython(seed_rules, migrations.RunPython.noop)]
