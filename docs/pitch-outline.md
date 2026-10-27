# SHAMBA SMART 360 — 6-slide pitch outline

## 1. Problem

- Smallholder farmers must make time-sensitive decisions about rain, planting, soil, pests, safe spraying, and market prices.
- Advice is fragmented across channels, often arrives late, and may not be usable on a basic phone or in a farmer's preferred language.
- County officers need ward-level signals to prioritize outreach without treating unverified reports or sample prices as facts.
- **Visual:** A day-in-the-life map of a Kisii farmer showing three disconnected information sources.
- **Speaker note:** Ground the story in a local farmer interview before presenting publicly; do not present illustrative product data as measured county outcomes.

## 2. Solution

- One practical, plain-language next step at a time: Mvua Planner, Udongo Doctor, Spray Safe, Mteremko Guard, Pest Radar, Soko Link, Shamba Academy, and Taka Loop.
- Smartphone PWA plus SMS/voice pathways for farmers with basic phones or low connectivity.
- Ward-aware alerts, officer verification, farmer feedback, and role-scoped county views.
- **Visual:** The eight modules grouped around a farmer, with English, Kiswahili, and Ekegusii review status shown.
- **Proof point:** Demonstrate the workflow and data boundaries; keep all unverified seed data visibly marked as sample.

## 3. Live demo

1. Open a farmer account and review today's most important action.
2. Show a weather-based planting window and the week-by-week farm calendar.
3. Submit a pest report, show the officer verification queue, and explain the three-confirmed-report area-alert threshold.
4. Compare a local produce price, then show the basic-phone/SMS version.
5. Toggle offline mode to show the queued-action indicator, then reconnect and show sync status.
- **Visual:** A short, rehearsed path across the farmer and officer views; use seeded demo records only and label them.

## 4. Architecture

- React + TypeScript installable PWA, user-scoped IndexedDB cache/outbox, and responsive role dashboards.
- Django REST Framework with JWT authentication and farmer/officer/admin access scopes.
- PostgreSQL for application records; Redis/Celery for scheduled weather, alerts, and weekly tips.
- Open-Meteo forecast source and configurable SMS/voice provider adapters.
- **Visual:** [`architecture.svg`](./architecture.svg).
- **Trust note:** Farmers retain private records; officers are scoped to assigned wards; pest matching is guidance, not diagnosis.

## 5. Impact and sustainability

- **County:** Co-design ward priorities, verify data quality, train officers, and review alert helpfulness and response times.
- **Cooperatives:** Help distribute localized learning, organize safe waste drop-offs, and connect harvest supply with demand.
- **Agro-dealers:** Verify directory entries and stock/prices for PPE and inputs; keep recommendations independent and avoid implying endorsement without agreement.
- **Measurement plan:** Agree baseline and targets before a pilot. Track reach, delivery, farmer feedback, report verification time, safety actions, and market-price coverage; disaggregate by ward and channel.
- **Sustainability:** Share operational ownership, training, data stewardship, and provider costs with local partners. Do not promise revenue, savings, or yield gains until measured.
- **Visual:** Partner roles surrounding a small pilot scorecard; clearly mark any demo metrics as sample.

## 6. Ask

- Invite Kisii County to co-design and sponsor a time-bounded, ward-selected pilot with named operational owners.
- Ask cooperatives and agro-dealers to nominate contacts, validate buyer/disposal-point information, and participate in farmer testing.
- Request agreement on consent, data governance, verification responsibilities, outcome measures, and a review date before any live rollout.
- **Close with:** “Will you nominate a county lead and two local partners to scope the pilot and its success measures?”
- **Visual:** A clear decision card: county lead · cooperative partner · agro-dealer partner · pilot planning session.
