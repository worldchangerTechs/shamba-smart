# Shamba Django API

Django REST Framework backend with PostgreSQL, role-scoped API viewsets, OpenAPI docs, and Celery configuration.

## Setup

Use Python 3.12-3.14 for the smoothest Windows installation; Python 3.15 may require a C++ compiler to build transitive dependencies that do not yet publish a compatible wheel.

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

The settings load `backend/.env` automatically. For local development, set `DJANGO_DEBUG=true` and replace `DJANGO_SECRET_KEY` with a generated secret before running Django. The example uses SQLite; PostgreSQL can be configured using `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_HOST`, and `POSTGRES_PORT`.

Apply existing schema migrations and create demo records:

```powershell
python manage.py migrate
$env:DEMO_USER_PASSWORD = "choose-a-demo-password"
python manage.py seed_demo
python manage.py createsuperuser
python manage.py runserver
```

`migrate` applies migrations already in the repository. To create a new migration after changing model fields, use `python manage.py makemigrations` (one word), then `python manage.py migrate`. Data-only changes do not need a schema migration.

The demo command creates 6 Kisii wards, 5 crop references, 40 farmer accounts, farms and plantings, and 3 officers. Demo farmer phones range from `+254720000001` to `+254720000040`; officer phones range from `+254710000001` to `+254710000003`. It sets passwords only on newly created users or existing demo users without a usable password, and only when `DEMO_USER_PASSWORD` is set. It is safe to rerun.

Run the backend tests with SQLite:

```powershell
python -m pytest
```

## API

- REST API: `/api/`
- Health: `/api/health/`
- Analytics summary: `/api/analytics/summary/`
- OpenAPI schema: `/api/schema/`
- Swagger UI: `/api/docs/`
- ReDoc: `/api/redoc/`
- Django admin: `/admin/`
- Farm planner: `/api/farms/{id}/planner/`
- Farm weather history and forecast: `/api/farms/{id}/weather/`
- Udongo Doctor: `POST /api/advice/udongo-doctor/`
- Mteremko Guard: `POST /api/advice/mteremko-guard/`
- PPE Gap Finder: `POST /api/advice/ppe-gap-finder/`
- Taka Loop: `GET /api/advice/taka-loop/?waste_type=CROP_RESIDUE`
- PPE-aware spray logging: `POST /api/spray-logs/`
- Advice catalogue: `GET /api/advice-content/`
- Pest report submission: `POST /api/pest-reports/` (multipart photo, crop, and device coordinates or farm)
- Officer verification queue: `GET /api/pest-reports/verification-queue/`
- Report verification: `PATCH /api/pest-reports/{id}/verify/`
- Outbreak GeoJSON: `GET /api/pests/outbreaks/`
- Pest knowledge: `GET /api/pests/knowledge/?language=en`
- Symptom-icon guide: `POST /api/pests/identify/`
- Public pest counters: `GET /api/pests/stats/`
- Academy lessons: `GET /api/lessons/?problem_tag=soil`
- Lesson progress and quiz: `POST /api/lesson-progress/`
- Earned badges: `GET /api/badges/`
- Ask an Officer: `POST /api/officer-questions/`
- Officer questions queue: `GET /api/officer-questions/queue/`
- Officer answer: `POST /api/officer-questions/{id}/answer/`
- Searchable FAQs: `GET /api/faqs/?q=soil&language=en`
- Market prices: `GET /api/market-prices/?crop_id={id}&ward_id={id}`
- Crop price trends: `GET /api/market-prices/trends/?crop_id={id}&ward_id={id}`
- Local price comparison: `GET /api/market-prices/compare/?farm_id={id}&crop_id={id}&middleman_price_per_kg={kes}&quantity_kg={kg}`
- Verified buyer directory: `GET /api/buyers/`
- Training and trade events: `GET /api/training-events/`
- Sell My Crop listings: `POST /api/sell-listings/` and `GET /api/sell-listings/`
- Public USSD/SMS-ready lookup: `GET /api/market/price-lookup/?crop=Tomato&ward=Kisii%20Central&language=sw`
- Gateway alias for price lookup: `GET /api/gateway/market-price/?crop=Tomato&ward=Kisii%20Central`

Open-Meteo weather is refreshed every six hours by Celery Beat. Each ward fetch stores 30 past days and a 14-day forecast so planner recommendations and 24-hour rain alerts have the required time windows. `forecast_json.hourly` preserves the hourly values used by rain alerts.

For offline development, run `python manage.py seed_weather_demo` after creating wards. It adds clearly labelled synthetic weather history and a 14-day sample forecast while preserving any live Open-Meteo snapshots already stored. Do not use sample weather for real farm decisions or production warning delivery.

JWT, session, and HTTP Basic authentication are enabled. Obtain an access/refresh pair with `POST /api/auth/token/` using `phone` and `password`; refresh with `POST /api/auth/token/refresh/`. The custom user model uses `phone` as its login identifier. Farmers are restricted to their own records (and ward weather/outbreak information); officers are restricted to their assigned wards; admins can access all records. Catalog, market, lesson, rule, and disposal-point endpoints are authenticated read-only for non-admin users.

The mobile-first React client is in `../frontend`. Configure `CORS_ALLOWED_ORIGINS` to include its origin (for example `http://localhost:5173`) and use `VITE_API_BASE_URL` when the API is not at `http://127.0.0.1:8000/api`.

## Celery

Celery loads tasks from installed apps and uses `CELERY_BROKER_URL` and `CELERY_RESULT_BACKEND`. Start a worker with:

```powershell
celery -A config worker -l INFO
celery -A config beat -l INFO
```

## Alerts and messaging

The alert rules evaluator runs every three hours and only evaluates active `Rule` rows. The built-in codes are `HEAVY_RAIN_STEEP`, `COOL_WET_TOMATO_BLIGHT`, `OUTBREAK_NEARBY`, `SPRAY_LOGGED`, `LOW_PH`, `DRY_SPELL_MULCH`, `PRICE_SPIKE`, and `WASTE_REMINDER`. SMS and voice gateways can be configured as dotted Python callables with `ALERT_SMS_SENDER` and `ALERT_VOICE_SENDER`; each callable receives `(user, message, alert)` and returns a truthy value when delivery succeeds. App delivery is recorded in the farmer's in-app alert inbox. The messenger observes SMS consent, language, weekly non-urgent delivery caps, and urgent severity bypass.

Submit delivery feedback with `POST /api/alert-deliveries/{id}/feedback/` and `{"feedback":"HELPFUL"}` or `{"feedback":"NOT_RELEVANT"}`. Three or more not-relevant votes lower that rule's priority for the recipient's ward.

The pytest configuration uses `config.test_settings`, which runs the suite against an in-memory SQLite database.

Pest reports require a photo and crop. The client should request device location and send `lat`/`lng`; when the farmer selects their own farm, its saved coordinates are used if device coordinates are omitted. Officers verify reports from their assigned wards, choose from the built-in pest list, or request more information. Three confirmed reports of the same pest in a ward within the configured seven-day window update the ward outbreak and alert farmers growing the reported crop within five kilometres of the report location. The symptom-icon helper is an educational guide, not a diagnosis. Pest reference photos can be managed in Django admin.

## Market prices and crop sales

After `seed_demo`, run `python manage.py seed_market_demo` to add 15 horticulture crops, weekly market price history in six Kisii wards, sample buyer directory entries, events, and sample sale listings. Seeded records are explicitly marked `is_sample_data`; buyer entries have placeholder contacts and are not verified real businesses. Replace the sample contact details and verify buyers before production.

Officers can create prices only in assigned wards and edit prices in those wards. `GET /api/market-prices/trends/` returns daily prices plus comparisons for the latest 7 and 30 days against the preceding periods. `GET /api/market-prices/compare/` compares a farmer-provided middleman offer with the best recorded market price within 30 km and estimates the gain for the requested quantity; its estimate excludes transport and handling. Because price records are ward-based, the distance is measured from ward coordinates and is an approximation, not a market-gate route distance.

Farmers create Sell My Crop offers at `POST /api/sell-listings/`; authenticated users can browse open listings at `GET /api/sell-listings/`. Verified buyer and training/trade event directories are at `/api/buyers/` and `/api/training-events/`.

USSD/SMS integrations can query the provider-neutral public lookup at `/api/gateway/market-price/` (also available at `/api/market/price-lookup/`). Send crop and ward names, plus optional `language=en`, `sw`, or `guz`. The response includes `ussd_text` and an `sms_text` capped at 160 characters. No USSD/SMS provider credentials or P13-specific callback contract are present in this repository; connect the provider's adapter to this lookup endpoint.

Import price CSV files with `python manage.py import_market_prices prices.csv`. Required headers are `crop,market_name,ward,price_per_kg,date`; `is_sample_data` is optional and defaults to false. Dates use `YYYY-MM-DD`. Imports upsert on crop, market, ward, and date and roll back the entire file if any row is invalid.

## Farmer advice services

The advice migrations seed 20 short, database-backed advice cards for Udongo Doctor, Spray Safe, Mteremko Guard, and Taka Loop. English and Swahili card text is seeded; Ekegusii fields are available and fall back to English until reviewed translations are added. Udongo Doctor accepts a crop with either soil pH or all six visual quiz answers. Mteremko Guard accepts a farm, ground-cover percentage, and tillage method, then uses the ward's 14-day rain snapshots. Taka Loop reports disposal-point distance and a Clean Farm score that adds 10 points per logged waste action, capped at 100.

Spray-log creation returns the PPE checklist, re-entry countdown, pre-harvest interval, and harvest lock date. PPE supplier records can be maintained in Django admin; `item_prices_kes` maps `mask`, `gloves`, `boots`, `overall`, and `goggles` to prices in KES. The PPE Gap Finder compares these offers and reports the lowest-price offers and nearest supplier with missing items.

## Farmer Academy

The academy migration seeds 16 short lessons, two for each of the eight problem tags. Lessons return five steps, a three-question quiz without answer keys, and an optional photo/audio asset for each supported language. Upload reviewed audio in English, Kiswahili, and Ekegusii through Django admin. If a localized text/audio asset is not present, the API falls back to English; only English and Kiswahili lesson text is seeded.

Farmers post progress to `/api/lesson-progress/` with a lesson ID, optional completed step count from 0 to 5, and three quiz option indexes. A perfect quiz completes the lesson and awards a category badge after two lessons; five logged waste actions award Clean Farm. Badges are read-only to users.

Farmers can submit a text question or voice note to `/api/officer-questions/`. Assigned officers view open questions in their wards and answer with `/api/officer-questions/{id}/answer/`; each answer is added to `/api/faqs/` for text search. The weekly SMS tip runs Mondays at 09:00 Africa/Nairobi time, sends only to farmers who have explicitly consented to SMS, and uses `ALERT_SMS_SENDER`. Each farmer receives at most one recorded tip per calendar week.
