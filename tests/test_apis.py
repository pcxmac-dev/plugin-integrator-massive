"""What Massive's plugin attaches to (plugin API 2.2, apis.py): one sound card for its feed and its headlines alike, its
calls the ones the client really makes (a recording session answers every request; nothing is sent), and nothing asked
to say what it learned (api_facts). With LIMINAL_VENDOR_PAGES=1, every address on the card is asked once: the one test
here that sends anything (the plugins' page check)."""
from __future__ import annotations

import os
import re
from datetime import date
from urllib.parse import urlparse

import pytest

from liminal_libs.sources import registry
from liminal_libs.sources.apis import dead_links, problems, urls
from plugin_integrator_massive import PLUGIN, PUBLISHER
from plugin_integrator_massive.apis import APIS, KEYS, MASSIVE_REST
from plugin_integrator_massive.client import BASE_URL, MassiveClient, MassiveSource

from .conftest import FakeResponse

DAY = date(2026, 11, 10)
ICON = f"{BASE_URL}/branding/acme_icon.png"  # an address a ticker's record gives (branding.icon_url)


class Recording:
    """Answers every request with an empty page (a ticker's record for /v3/reference/tickers/<T>) and records it."""

    def __init__(self):
        self.asked: list[tuple[str, str]] = []

    def get(self, url, params=None, headers=None, timeout=None):
        self.asked.append(("GET", url))
        path = urlparse(url).path
        body = {"results": {"ticker": "AAPL", "type": "CS", "primary_exchange": "XNAS", "locale": "us"}} \
            if path == "/v3/reference/tickers/AAPL" else {"results": []}
        resp = FakeResponse(200, body, {"Content-Type": "image/png"})
        resp.content = b""
        return resp


def _pattern(template: str) -> re.Pattern:
    """A call's path as a pattern: each {placeholder} one path segment."""
    return re.compile("[^/]+".join(re.escape(part) for part in re.split(r"\{[^}]*\}", template)))


def _call_of(method: str, path: str) -> str | None:
    """The card's call a request is (its name), or None."""
    for call in MASSIVE_REST.calls:
        verb, _, template = call.name.partition(" ")
        if verb == method and template.startswith("/") and _pattern(template).fullmatch(path):
            return call.name
    return None


def _every_request(source: MassiveSource) -> None:
    """Every request its source makes, each kind once (the feed's and the headlines')."""
    source.plan_reach("AAPL", today=DAY)  # daily bars years back, 1-second bars, trades, quotes
    list(source.bar_pages("AAPL", DAY, DAY, "minute"))
    list(source.bar_pages("I:SPX", DAY, DAY, "day", asset="index"))
    list(source.bar_pages("ESZ6", DAY, DAY, "minute", asset="future"))
    list(source.trade_pages("AAPL"))
    source.instrument("AAPL")  # its record, then the exchanges its MIC is found among
    source.latest_bar("AAPL", DAY)
    source.market_holidays()
    source.futures_schedule("ES", DAY)
    source.news(None, 10)
    source.listings("XNAS")
    source.futures_products(DAY)
    source.trade_conditions()
    source.market_daily(DAY)


def test_its_card_names_every_call_its_client_makes_and_none_it_does_not():
    session = Recording()
    source = MassiveSource(MassiveClient("KEY", session=session, sleep=lambda s: None))
    _every_request(source)
    asked = [(m, urlparse(u).path) for m, u in session.asked]
    assert all(u.startswith(BASE_URL + "/") for _, u in session.asked)  # the card's base: every request's host
    unnamed = [f"{m} {p}" for m, p in asked if _call_of(m, p) is None]
    assert unnamed == []  # every request it made is a call on the card
    made = {_call_of(m, p) for m, p in asked}
    source.icon(ICON)  # a company's icon: at the address its record gives, not a path of the card's
    assert session.asked[-1] == ("GET", ICON)
    used = {c.name for c in MASSIVE_REST.used}
    assert used - made == {"GET branding.icon_url"}  # every call the card says it makes, it makes
    assert made <= used  # and the card says each is made here, what for
    assert {c.name for c in MASSIVE_REST.calls if not c.used} >= {"GET /v1/marketstatus/now", "GET /stocks/v1/splits"}


def test_one_sound_card_for_its_feed_and_its_headlines():
    assert APIS == (MASSIVE_REST,) and PLUGIN.apis is APIS and PUBLISHER.apis is APIS
    assert problems(APIS, today=DAY) == []
    assert MASSIVE_REST.docs == "https://massive.com/docs" and MASSIVE_REST.base == BASE_URL == "https://api.massive.com"
    assert PLUGIN.signup == KEYS == MASSIVE_REST.link("console")  # where a key is made: the card's console page
    kinds = {x.kind for x in MASSIVE_REST.links}
    assert {"docs", "limits", "pricing", "status", "changelog", "console", "terms"} <= kinds
    parts = {a.name for a in MASSIVE_REST.areas}
    assert {"Options", "Futures", "Indices", "Forex", "Crypto", "News", "WebSockets", "Flat Files"} <= parts
    assert {a.name for a in MASSIVE_REST.covered} >= {"Stocks: aggregates", "News", "Futures"}
    assert not [c for c in MASSIVE_REST.calls if c.writes or c.costs]  # it only reads; nothing on it starts a charge
    assert all(a.area in parts for a in MASSIVE_REST.calls)  # each call in a part the card names
    assert all(u.startswith("https://") for u in urls(APIS))
    assert MASSIVE_REST.verified == "2026-11-11"


def test_it_asks_nothing_to_say_what_it_learned():
    assert PLUGIN.api_facts() == {} and PUBLISHER.api_facts() == {}  # the instance holds no run's state
    registry.reload()
    p, news = registry.providers()["massive"], registry.publishers()["massive-news"]
    assert p.apis == APIS == news.apis and p.interface()["apis"] == ["Massive REST API"] == news.interface()["apis"]


@pytest.mark.skipif(os.environ.get("LIMINAL_VENDOR_PAGES") != "1", reason="asks Massive's pages (LIMINAL_VENDOR_PAGES=1)")
def test_every_address_on_its_card_answers():
    assert dead_links(APIS) == []
