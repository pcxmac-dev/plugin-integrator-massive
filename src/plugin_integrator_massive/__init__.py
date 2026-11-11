"""Massive (massive.com, formerly Polygon.io) for Liminal: stocks, indices, currencies, crypto and
futures, one plan per asset class; and its headlines, a publisher in this plugin.

A Liminal plugin released on its own, registered under the entry point group `liminal.providers` as
`massive`: a class each on the class contract (plugin API 2.2, liminal_libs.sources.plugin): its feed
`MassivePlugin` (a FeedPlugin: what it declares class attributes, what it does methods; the instance
PLUGIN) and its headlines `MassiveHeadlines` (a PublisherPlugin; PUBLISHER). Its key, plans and caps
are its own settings (MassiveSettings, from the variables the app read: the `settings` hook), reached
with `settings.plugin("massive")`; its view of the app's settings (Settings.for_source("massive"))
carries its plan and caps. It relies on plugin API 2.2 and nothing of the app outside the contract
(docs/ARCHITECTURE.md in liminal: "Providers are plugins"); its version is this distribution's
(pyproject.toml), so the classes' versions are left empty.

Its scan finds the stocks plan from what the key may ask for (MassiveSource.plan_reach) and sets
MASSIVE_TIER where you have not. The other classes' plans are not probed (PLAN_NOTE).

Its headlines are a publisher in this plugin (PUBLISHER, part_of="massive": a section of Massive's
page in the Plugins view, never a plugin of their own; read by the app's publications.py every 30
minutes), on this feed's key and limits, released with it (its version and contract).

What it attaches to (plugin API 2.2, `apis`: the card in apis.py, the feed's and the headlines' alike):
Massive's REST API, its documentation and pricing pages, every part of it (each asset class's sections,
the WebSockets, the Flat Files) said used here or not, and its calls, the ones made here first. What it
learned of the API while it ran it does not say (api_facts, the contract's: nothing): the instance holds
no run's state, the requests and limits of a run are its client's and the machine's ledgers'.

Settings (user environment variables; the key is only ever read from the environment):
    MASSIVE_API_KEY   required for any request
    MASSIVE_TIER      free | starter | developer | advanced   (default: free): your Stocks plan; sets
                      the history the collector reaches back to. The scan (`liminal-charts capabilities massive`)
                      finds it
    MASSIVE_TIER_INDICES / _CURRENCIES / _CRYPTO / _FUTURES   the plan of each other asset class
                      (Massive sells one per class; default: free)
    MASSIVE_RPM       override the tier's requests-per-minute limit (0 = unlimited)
    MASSIVE_BASE_URL  API base URL (default: Massive's own)
    MASSIVE_MAX_REQUESTS_PER_RUN   hard cap on API requests in one command (default: 250)
    MASSIVE_MAX_REQUESTS_PER_DAY   hard cap on API requests per day, all runs (default: 2000)
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, timedelta
from typing import Mapping

from liminal_libs.config import ConfigError, Tier, asset_tier
from liminal_libs.freshness import Delay
from liminal_libs.sources.publisher import Feed, Policy, PublisherPlugin
from liminal_libs.sources.registry import (MAIN, Database, FeedPlugin, KeyVar, MachineLedger, RateLimiter, Scanned, limiter,
                                          machine_caps, minute_window)
from .apis import APIS, KEYS
from .client import BASE_URL, PAGE_LIMIT, MassiveClient, MassiveSource

ASSETS = ("stock", "index", "fx", "crypto", "future")  # its asset classes, each on a plan of its own
KEY = "MASSIVE_API_KEY"

# Massive's stocks plans (massive.com/pricing), a little inside their published rates.
TIERS: dict[str, Tier] = {
    "free": Tier("free", requests_per_minute=5, history_years=2),
    "starter": Tier("starter", requests_per_minute=None, history_years=5),
    "developer": Tier("developer", requests_per_minute=None, history_years=10),
    # Advanced: all of Massive's stock history, which begins 2003-09-10 (`plan`, 2026-10-24).
    "advanced": Tier("advanced", requests_per_minute=None, history_years=None, history_start=date(2003, 9, 10)),
}
# The variables naming Massive's plan for each asset class besides stocks (MASSIVE_TIER).
MASSIVE_CLASS_TIERS = {"index": "MASSIVE_TIER_INDICES", "fx": "MASSIVE_TIER_CURRENCIES",
                       "crypto": "MASSIVE_TIER_CRYPTO", "future": "MASSIVE_TIER_FUTURES"}


def tier_for(reach: dict[str, bool]) -> str:
    """The Massive stocks plan (TIERS) a plan probe's reach matches (MassiveSource.plan_reach):
    Advanced has quotes and more than 10 years, Developer trades and 10 years, Starter 5 years,
    the free plan 2."""
    if reach.get("quotes") or reach.get("day_11y") or reach.get("day_21y"):
        return "advanced"
    if reach.get("trades") or reach.get("day_6y"):
        return "developer"
    if reach.get("day_3y") or reach.get("second"):
        return "starter"
    return "free"


# plan_reach's answers, and the plans that have each (tier_for)
REACH = {"day_3y": "stock daily bars 3 years back (Starter and up)",
         "day_6y": "stock daily bars 6 years back (Developer and up)",
         "day_11y": "stock daily bars 11 years back (Advanced)",
         "day_21y": "stock daily bars 21 years back (Advanced)",
         "second": "stock 1-second bars (the paid plans)",
         "trades": "stock trades (Developer and up)",
         "quotes": "stock quotes (Advanced)"}
PLAN_NOTE = ("only the stocks plan (MASSIVE_TIER) is probed: the other asset classes' plans "
             f"({', '.join(MASSIVE_CLASS_TIERS.values())}) are what you set, free unless you do. "
             "A free class is held to 5 requests a minute, and a probe that took one for paid would lift that")


@dataclass(frozen=True)
class MassiveSettings:
    """The plugin's own settings (Settings.plugin("massive")): its key, its plans (the stocks plan,
    with the other classes' as the tier's by_asset) and its caps, from the variables the app read."""
    api_key: str | None
    tier: Tier
    base_url: str = ""  # MASSIVE_BASE_URL; empty: Massive's own
    max_requests_per_run: int = 250
    max_requests_per_day: int = 2000

    def __repr__(self) -> str:  # never print the key
        classes = ", ".join(f"{a}={t.name}" for a, t in self.tier.by_asset)
        return (f"MassiveSettings(key={'set' if self.api_key else 'not set'}, tier={self.tier.name}"
                f"{', ' + classes if classes else ''}, caps={self.max_requests_per_run}/{self.max_requests_per_day})")

    def require_api_key(self) -> str:
        if not self.api_key:
            raise ConfigError(f"{KEY} is not set. Set it in your environment or in a .env file (see .env.example).")
        return self.api_key


def _int(variables: Mapping[str, str], name: str) -> int | None:
    raw = (variables.get(name) or "").strip()
    if not raw:
        return None
    try:
        value = int(raw)
    except ValueError as e:
        raise ConfigError(f"{name} must be a whole number, got {raw!r}") from e
    if value < 0:
        raise ConfigError(f"{name} must not be negative")
    return value


def _own(settings) -> MassiveSettings:
    m = settings.plugin("massive")
    if m is None:
        raise ConfigError("Massive settings missing")
    return m


class MassivePlugin(FeedPlugin):
    """Massive's feed: its plans (one per asset class), its client on its own key and caps, its scan
    of the stocks plan, and its own settings (plugin API 2.0: a FeedPlugin subclass; the record it
    was until 1.4.1 became this class, a field an attribute, a callback a method); what it attaches to
    (2.2: `apis`)."""

    api = "2.2"  # the contract it is written for (the classes; its own settings; its headlines' database; its API's card); its version: the distribution's
    name = "massive"
    title = "Massive"
    about = "stocks, indices, currencies, crypto and futures: 1-second and minute bars, reference data, news"
    order = 0
    assets = frozenset(ASSETS)
    keys = (KeyVar(KEY),)
    signup = KEYS  # the dashboard's API keys page (the card's console link)
    apis = APIS  # Massive's REST API (apis.py), with its headlines'
    plan_vars = ("MASSIVE_TIER", *MASSIVE_CLASS_TIERS.values(), "MASSIVE_MAX_REQUESTS_PER_RUN",
                 "MASSIVE_MAX_REQUESTS_PER_DAY")
    plan_choices = {v: tuple(TIERS) for v in ("MASSIVE_TIER", *MASSIVE_CLASS_TIERS.values())}
    plan_note = PLAN_NOTE
    kind = "consolidated"
    venue_notes = {"crypto": "consolidated across exchanges"}
    # every stock's year of 1-second bars after its minute history (the user, 2026-10-28: "all 7,800");
    # futures at minutes
    bulk_resolution = {"stock": "second", "future": "minute"}
    per_request = {"day": PAGE_LIMIT, "minute": PAGE_LIMIT, "second": PAGE_LIMIT}
    # When each plan publishes (the rows the library's freshness.PLAN_DELAYS held for Massive, declared
    # by the feed itself since 2.0). Observed on Massive, Oct 2026: the free plan's stocks and indices
    # at the end of the day (a session's minute bars appear overnight), its currencies and crypto
    # through the end of the previous UTC day; futures (Basic) 8 hours delayed; the paid stock plans 15
    # minutes delayed (Starter, Developer) or real time (Advanced).
    delays = {
        "free": {"stock": Delay("eod"), "index": Delay("eod"), "fx": Delay("utc_day"), "crypto": Delay("utc_day"),
                 "future": Delay("delay", timedelta(hours=8))},
        "starter": {"stock": Delay("delay", timedelta(minutes=15)), "index": Delay("delay", timedelta(minutes=15)),
                    "fx": Delay("delay", timedelta(minutes=15)), "crypto": Delay("delay", timedelta(minutes=15)),
                    "future": Delay("delay", timedelta(hours=8))},
        "developer": {"stock": Delay("delay", timedelta(minutes=15)), "index": Delay("delay", timedelta(minutes=15)),
                      "fx": Delay("delay", timedelta(minutes=15)), "crypto": Delay("delay", timedelta(minutes=15)),
                      "future": Delay("delay", timedelta(hours=8))},
        "advanced": {"stock": Delay("delay"), "index": Delay("delay"), "fx": Delay("delay"), "crypto": Delay("delay"),
                     "future": Delay("delay", timedelta(hours=8))},
    }

    def settings(self, variables: Mapping[str, str]) -> MassiveSettings:
        """The plugin's settings from every variable the app read (the `settings` hook); a value it
        refuses is a ConfigError, which stops the app as any setting's does."""
        tier_name = (variables.get("MASSIVE_TIER") or "").strip().lower() or "free"  # set but empty: the default
        if tier_name not in TIERS:
            raise ConfigError(f"Unknown MASSIVE_TIER {tier_name!r}; choose one of {', '.join(TIERS)}")
        tier = TIERS[tier_name]
        rpm = _int(variables, "MASSIVE_RPM")
        if rpm is not None:
            tier = replace(tier, requests_per_minute=rpm or None)
        classes = []
        for asset, var in MASSIVE_CLASS_TIERS.items():
            name = (variables.get(var) or "free").strip().lower()
            if name not in TIERS:
                raise ConfigError(f"Unknown {var} {name!r}; choose one of {', '.join(TIERS)}")
            if name != tier.name:
                classes.append((asset, TIERS[name]))
        tier = replace(tier, by_asset=tuple(classes))
        per_run = _int(variables, "MASSIVE_MAX_REQUESTS_PER_RUN")
        per_day = _int(variables, "MASSIVE_MAX_REQUESTS_PER_DAY")
        return MassiveSettings(
            api_key=(variables.get(KEY) or "").strip() or None,  # spaces and line breaks around a pasted key taken off
            tier=tier, base_url=(variables.get("MASSIVE_BASE_URL") or "").rstrip("/"),
            max_requests_per_run=250 if per_run is None else per_run,
            max_requests_per_day=2000 if per_day is None else per_day,
        )

    def view(self, base):
        """The app's settings as this feed sees them: its plans (every asset class's) and its caps."""
        m = base.plugin("massive")
        if m is None:
            return base
        return replace(base, tier=m.tier, max_requests_per_run=m.max_requests_per_run,
                       max_requests_per_day=m.max_requests_per_day, origin=base)

    def build(self, settings, request_budget, max_retries: int = 4):
        m = _own(settings)
        key = m.require_api_key()
        client = MassiveClient(
            key,
            base_url=m.base_url or BASE_URL,  # MASSIVE_BASE_URL, else its own
            rate_limiter=limiter("massive", settings, key),
            request_budget=request_budget,
            max_retries=max_retries,
        )
        # Asset classes on another plan keep that plan's rate (the free plan: 5 a minute per class),
        # with the same margin as the feed's own window.
        client.class_limiters = {}
        for a, t in m.tier.by_asset:
            client.class_limiters[a] = RateLimiter(t.requests_per_minute, minute_window(t.requests_per_minute))
            client.class_limiters[a].share(MachineLedger(f"massive:{a}", key))
        return MassiveSource(machine_caps(client, "massive", settings, key))

    def scan(self, source) -> Scanned:
        """The stocks plan the key has (seven small requests, AAPL's): daily bars 3, 6, 11 and 21 years
        back, then the last week's 1-second bars, trades and quotes."""
        reach = source.plan_reach("AAPL")
        found = tier_for(reach)
        rows = [(REACH.get(k, k), ok, "") for k, ok in reach.items()]
        years = TIERS[found].history_years
        rows.append((f"stocks plan: {found}", True, f"{years} years of history" if years else "all of Massive's history"))
        return Scanned(tuple(rows), {"MASSIVE_TIER": found})

    def has_keys(self, settings) -> bool:
        m = settings.plugin("massive")
        return bool(m and m.api_key)

    def serves(self, settings):
        return frozenset(ASSETS) if self.has_keys(settings) else None  # not set up at all without its key

    def markets(self, settings):
        return {"stock": "sip", "index": "index", "fx": "otc", "crypto": "consolidated", "future": "cme"}

    def plan_resolutions(self, tier, asset):
        # 1-second bars on a paid plan of the asset class (the free plan: day and minute bars, 2 years)
        return ("day", "minute") if asset_tier(tier, asset).name == "free" else ("day", "minute", "second")


PLUGIN = MassivePlugin()

NEWS_DAYS = 2  # the first read reaches this far back


class MassiveHeadlines(PublisherPlugin):
    """Massive's headlines, a publisher in this plugin: read by itself (`read`) on the feed's key and
    limits, into the main database's news."""

    api = MassivePlugin.api  # one plugin: Massive's release and contract (its version: the distribution's)
    apis = APIS  # the feed's card: the news endpoint among its calls, used by these headlines
    name = "massive-news"
    title = "Massive headlines"
    about = "news headlines for the News view and the globe's ticker, on Massive's key and limits"
    order = 300
    kind = "vendor"
    account = "massive"
    part_of = "massive"
    feeds = (Feed("massive-news", "Massive", "Headlines", f"{BASE_URL}/v2/reference/news", "headlines",
                  every_minutes=30, moments=False),)
    policy = Policy(min_minutes=30, per_day=60, terms="your Massive plan's terms; one request a read",
                    terms_url="https://massive.com/terms")
    databases = (Database(MAIN, "Massive headlines: the news", shared=True),)  # `read` saves them there

    def read(self, ctx) -> int:
        """Massive's newest headlines (one request, on Massive's limits: its rate window, daily cap and
        kills), into the main database's news for the News view and the globe's ticker. Returns how many.
        Never retried here: a 429 is the account's to answer (RateLimited kills it), anything else the
        reader's to ask again on its schedule (with a budget of one, a retry only failed again)."""
        from datetime import datetime, timedelta, timezone

        source = PLUGIN.build(ctx.settings.for_source("massive"), 1, max_retries=0)
        source.client.on_request = lambda n: (ctx.store.count_request("massive", now=ctx.now), ctx.count(1))
        newest = ctx.store.latest_news_ms("massive")
        since = datetime.fromtimestamp(newest / 1000, timezone.utc) if newest else ctx.now - timedelta(days=NEWS_DAYS)
        n = ctx.store.save_news("massive", source.news(since, 100))
        ctx.store.kv_set("news:massive", ctx.now.isoformat())  # the Fetcher's "Headlines" row reads when
        return n


PUBLISHER = MassiveHeadlines()
