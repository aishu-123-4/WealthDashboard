# WealthDesk Portfolio Dashboard

## Deploy this repository on Netlify

The repository root now contains the Netlify build configuration and API function. Select the repository's root as the Base directory and use `npm run build` with Publish directory `dist`. The checked-in `netlify.toml` supplies these settings. Do not set the Base directory to the nested Python project. Deploy from Git; uploading only `dist` omits the API function.

Netlify builds the original dashboard HTML/CSS/JS into `dist` and deploys `/api/*` to a Node serverless function. Portfolios, ledger entries, proposals, sales, messages and chat history persist in the site-wide `wealthdesk-demo-v1` Netlify Blobs store. No external database credential is needed: Netlify supplies storage access to the function. Conditional ETag writes prevent simultaneous edits from overwriting balances. Failed or stale mutations save nothing and ask the user to refresh/retry.

After a successful production deployment, open `/` and choose a fictional profile. `/api/profiles` should return seven profiles; `/healthz` should return `{"status":"ok"}`. Create a test portfolio and reload to confirm persistence. The first request seeds the fictional dataset once; redeployments do not reset the saved workspace. Live Netlify storage still requires verification after deployment; tests use an isolated implementation of its documented conditional-write interface.

If the site asks visitors to log in, check Netlify's Project configuration > General > Visitor access settings. Repository changes cannot alter account-level project visibility. A public demo must be set Public in the Netlify dashboard by its owner.

## Included workflows

Business owners have multiple named personal and business portfolios, family recipients and transfers, recorded assets/liquidity/liabilities/investments, sale proceeds credited to a selected personal portfolio, investment proposal approvals, a floating AI chat popup, and messages/meeting requests with their wealth advisor. The advisor's book includes all assigned owners and professional contacts. CA, broker and commercial RM screens and A/B/C/D trigger alerts preserve account-sharing permissions.

The role selector and all seeded people, companies, balances and events are fictional demonstration content. Everyone who can access the site can switch demo roles. Use fictional data only. Entries do not execute bank transfers, trades, email or calendar bookings. The demo workspace is bounded to 1.5 MB. This is not a real banking authentication system or a trained sale-prediction model.

## AI chat

Without configuration, chat provides explicitly labeled account summaries. Optional external AI requires `OPENAI_API_KEY` and `OPENAI_MODEL` in Netlify environment variables with Functions scope, followed by redeployment. Never commit an API key. Per-question sharing consent remains required; only the selected account and that user's account-specific history are sent. Provider usage can incur separate charges. No live provider key is included.

## Local verification

```sh
npm ci
npm test
npm run build
```

The tests cover all seven roles against reference output from the Python app, named portfolio balances, transfers, proposal approvals, sale closings, trigger routing, account access, chat, advisor messages, concurrent edits and persistence. Additional tests exercise the Netlify storage adapter's first-write, compare-and-swap and failed-write behavior.

## Original Python project

The original app remains in `WealthDesk-Portfolio-Dashboard_Demo_code/portfolio-dashboard/` and can still run locally with `python launch.py`. Its local SQLite database is separate from the hosted Netlify demo and is not uploaded. Do not use the earlier Heroku Procfile instructions for this Netlify deployment.
