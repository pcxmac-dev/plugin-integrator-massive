# plugin-integrator-massive

Massive (massive.com, formerly Polygon.io) for [Liminal](https://github.com/pcxmac-dev/liminal-charts):
stocks, indices, currencies, crypto and futures on its REST API, one plan per asset class, with
1-second and minute bars, reference data (exchanges, listings, trade conditions, market holidays)
and its headlines (a publisher in this plugin, `massive-news`, read every 30 minutes on the same key
and limits). Its scan finds the stocks plan from what the key may ask for.

A Liminal provider plugin released on its own: a class each on the class contract (plugin API 2.2),
`MassivePlugin` (its feed, a `FeedPlugin`) and `MassiveHeadlines` (its headlines, a `PublisherPlugin`).
The app finds it through the entry point group `liminal.providers` and lists it on the Plugins view and
in `liminal-charts plugins` as `package: plugin-integrator-massive`, with this package's version.

## Its API

It attaches to Massive's REST API at `https://api.massive.com`, the key sent as a bearer token. The card on its page
in every app (`apis`, plugin API 2.2: `src/plugin_integrator_massive/apis.py`, read from Massive's pages on
2026-11-11) says what the API is, its limits and prices, every part of it and every call made here:

- Documentation: <https://massive.com/docs> (the REST quickstart: <https://massive.com/docs/rest/quickstart>)
- Request limits: <https://massive.com/knowledge-base/article/what-is-the-request-limit-for-massives-restful-apis>
  (a free plan: 5 requests a minute per asset class; a paid one: none)
- Pricing: <https://massive.com/pricing> (each asset class a plan of its own)
- Status: <https://massive.com/system>, alerts and incidents at <https://massive-status.com/>
- Changelog: <https://massive.com/changelog>
- API keys: <https://massive.com/dashboard/keys>

Used here: the aggregates of stocks, indices (`I:`), currencies (`C:`) and crypto (`X:`), the whole market's day,
trades, one quote (the plan scan), tickers, exchanges, trade conditions, market holidays, news (the headlines), and
futures' bars, schedules and products. Not used: options, snapshots, technical indicators, corporate actions,
fundamentals, filings, the economy, alternative and partners' data, the WebSockets and the Flat Files.

## Settings

User environment variables, saved with the app's `tools/set-key.ps1` or on the Plugins view; the key
is only ever read from the environment and never written to a file. They are the plugin's own
settings (the plugin's `settings` hook), read when the app's settings load:

| Variable | Meaning |
| --- | --- |
| `MASSIVE_API_KEY` | required for any request (your dashboard's API key) |
| `MASSIVE_TIER` | `free` (default), `starter`, `developer` or `advanced`: your Stocks plan; sets how far back the collector reaches; the scan finds it where you set none |
| `MASSIVE_TIER_INDICES`, `MASSIVE_TIER_CURRENCIES`, `MASSIVE_TIER_CRYPTO`, `MASSIVE_TIER_FUTURES` | the plan of each other asset class (default `free`); a free class is held to 5 requests a minute |
| `MASSIVE_RPM` | override the plan's requests a minute (0 = unlimited) |
| `MASSIVE_BASE_URL` | the API's base URL (default: Massive's own) |
| `MASSIVE_MAX_REQUESTS_PER_RUN`, `MASSIVE_MAX_REQUESTS_PER_DAY` | hard caps (default 250 / 2000) |

## Install

Into the app's environment, from the app's folder:

```powershell
.venv\Scripts\python.exe -m pip install "plugin-integrator-massive @ git+https://github.com/pcxmac-dev/plugin-integrator-massive@v0.3.0"
```

or with the app's plugins (`pip install -e ".[plugins]"` in liminal-charts). The app loads it on its next
start.

## Compatibility

It is written for plugin API 2.2 (`PLUGIN.api`: the class contract of liminal-libs 1.3.0, a plugin an
instance of a `FeedPlugin` or `PublisherPlugin` subclass, with the API cards of liminal-libs 1.49.0). An app
offering 2.2 or a later 2.x loads it; an app offering an older 2.x, or another major, leaves it out and says why on
the Plugins view.

## Develop

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install "liminal-libs @ git+https://github.com/pcxmac-dev/liminal-libs@release/0.2.0"
.venv\Scripts\python.exe -m pip install -e ".[dev]"
.venv\Scripts\python.exe -m pytest -q
```

Tests never send requests (a fake session answers) and never read your key. One test asks every address on the
API's card, only with `LIMINAL_VENDOR_PAGES=1` set.
