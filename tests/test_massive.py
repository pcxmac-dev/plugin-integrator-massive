"""Massive's plugin, tested on its own: its client's requests (a fake session answers; nothing is
sent), its settings and plans, its scan, its headlines, and that the app loads it from this package as
its classes (plugin API 2.2: MassivePlugin, MassiveHeadlines)."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from importlib.metadata import version
from pathlib import Path
from types import SimpleNamespace

import pytest

import plugin_integrator_massive as massive
from liminal_libs import freshness
from liminal_libs.config import ConfigError, Settings, asset_tier, load_settings
from liminal_libs.models import ETF
from liminal_libs.sources import build_source, feed_profiles, markets, provider, publishers, rate_window, registry, supports
from liminal_libs.symbols import resolve
from plugin_integrator_massive import (ASSETS, MASSIVE_CLASS_TIERS, PLUGIN, PUBLISHER, TIERS, MassiveHeadlines, MassivePlugin,
                                    MassiveSettings, tier_for)
from plugin_integrator_massive.client import MassiveClient, MassiveSource, asset_class

from .conftest import FakeResponse, FakeSession


def _source(responses):
    session = FakeSession(responses)
    return MassiveSource(MassiveClient("KEY", session=session, sleep=lambda s: None)), session


# -- its requests (once the app's tests/test_massive_source.py) -----------------------------------------
def test_probe_costs_exactly_one_request():
    src, session = _source([FakeResponse(200, {"results": [{}], "next_url": "https://api.massive.com/n"})])
    assert src.is_entitled("trades", "SPCX") is True
    assert src.requests_made == 1
    url, params, _ = session.calls[0]
    assert url.endswith("/v3/trades/SPCX") and params["limit"] == 1


def test_probe_refused_means_not_entitled():
    src, _ = _source([FakeResponse(403, {"message": "NOT_AUTHORIZED"})])
    assert src.is_entitled("second", "SPCX") is False


def test_bar_request_shape():
    src, session = _source([FakeResponse(200, {"results": [{"t": 1}]})])
    pages = list(src.bar_pages("spcx", date(2025, 1, 1), date(2025, 2, 1), "second", descending=True))
    assert pages == [[{"t": 1}]]
    url, params, _ = session.calls[0]
    assert url == "https://api.massive.com/v2/aggs/ticker/SPCX/range/1/second/2025-01-01/2025-02-01"
    assert params == {"adjusted": "true", "sort": "desc", "limit": 50000}


def test_trade_request_window():
    src, session = _source([FakeResponse(200, {"results": []})])
    list(src.trade_pages("SPCX", gte_ns=10, lt_ns=20, descending=True))
    _, params, _ = session.calls[0]
    assert params["timestamp.gte"] == 10 and params["timestamp.lt"] == 20 and params["order"] == "desc"


EXCHANGES = {"results": [
    {"id": 4, "name": "Nasdaq", "mic": "XNAS", "locale": "us", "type": "exchange"},
    {"id": 12, "name": "NYSE Arca", "mic": "ARCX", "locale": "us", "type": "exchange"},
]}


def test_exchanges_carry_country():
    src, _ = _source([FakeResponse(200, EXCHANGES)])
    ex = src.exchanges()
    assert [e.name for e in ex] == ["Nasdaq", "NYSE Arca"]
    assert ex[0].country.code == "US" and ex[0].timezone == "America/New_York"


def test_instrument_resolves_kind_and_exchange():
    details = {"results": {"ticker": "SPCX", "name": "SPAC ETF", "type": "ETF", "primary_exchange": "ARCX",
                           "locale": "us", "currency_name": "usd"}}
    src, _ = _source([FakeResponse(200, details), FakeResponse(200, EXCHANGES)])
    inst = src.instrument("spcx")
    assert isinstance(inst, ETF)
    assert inst.primary_exchange.name == "NYSE Arca" and inst.country.code == "US" and inst.currency == "USD"


def test_each_request_is_counted_against_its_asset_class():
    assert asset_class("https://api.massive.com/v2/aggs/ticker/X:BTCUSD/range/1/minute/a/b") == "crypto"
    assert asset_class("https://api.massive.com/v2/aggs/ticker/C%3AEURUSD/range/1/day/a/b") == "fx"
    assert asset_class("/v3/reference/tickers/I:SPX") == "index"
    assert asset_class("/futures/v1/aggs/ESZ6") == "future"
    assert asset_class("/v2/aggs/grouped/locale/global/market/crypto/2026-10-23") == "crypto"
    assert asset_class("/v2/aggs/ticker/AAPL/range/1/minute/a/b") == "stock"


# -- its settings and plans (its own, the `settings` hook, read with the app's) --------------------------
def test_its_settings_are_its_own_read_with_the_apps_and_a_bad_value_stops_the_app():
    s = load_settings(env={"MASSIVE_API_KEY": " k-1\n", "MASSIVE_TIER": "starter", "MASSIVE_TIER_FUTURES": "developer",
                           "MASSIVE_MAX_REQUESTS_PER_RUN": "7", "MASSIVE_BASE_URL": "https://proxy.example/"}, env_file=None)
    own = s.plugin("massive")
    assert isinstance(own, MassiveSettings) and own.api_key == "k-1"  # stripped: a pasted line break failed every request
    assert own.tier.name == "starter" and dict(own.tier.by_asset) == {  # every class on another plan than the stocks'
        "index": TIERS["free"], "fx": TIERS["free"], "crypto": TIERS["free"], "future": TIERS["developer"]}
    assert own.base_url == "https://proxy.example" and (own.max_requests_per_run, own.max_requests_per_day) == (7, 2000)
    assert "k-1" not in repr(own) and "k-1" not in repr(s)  # never printed
    feed = s.for_source("massive")  # the app's settings as this feed sees them: its plans and caps
    assert feed.tier is own.tier and feed.max_requests_per_run == 7 and feed.plugin("massive") is own
    free = PLUGIN.settings({})
    assert free.api_key is None and free.tier == TIERS["free"] and (free.max_requests_per_run, free.max_requests_per_day) == (250, 2000)
    assert PLUGIN.settings({"MASSIVE_TIER": "  "}).tier.name == "free"  # set but empty: the default
    assert PLUGIN.settings({"MASSIVE_RPM": "0"}).tier.requests_per_minute is None  # 0: unlimited
    assert PLUGIN.settings({"MASSIVE_RPM": "12", "MASSIVE_TIER": "advanced"}).tier.requests_per_minute == 12
    with pytest.raises(ConfigError, match="MASSIVE_API_KEY"):
        free.require_api_key()
    for bad in ({"MASSIVE_TIER": "platinum"}, {"MASSIVE_TIER_CRYPTO": "gold"}, {"MASSIVE_MAX_REQUESTS_PER_DAY": "-1"},
                {"MASSIVE_RPM": "five"}):
        with pytest.raises(ConfigError):
            PLUGIN.settings(bad)
        with pytest.raises(ConfigError):
            load_settings(env=bad, env_file=None)  # the app's settings refuse it too, as they load


def test_a_plan_per_asset_class_and_the_probe_that_names_the_stocks_plan():
    tier = PLUGIN.settings({"MASSIVE_TIER": "advanced", "MASSIVE_TIER_FUTURES": "starter"}).tier
    assert asset_tier(tier, "stock") is tier and asset_tier(tier, "future").name == "starter"
    assert asset_tier(tier, "crypto").name == "free"  # the stocks plan does not reach the other classes
    assert tier.history_start == date(2003, 9, 10) and tier.history_years is None  # all of Massive's stock history
    assert tuple(TIERS) == ("free", "starter", "developer", "advanced") and TIERS["free"].requests_per_minute == 5
    assert [tier_for({k: True}) for k in ("quotes", "day_11y", "day_21y")] == ["advanced"] * 3
    assert [tier_for({k: True}) for k in ("trades", "day_6y")] == ["developer"] * 2
    assert [tier_for({k: True}) for k in ("day_3y", "second")] == ["starter"] * 2
    assert tier_for({}) == "free" and tier_for({"quotes": False, "trades": True, "day_3y": True}) == "developer"


def test_its_scan_finds_the_stocks_plan_and_leaves_the_other_classes_to_you():
    reach = {"day_3y": True, "day_6y": True, "day_11y": False, "day_21y": False, "second": True, "trades": True,
             "quotes": False}
    found = PLUGIN.scan(SimpleNamespace(plan_reach=lambda ticker: reach))
    assert found.plan == {"MASSIVE_TIER": "developer"}
    assert found.results[-1] == ("stocks plan: developer", True, "10 years of history")
    assert found.results[0] == ("stock daily bars 3 years back (Starter and up)", True, "")
    assert [ok for _, ok, _ in found.results[:-1]] == list(reach.values())
    assert PLUGIN.plan_vars[0] == "MASSIVE_TIER" and set(MASSIVE_CLASS_TIERS.values()) <= set(PLUGIN.plan_vars)
    assert PLUGIN.plan_choices["MASSIVE_TIER"] == tuple(TIERS)
    assert "MASSIVE_TIER_FUTURES" in PLUGIN.plan_note and "5 requests a minute" in PLUGIN.plan_note


def test_it_builds_its_client_on_its_own_key_plans_and_caps():
    s = load_settings(env={"MASSIVE_API_KEY": "k", "MASSIVE_TIER": "advanced", "MASSIVE_BASE_URL": "https://proxy.example/"},
                      env_file=None)
    src = build_source("massive", s, request_budget=9)
    assert isinstance(src, MassiveSource) and src.client.base_url == "https://proxy.example"
    assert src.client._limiter.max_calls is None  # stocks: unlimited on Advanced
    assert set(src.client.class_limiters) == {"index", "fx", "crypto", "future"}
    assert src.client.class_limiters["crypto"].max_calls == 5  # crypto: the free plan's 5 a minute
    free = build_source("massive", load_settings(env={"MASSIVE_API_KEY": "k"}, env_file=None), request_budget=1)
    assert free.client._limiter.max_calls == 5 and free.client.class_limiters == {}  # one plan: no class windows
    with pytest.raises(ConfigError, match="MASSIVE_API_KEY"):
        build_source("massive", load_settings(env={}, env_file=None))
    with pytest.raises(ConfigError, match="Massive settings"):
        PLUGIN.build(Settings(db_path=Path("x.db")), 1)  # settings made directly: none of its own


# -- the app loads it from this package --------------------------------------------------------------------
def own_version(origin: str) -> str:
    """This distribution's version as the registry read it: its checkout's pyproject.toml when loaded from the
    workspace's plugin directory, else the installed package's (an editable install's record keeps the version it
    was installed at until it is installed again)."""
    if origin.startswith("plugins/"):
        import tomllib

        return tomllib.loads((Path(__file__).parents[1] / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
    return version("plugin-integrator-massive")


def test_the_app_loads_it_and_its_headlines_from_this_package_with_its_own_version():
    registry.reload()
    p = provider("massive")
    assert p is not None, dict(registry.errors())
    assert p.origin in {"package: plugin-integrator-massive (plugin_integrator_massive)", "plugins/plugin-integrator-massive (plugin_integrator_massive)"}  # its package, or its checkout in the workspace\'s plugin directory
    assert p.version == own_version(p.origin) and p.api == "2.2" and registry.api_refusal(p.api) is None
    assert PLUGIN.version == "" and PLUGIN.has_settings
    news = publishers()["massive-news"]
    assert (news.origin, news.version, news.api) == (p.origin, p.version, p.api)  # one plugin: released with it
    assert news.part_of == "massive" and news.account == "massive" and news.reads_itself
    assert not [why for where, why in registry.errors() if "massive" in where or "massive" in why]
    row = {r["name"]: r for r in registry.menu()}["massive"]
    assert (row["version"], row["api"]) == (own_version(p.origin), "2.2")
    assert registry.plugin_feeds("massive") == ["massive"] and registry.plugin_of("massive") == "massive"


def test_it_is_a_class_on_plugin_api_2_2_and_the_app_loads_it_as_one():
    assert isinstance(PLUGIN, MassivePlugin) and isinstance(PUBLISHER, MassiveHeadlines)
    assert PLUGIN.api == "2.2" == PUBLISHER.api and not PLUGIN.is_record and not PUBLISHER.is_record
    assert PLUGIN.has_scan and PLUGIN.has_settings and PLUGIN.gives("view") and PLUGIN.gives("build")
    assert PLUGIN.gives("has_keys") and PLUGIN.gives("serves") and PLUGIN.gives("markets") and PLUGIN.gives("plan_resolutions")
    assert not PLUGIN.gives("rate") and not PLUGIN.gives("carries") and not PLUGIN.gives("reporter")  # the contract's defaults
    assert PUBLISHER.reads_itself and not PUBLISHER.has_calendar and not PUBLISHER.has_moments and not PUBLISHER.has_settings
    assert PLUGIN.settings_of({}) == PLUGIN.settings({}) and PUBLISHER.settings_of({}) is None
    # its plans' publication delays, the library's rows for Massive, declared by the feed (2.0)
    assert set(PLUGIN.delays) == set(TIERS) and PLUGIN.hours == {}
    registry.reload()
    assert freshness.plan_delay(TIERS["free"], "stock").kind == "eod" and freshness.plan_delay(TIERS["free"], "fx").kind == "utc_day"
    assert freshness.plan_delay(TIERS["starter"], "stock").lag == timedelta(minutes=15)
    assert freshness.plan_delay(TIERS["advanced"], "crypto").describe() == "real time"
    assert freshness.plan_delay(TIERS["developer"], "future").lag == timedelta(hours=8)
    assert freshness.DELAYS.declare(PLUGIN) is False  # declared already, the same rows: nothing changes
    # the registry loads them as the classes: a copy each (its origin and version set), the same type
    p, news = registry.providers()["massive"], registry.publishers()["massive-news"]
    assert type(p) is MassivePlugin and type(news) is MassiveHeadlines and p is not PLUGIN and p.api == "2.2"
    assert p.has_scan and p.has_settings and news.reads_itself and p.with_(scan=None).has_scan is False and PLUGIN.has_scan
    assert repr(PLUGIN) == "<MassivePlugin 'massive': built in>" and repr(p).startswith("<MassivePlugin 'massive': ")


def test_it_keeps_the_facts_it_had_built_in():
    registry.reload()
    s = load_settings(env={"MASSIVE_API_KEY": "k"}, env_file=None)
    assert rate_window("massive", s) == (5, 62.0)  # the free plan's five a minute, with its margin
    paid = load_settings(env={"MASSIVE_API_KEY": "k", "MASSIVE_TIER": "developer"}, env_file=None)
    assert provider("massive").rate_window(paid)[0] is None
    assert markets("massive", s) == {"stock": "sip", "index": "index", "fx": "otc", "crypto": "consolidated", "future": "cme"}
    assert supports("massive", resolve("AAPL")) and supports("massive", resolve("BTCUSD"))
    assert "massive" not in feed_profiles(load_settings(env={}, env_file=None))  # not set up at all without its key
    keyed = feed_profiles(s)
    assert keyed["massive"].assets == set(ASSETS) and keyed["massive"].tier == TIERS["free"]
    p = provider("massive")
    assert [k.name for k in p.keys] == ["MASSIVE_API_KEY"] and p.kind == "consolidated" and p.order == 0
    assert p.bulk_resolution == {"stock": "second", "future": "minute"}
    assert p.plan_resolutions(TIERS["free"], "stock") == ("day", "minute")
    assert p.plan_resolutions(TIERS["starter"], "stock") == ("day", "minute", "second")
    assert p.plan_resolutions(PLUGIN.settings({"MASSIVE_TIER": "starter"}).tier, "crypto") == ("day", "minute")  # crypto: still free
    assert PUBLISHER.feeds[0].every_minutes == 30 and PUBLISHER.policy.per_day == 60 and PUBLISHER.databases[0].shared


def test_its_headlines_are_read_on_its_key_once_a_read_and_counted_on_its_day(monkeypatch):
    rows = [{"id": "n1", "published_ms": 1_761_000_000_000, "title": "Headline", "publisher": "Wire",
             "url": "https://x/1", "tickers": ["AAPL"]}]
    asked, built, counted, kept = [], [], [], {}
    fake = SimpleNamespace(client=SimpleNamespace(on_request=None), news=lambda since, limit: asked.append((since, limit)) or rows)
    monkeypatch.setattr(massive.MassivePlugin, "build",
                        lambda self, settings, budget, max_retries=4: built.append((settings.tier.name, budget, max_retries)) or fake)
    now = datetime(2026, 10, 24, 12, tzinfo=timezone.utc)
    store = SimpleNamespace(latest_news_ms=lambda feed: None, save_news=lambda feed, items: len(list(items)),
                            kv_set=lambda k, v: kept.__setitem__(k, v),
                            count_request=lambda feed, now=None: counted.append((feed, now)))
    ctx = SimpleNamespace(settings=load_settings(env={"MASSIVE_API_KEY": "k", "MASSIVE_TIER": "starter"}, env_file=None),
                          store=store, now=now, count=lambda n: counted.append(n))
    assert massive.PUBLISHER.read(ctx) == 1
    assert built == [("starter", 1, 0)]  # its own view of the settings, a budget of one, never retried here
    assert asked == [(now - timedelta(days=massive.NEWS_DAYS), 100)]  # the first read reaches two days back
    fake.client.on_request(1)
    assert counted == [("massive", now), 1] and kept == {"news:massive": now.isoformat()}
    store.latest_news_ms = lambda feed: 1_761_000_000_000  # from then on: since the newest kept
    massive.PUBLISHER.read(ctx)
    assert asked[-1] == (datetime.fromtimestamp(1_761_000_000, timezone.utc), 100)
