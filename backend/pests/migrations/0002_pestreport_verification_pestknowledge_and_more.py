from django.db import migrations, models
import django.db.models.deletion


KNOWLEDGE = [
    (
        "fall_armyworm",
        ["leaf_holes", "frass"],
        {
            "en": ["Leaves have ragged holes.", "Look for fresh waste deep in the leaf funnel."],
            "sw": ["Majani yana mashimo yasiyo sawa.", "Angalia uchafu mpya katikati ya jani."],
        },
        {
            "en": ["Inspect several plants in the morning.", "Hand-pick egg masses and larvae on a small plot; wear gloves."],
            "sw": ["Kagua mimea kadhaa asubuhi.", "Ondoa mayai na viwavi kwa mkono kwenye eneo dogo; vaa glavu."],
        },
        {
            "en": ["Plant at the recommended time.", "Rotate crops and keep scouting.", "Use locally recommended biological controls."],
            "sw": ["Panda kwa wakati unaofaa.", "Badilisha mazao na endelea kukagua.", "Tumia njia za asili zinazopendekezwa eneo lako."],
        },
        {
            "en": ["Call an officer if damage is spreading or many young plants are affected."],
            "sw": ["Piga simu kwa afisa ikiwa uharibifu unaenea au miche mingi imeathirika."],
        },
    ),
    (
        "aphids",
        ["aphid_clusters", "sticky_leaves"],
        {
            "en": ["Small insects cluster on young shoots.", "Leaves may curl or feel sticky."],
            "sw": ["Wadudu wadogo hukusanyika kwenye machipukizi.", "Majani yanaweza kujikunja au kuwa na utomvu."],
        },
        {
            "en": ["Check the undersides of leaves.", "On a small patch, knock aphids off with water and protect ladybirds."],
            "sw": ["Kagua upande wa chini wa majani.", "Kwenye sehemu ndogo, ondoa vidukari kwa maji na linda wadudu rafiki."],
        },
        {
            "en": ["Avoid excess nitrogen.", "Encourage natural enemies and remove heavily affected shoots."],
            "sw": ["Epuka nitrojeni nyingi.", "Linda wadudu rafiki na ondoa machipukizi yaliyoathirika sana."],
        },
        {
            "en": ["Call an officer if the infestation spreads or the crop stops growing."],
            "sw": ["Piga simu kwa afisa ikiwa wadudu wanaenea au ukuaji unasimama."],
        },
    ),
    (
        "whitefly",
        ["whitefly_cloud", "sticky_leaves"],
        {
            "en": ["Tiny white insects fly when leaves are disturbed.", "Leaves may yellow or become sticky."],
            "sw": ["Nzi weupe wadogo huruka ukitikisa majani.", "Majani yanaweza kuwa ya manjano au yenye utomvu."],
        },
        {
            "en": ["Inspect leaf undersides.", "Remove badly infested leaves and avoid moving infested seedlings."],
            "sw": ["Kagua upande wa chini wa majani.", "Ondoa majani yaliyoathirika sana na usihamishe miche yenye wadudu."],
        },
        {
            "en": ["Use clean seedlings.", "Remove weeds and conserve natural enemies.", "Use monitoring traps where locally recommended."],
            "sw": ["Tumia miche safi.", "Ondoa magugu na linda wadudu rafiki.", "Tumia mitego ya ufuatiliaji inapopendekezwa."],
        },
        {
            "en": ["Call an officer if numbers rise quickly or a virus-like disease appears."],
            "sw": ["Piga simu kwa afisa ikiwa idadi inaongezeka haraka au dalili za ugonjwa zinaonekana."],
        },
    ),
    (
        "tomato_leafminer",
        ["leafminer_tunnels", "leaf_holes"],
        {
            "en": ["Leaves show winding tunnels or blotches.", "Fruit may have small entry holes."],
            "sw": ["Majani yana njia zilizochimbwa au madoa.", "Matunda yanaweza kuwa na matundu madogo."],
        },
        {
            "en": ["Check leaves and fruit closely.", "Remove and safely destroy infested plant parts; do not leave them in the field."],
            "sw": ["Kagua majani na matunda kwa makini.", "Ondoa na haribu salama sehemu zilizoathirika; usiziachie shambani."],
        },
        {
            "en": ["Use clean seedlings.", "Remove crop residues after harvest.", "Use pheromone traps for monitoring and follow local IPM advice."],
            "sw": ["Tumia miche safi.", "Ondoa mabaki ya mazao baada ya kuvuna.", "Tumia mitego ya pheromone kufuatilia na fuata ushauri wa IPM."],
        },
        {
            "en": ["Call an officer when tunnels appear in many plants or fruit is being damaged."],
            "sw": ["Piga simu kwa afisa njia zikionekana kwenye mimea mingi au matunda yakiharibika."],
        },
    ),
    (
        "late_blight",
        ["dark_leaf_spots", "white_leaf_growth", "dark_fruit_lesions"],
        {
            "en": ["Dark, spreading patches appear on leaves.", "White growth may show underneath in damp weather.", "Fruit can develop firm dark lesions."],
            "sw": ["Madoa meusi yanayoenea huonekana kwenye majani.", "Unga mweupe unaweza kuonekana chini wakati wa unyevu.", "Matunda yanaweza kupata vidonda vyeusi."],
        },
        {
            "en": ["Avoid touching wet plants.", "Remove badly affected parts carefully and keep them away from the field.", "Do not eat damaged fruit."],
            "sw": ["Epuka kugusa mimea yenye unyevunyevu.", "Ondoa sehemu zilizoathirika sana kwa uangalifu na uzitoe shambani.", "Usile matunda yaliyoharibika."],
        },
        {
            "en": ["Space plants for airflow.", "Water at the soil, not over leaves.", "Rotate crops and remove volunteer potatoes and tomatoes."],
            "sw": ["Acha nafasi ya hewa kati ya mimea.", "Mwagilia udongo, si majani.", "Badilisha mazao na ondoa viazi na nyanya zilizoota zenyewe."],
        },
        {
            "en": ["Call an officer promptly; the disease can spread quickly in cool, wet weather."],
            "sw": ["Wasiliana na afisa haraka; ugonjwa unaweza kuenea upesi wakati wa baridi na unyevu."],
        },
    ),
    (
        "coffee_berry_disease",
        ["dark_fruit_lesions", "berry_drop"],
        {
            "en": ["Coffee berries develop dark, sunken lesions.", "Green berries may shrivel or drop early."],
            "sw": ["Matunda ya kahawa hupata vidonda vyeusi vilivyozama.", "Matunda mabichi yanaweza kusinyaa au kudondoka mapema."],
        },
        {
            "en": ["Collect affected berries and remove them from the coffee plot.", "Clean tools before moving between plots."],
            "sw": ["Kusanya matunda yaliyoathirika na uyaondoe shambani.", "Safisha vifaa kabla ya kwenda shamba lingine."],
        },
        {
            "en": ["Prune for airflow using local guidance.", "Harvest and sanitize regularly.", "Use only locally approved control measures."],
            "sw": ["Pogoa ili hewa ipite kwa ushauri wa eneo lako.", "Vuna na safisha shamba mara kwa mara.", "Tumia njia zilizoidhinishwa eneo lako pekee."],
        },
        {
            "en": ["Call a coffee extension officer when berry lesions or early drop are seen."],
            "sw": ["Wasiliana na afisa wa kahawa ukiona vidonda au matunda yakidondoka mapema."],
        },
    ),
]


def seed_knowledge(apps, schema_editor):
    Knowledge = apps.get_model("pests", "PestKnowledge")
    for pest_name, icons, symptoms, actions, ipm, call_officer in KNOWLEDGE:
        Knowledge.objects.update_or_create(
            pest_name=pest_name,
            defaults={
                "symptom_icons": icons,
                "symptoms_by_language": symptoms,
                "safe_actions_by_language": actions,
                "ipm_by_language": ipm,
                "call_officer_by_language": call_officer,
            },
        )


class Migration(migrations.Migration):
    dependencies = [("pests", "0001_initial")]

    operations = [
        migrations.AlterField(
            model_name="pestreport",
            name="status",
            field=models.CharField(
                choices=[
                    ("PENDING", "Pending"),
                    ("NEEDS_INFO", "More information requested"),
                    ("CONFIRMED", "Confirmed"),
                    ("REJECTED", "Rejected"),
                ],
                default="PENDING",
                max_length=12,
            ),
        ),
        migrations.AlterField(
            model_name="pestreport",
            name="pest_name",
            field=models.CharField(
                blank=True,
                choices=[
                    ("fall_armyworm", "Fall armyworm"),
                    ("aphids", "Aphids"),
                    ("whitefly", "Whitefly"),
                    ("tomato_leafminer", "Tomato leafminer (Tuta absoluta)"),
                    ("late_blight", "Late blight"),
                    ("coffee_berry_disease", "Coffee berry disease"),
                ],
                max_length=32,
            ),
        ),
        migrations.AddField(
            model_name="pestreport",
            name="symptoms",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="pestreport",
            name="verification_note",
            field=models.TextField(blank=True),
        ),
        migrations.AddConstraint(
            model_name="outbreak",
            constraint=models.UniqueConstraint(
                fields=("ward", "pest_name"),
                name="unique_outbreak_ward_pest",
            ),
        ),
        migrations.CreateModel(
            name="PestKnowledge",
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
                    "pest_name",
                    models.CharField(
                        choices=[
                            ("fall_armyworm", "Fall armyworm"),
                            ("aphids", "Aphids"),
                            ("whitefly", "Whitefly"),
                            ("tomato_leafminer", "Tomato leafminer (Tuta absoluta)"),
                            ("late_blight", "Late blight"),
                            ("coffee_berry_disease", "Coffee berry disease"),
                        ],
                        max_length=32,
                        unique=True,
                    ),
                ),
                ("symptom_icons", models.JSONField(default=list)),
                ("symptoms_by_language", models.JSONField(default=dict)),
                ("safe_actions_by_language", models.JSONField(default=dict)),
                ("ipm_by_language", models.JSONField(default=dict)),
                ("call_officer_by_language", models.JSONField(default=dict)),
                (
                    "photo",
                    models.ImageField(
                        blank=True, null=True, upload_to="pest-knowledge/"
                    ),
                ),
            ],
            options={"ordering": ["pest_name"]},
        ),
        migrations.RunPython(seed_knowledge, migrations.RunPython.noop),
    ]
