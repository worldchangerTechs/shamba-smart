# Shamba frontend

Mobile-first React, Vite, TypeScript and Tailwind client for the Django API.

## Run locally

```powershell
cd frontend
npm install
Copy-Item .env.example .env
npm run dev
```

The default API URL is `http://127.0.0.1:8000/api`. Set `VITE_API_BASE_URL` to override it. Allow the frontend origin in the backend's `CORS_ALLOWED_ORIGINS` environment variable.

## Public landing page

The public SHAMBA SMART 360 landing page is at `/`. The farmer application is under `/app` and requires login. Framer Motion drives its in-view reveals and pinned scroll scenes; the Kisii outbreak map and its Leaflet code load only as the map approaches the viewport. The basic-phone USSD illustration is interactive. Dashboard and outbreak figures on the public page are illustrative and explicitly labelled sample data.

Landing page image names, responsive WebP paths and the outstanding source-photo requirements are documented in [`src/assets/README.md`](./src/assets/README.md). The supplied photo files were not present in the workspace, so the site currently displays branded gradient fallbacks until the reviewed originals and WebP exports are added.

## Authentication

The login view uses phone and password at `POST /api/auth/token/`. Access tokens are sent as Bearer tokens; the Axios client refreshes them at `/api/auth/token/refresh/` and signs the farmer out if refresh fails. Tokens are stored in browser local storage. The API's `/api/users/` endpoint supplies the signed-in user's profile.

## Localization

Translation dictionaries are in `src/i18n/`. English and Kiswahili strings are included. The Ekegusii (`guz`) dictionary deliberately includes `_review: "Needs native-speaker review"` and currently falls back to English for untranslated interface copy.
