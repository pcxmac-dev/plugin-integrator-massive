# Changelog

## 0.3.0 (2026-11-11)

Its API on its page (plugin API 2.2, liminal-libs 1.49.0; the user: "each plugin should reflect the the API its
attached to, and present links that provide documentation, the plugin interface should more or less contain what it
already has, BUT, it should also expose more of what the API is about"). The feed and its headlines declare one card
(`apis`, from `apis.py`: `MASSIVE_REST`), Massive's REST API as Massive's pages said on 2026-11-11: what it is and
for, its address, the key's form (a bearer token), its limits (5 requests a minute per asset class on a free plan, none
on a paid one), its plans' prices, and Massive's pages (the documentation, the REST quickstart, the knowledge base, the
request limits, pricing, the status pages, the changelog, the API keys page, the Python client, the terms). Its 20
parts, each asset class's sections with the WebSockets and the Flat Files, say what is used here (9) and what is not;
its 32 calls the 14 made here, each with what for, beside the notable others. `signup` is the API keys page's address
(a link on the Plugins view). `api_facts` says nothing (the contract's): the plugin holds no run's state. Tests: the
card names every call its client makes and none it does not; every address on it answers (with
`LIMINAL_VENDOR_PAGES=1`). Nothing it fetches changed. Requires liminal-libs 1.49.0.

## 0.2.0 (2026-11-03)

Renamed `plugin-integrator-massive` (the package `plugin_integrator_massive`; it was `liminal-plugin-massive`) on 2026-11-03: the naming by system (plugins are `plugin-<app>-<name>`), on liminal-libs 1.4.0 (`liminal_libs`, the library renamed with it).

A class on plugin API 2.0 (liminal-libs 1.3.0; the user: "all the plugins under liminal should basically
follow inheritance/oop paradigm"), versioned 0.2.0 with Liminal's release (every distribution at 0.2.0 on
a `release/0.2.0` branch). The feed is `MassivePlugin`, a `FeedPlugin` subclass (`PLUGIN`, its
instance), its headlines `MassiveHeadlines`, a `PublisherPlugin` subclass (`PUBLISHER`): what each
declares is a class attribute of the record field's name, what it does a method of the callback's
(`settings`, `view`, `build`, `scan`, `has_keys`, `serves`, `markets`, `plan_resolutions`; the
headlines' `read`, once `read_headlines`). The feed declares its plans' publication delays itself
(`MassivePlugin.delays`: the free, Starter, Developer and Advanced rows the library's `freshness.py`
held for it). Nothing it does changed: the same settings, requests, scan, strings and limits.

## 1.4.1 (2026-11-02)

The plugin imports the library as `liminal_libs` and depends on liminal-libs (the app, renamed liminal-charts, is no longer needed to run the tests; the user, 2026-11-02: "lets rename the app to liminal-charts").

## 1.4.0 (2026-11-01)

- Released as its own package, `plugin-integrator-massive`, registered under the entry point group
  `liminal.providers` (its feed and its headlines publisher); its version is the distribution's.
- Its settings are its own (plugin API 1.11, `Provider.settings`): the key, the plans (`TIERS`, the
  stocks plan and each other class's), `MASSIVE_RPM`, `MASSIVE_BASE_URL` and the request caps, once
  the app's base settings (`Settings.api_key`, `tier`, `base_url`, the caps' defaults), are read from
  the variables the app loads and reached with `settings.plugin("massive")`; the plan probe's
  reading of a plan (`tier_for`) is in the package.

## 1.3.0 (2026-10-31)

- Built into the app (then massive-collate): its headlines publisher declares where it writes (the
  main file's news; plugin API 1.8).

## 1.2.0 and before

- Built into the app (then massive-collate): its client on the app's HTTP client (API 1.6), its
  headlines a part of it (API 1.2); see the app's history.
