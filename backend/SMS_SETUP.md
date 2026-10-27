# SMS setup

The default provider is the network-free simulator. Keep it selected while testing. A Vendel batch is sent only after an authenticated admin or officer confirms it in the warning center; the rules and weekly tip jobs create draft Alerts only.

## Vendel

1. Create an account at [Vendel](https://app.vendel.cc).
2. Pair the Android phone or USB modem that will send messages, then verify it is online in Vendel.
3. Create an integration API key. Use the `vk_` integration key, not a user session token.
4. Copy `backend/.env.example` to `backend/.env` and set `SMS_PROVIDER=vendel`, `VENDEL_BASE_URL=https://app.vendel.cc`, `VENDEL_API_KEY`, and `VENDEL_WEBHOOK_SECRET`. The webhook secret is a shared signing secret, not a URL; do not commit `backend/.env`.
5. Add only opted-in E.164 numbers to `DEMO_RECIPIENTS` when using the Demo Group.
6. Create a Vendel webhook for `https://YOUR_PUBLIC_HOST/api/sms/vendel/webhook/` and use the same secret as `VENDEL_WEBHOOK_SECRET`. For local development, the callback path is `http://127.0.0.1:8000/api/sms/vendel/webhook/`, but Vendel cannot reach that loopback address; expose the local server through a secure public HTTPS tunnel and configure the tunnel URL instead.
7. Run the provider check with `python manage.py sms_status`. To send one explicit test to an opted-in number, run `python manage.py sms_test --to +254712345678`.
8. Use `/admin/warnings` for farmer or ward warnings. Review the provider, recipients and skipped reasons, then type `SEND` to confirm.

The webhook accepts only valid Vendel signatures. Vendel batch status is also polled when an authorized user opens a batch.

## Simulator fallback

Set `SMS_PROVIDER=simulator` and leave Vendel credentials empty. The simulator makes no network requests and progresses queued messages through sent to delivered. Run `python manage.py sms_status` to check the selected provider. The `sms_test` command can also exercise the simulator without contacting a phone.
