"""What Massive's plugin attaches to (plugin API 2.2, liminal_libs.sources.apis): Massive's REST API, as its own pages
said on 2026-11-11 (massive.com/docs and its index, massive.com/docs/llms.txt; the pricing pages; the knowledge base's
request limits). One card for the whole plugin, its feed (`massive`) and its headlines (`massive-news`) alike: the app
draws a plugin's APIs and its parts' once each, by name.

The user, 2026-11-11: "each plugin should reflect the the API its attached to, and present links that provide
documentation, the plugin interface should more or less contain what it already has, BUT, it should also expose more of
what the API is about". So every part of the API is named (`areas`: the reference's sections, each asset class's), each
said used here or not, and the calls the plugin makes (`used`) beside the notable ones it does not."""
from __future__ import annotations

from liminal_libs.sources.apis import Api, Area, Call, Link

from .client import BASE_URL

DOCS = "https://massive.com/docs"
REST = f"{DOCS}/rest"
KEYS = "https://massive.com/dashboard/keys"  # where a key is made (the plugin's `signup`)
STOCKS, TICKERS, OPS = "Stocks: aggregates", "Stocks: tickers", "Stocks: market operations"
TRADES = "Stocks: trades and quotes"


def _rest(path: str) -> str:
    return f"{REST}/{path}"


MASSIVE_REST = Api(
    name="Massive REST API",
    maker="Massive (formerly Polygon.io)",
    about=("Massive's REST API serves US stocks, options, indices, currencies, crypto and futures: bars from one second "
           "to a year, tick-level trades and quotes, snapshots, reference data (tickers, exchanges, conditions, "
           "holidays), corporate actions, fundamentals, filings and news. Each asset class is sold as a plan of its own, "
           "and the plan sets how far back, how fresh and how fast it answers."),
    kind="rest",
    base=BASE_URL,
    version="v1, v2 and v3 endpoints; futures v1",
    auth=("an API key from the dashboard's API keys page, sent as an Authorization: Bearer header (the plugin's way; an "
          "apiKey query parameter works too); the WebSockets sign in with the same key, the Flat Files with S3 keys of "
          "their own"),
    limits=("a free (Basic) plan: 5 requests a minute, counted per asset class; an asset class on a paid plan has no "
            "request limit; a minute's requests spent: HTTP 429. Up to 50,000 bars a page (aggregates), 1,000 articles "
            "(news); one WebSocket connection per asset class"),
    costs=("each asset class is a plan of its own, a month: Stocks Basic free (2 years, end of day), Starter $29 (5 "
           "years, 15 minutes delayed, second bars), Developer $79 (10 years, trades), Advanced $199 (20+ years, real "
           "time, quotes); Options and Futures $29 and up, Indices and Currencies $49 and up (each with a free Basic "
           "plan); Financials & Ratios $29; a year's billing 20% less. The requests themselves cost nothing more"),
    links=(
        Link("Documentation", DOCS, "docs"),
        Link("REST quickstart", _rest("quickstart"), "guide"),
        Link("Knowledge base", "https://massive.com/knowledge-base", "guide"),
        Link("Request limits", "https://massive.com/knowledge-base/article/what-is-the-request-limit-for-massives-restful-apis",
             "limits"),
        Link("Pricing", "https://massive.com/pricing", "pricing"),
        Link("System status", "https://massive.com/system", "status"),
        Link("Status alerts and incidents", "https://massive-status.com/", "status"),
        Link("Changelog", "https://massive.com/changelog", "changelog"),
        Link("API keys", KEYS, "console"),
        Link("Python client", "https://github.com/massive-com/client-python", "sdk"),
        Link("Terms of service", "https://massive.com/terms", "terms"),
    ),
    areas=(
        Area(STOCKS, "bars of any size from a second to a year, the whole market's day, a day's open and close",
             _rest("stocks/aggregates/custom-bars"),
             covered="every stock's 1-second, minute and daily bars (split-adjusted); the whole US market's day in one "
                     "request"),
        Area(TRADES, "tick-level trades and NBBO quotes, the last trade and quote",
             _rest("stocks/trades-quotes/trades"),
             covered="a stock's trades (Developer and up); one quote, by the plan scan (Advanced)"),
        Area("Stocks: snapshots", "the whole market's or a ticker's latest minute, day and trade, top movers",
             _rest("stocks/snapshots/full-market-snapshot")),
        Area("Stocks: technical indicators", "SMA, EMA, MACD and RSI computed by Massive",
             _rest("stocks/technical-indicators/simple-moving-average")),
        Area(TICKERS, "every ticker, a ticker's overview with its branding, ticker types, related tickers",
             _rest("stocks/tickers/all-tickers"),
             covered="each exchange's listings (the directory), a ticker's record and its company icon"),
        Area(OPS, "exchanges, trade and quote condition codes, market holidays, the market's status now",
             _rest("stocks/market-operations/exchanges"),
             covered="the exchanges, the trade conditions with their update rules, upcoming holidays and early closes"),
        Area("Stocks: corporate actions", "splits, dividends, IPOs and ticker events",
             _rest("stocks/corporate-actions/splits")),
        Area("Stocks: fundamentals", "income statements, balance sheets, cash flows, ratios, float, short interest and "
             "short volume", _rest("stocks/fundamentals/income-statements")),
        Area("Stocks: filings", "10-K sections, 8-K disclosures, Forms 3 and 4, 13-F holdings, insider activity, risk "
             "factors", _rest("stocks/filings/10-k-sections")),
        Area("News", "articles by ticker with their publishers and sentiment", _rest("stocks/news"),
             covered="the headlines (massive-news), every 30 minutes: the News view and the globe's ticker"),
        Area("Options", "contracts, bars, trades and quotes, chains and snapshots, open interest", _rest("options")),
        Area("Futures", "contracts, products, schedules, bars, trades and quotes of CME, CBOT, NYMEX and COMEX",
             _rest("futures"),
             covered="a contract's 1-second, minute and session bars; the products of a day; each product's sessions "
                     "for the next 60 days"),
        Area("Indices", "index values and bars, snapshots, indicators", _rest("indices"),
             covered="index bars (I: tickers, on the aggregates endpoint)"),
        Area("Forex", "currency pairs' bars, quotes, snapshots and conversion", _rest("forex"),
             covered="currency pairs' bars (C: tickers, on the aggregates endpoint)"),
        Area("Crypto", "crypto pairs' bars, trades, snapshots and indicators", _rest("crypto"),
             covered="crypto pairs' bars (X: tickers, on the aggregates endpoint)"),
        Area("Economy", "treasury yields, inflation and its expectations, the labor market, funding conditions",
             _rest("economy")),
        Area("Alternative", "consumer spending by merchant", _rest("alternative")),
        Area("Partners", "Benzinga's ratings, earnings and news, ETF Global's analytics, TMX's corporate events",
             _rest("partners")),
        Area("WebSockets", "streams of each asset class's trades, quotes and bars as they happen (a separate API; "
             "stocks: wss://socket.massive.com/stocks, 15 minutes delayed: wss://delayed.massive.com/stocks)",
             f"{DOCS}/websocket/quickstart"),
        Area("Flat Files", "each trading day's trades, quotes and bars as gzipped CSV files over S3 (files.massive.com)",
             f"{DOCS}/flat-files/quickstart"),
    ),
    calls=(
        Call("GET /v2/aggs/ticker/{stocksTicker}/range/{multiplier}/{timespan}/{from}/{to}",
             "a ticker's bars over a range, adjusted for splits, up to 50,000 a page", STOCKS,
             used="every bar it collects: stocks, indices (I:), currencies (C:) and crypto (X:) at 1 second, 1 minute "
                  "and 1 day; the plan scan's daily bars 3, 6, 11 and 21 years back",
             docs=_rest("stocks/aggregates/custom-bars")),
        Call("GET /v2/aggs/grouped/locale/us/market/stocks/{date}", "every US stock's daily bar of one day", STOCKS,
             used="the whole market's day in one request (the daily fill)",
             docs=_rest("stocks/aggregates/daily-market-summary")),
        Call("GET /v3/trades/{stockTicker}", "a ticker's trades over a time range (Developer and up)", TRADES,
             used="a stock's trades; the plan scan's trades probe", docs=_rest("stocks/trades-quotes/trades")),
        Call("GET /v3/quotes/{stockTicker}", "a ticker's NBBO quotes over a time range (Advanced)", TRADES,
             used="the plan scan only: one quote tells Advanced", docs=_rest("stocks/trades-quotes/quotes")),
        Call("GET /v3/reference/tickers", "the tickers, filtered by market, exchange and type, paged", TICKERS,
             used="each exchange's active listings (the directory refresh)", docs=_rest("stocks/tickers/all-tickers")),
        Call("GET /v3/reference/tickers/{ticker}", "one ticker's overview: exchange, identifiers, dates, branding",
             TICKERS, used="a ticker's record: name, primary exchange, list date, FIGI, whether active",
             docs=_rest("stocks/tickers/ticker-overview")),
        Call("GET branding.icon_url", "a company's icon, at the address its ticker overview gives (on the API host)",
             TICKERS, used="the company icon beside a ticker", docs=_rest("stocks/tickers/ticker-overview")),
        Call("GET /v3/reference/exchanges", "the exchanges with their identifiers and MICs", OPS,
             used="the exchanges table (stocks)", docs=_rest("stocks/market-operations/exchanges")),
        Call("GET /v3/reference/conditions", "the trade and quote conditions with their SIP mappings and update rules",
             OPS, used="the trade conditions: which update a bar's high, low, open, close and volume",
             docs=_rest("stocks/market-operations/condition-codes")),
        Call("GET /v1/marketstatus/upcoming", "the upcoming market holidays and early closes", OPS,
             used="the sessions calendar's holidays and early closes",
             docs=_rest("stocks/market-operations/market-holidays")),
        Call("GET /v2/reference/news", "the newest articles, by ticker and publication time", "News",
             used="the headlines (massive-news): one request every 30 minutes", docs=_rest("stocks/news")),
        Call("GET /futures/v1/aggs/{ticker}", "a futures contract's bars, from a second to a session and longer",
             "Futures", used="a contract's 1-second, minute and session bars", docs=_rest("futures/aggregates")),
        Call("GET /futures/v1/schedules", "the futures products' trading sessions, breaks and holiday changes", "Futures",
             used="each futures product's sessions for the next 60 days", docs=_rest("futures/schedules")),
        Call("GET /futures/v1/products", "the futures products' specifications, as of a day", "Futures",
             used="the futures products of a day (the futures directory)", docs=_rest("futures/products")),
        Call("GET /v2/aggs/ticker/{stocksTicker}/prev", "a ticker's previous day's bar", STOCKS,
             docs=_rest("stocks/aggregates/previous-day-bar")),
        Call("GET /v1/open-close/{stocksTicker}/{date}", "a ticker's open, close and extended hours of one day", STOCKS,
             docs=_rest("stocks/aggregates/daily-ticker-summary")),
        Call("GET /v2/last/trade/{stocksTicker}", "a ticker's last trade (Developer and up)", TRADES,
             docs=_rest("stocks/trades-quotes/last-trade")),
        Call("GET /v2/snapshot/locale/us/markets/stocks/tickers", "every US stock's latest minute, day and trade",
             "Stocks: snapshots", docs=_rest("stocks/snapshots/full-market-snapshot")),
        Call("GET /v2/snapshot/locale/us/markets/stocks/tickers/{stocksTicker}", "one ticker's snapshot",
             "Stocks: snapshots", docs=_rest("stocks/snapshots/single-ticker-snapshot")),
        Call("GET /v1/indicators/sma/{stockTicker}", "a simple moving average computed by Massive (EMA, MACD, RSI alike)",
             "Stocks: technical indicators", docs=_rest("stocks/technical-indicators/simple-moving-average")),
        Call("GET /v1/marketstatus/now", "whether each market is open, closed or in extended hours now", OPS,
             docs=_rest("stocks/market-operations/market-status")),
        Call("GET /stocks/v1/splits", "split events with their ratios and adjustment factors", "Stocks: corporate actions",
             docs=_rest("stocks/corporate-actions/splits")),
        Call("GET /stocks/v1/dividends", "cash dividends with their dates and amounts", "Stocks: corporate actions",
             docs=_rest("stocks/corporate-actions/dividends")),
        Call("GET /vX/reference/ipos", "initial public offerings", "Stocks: corporate actions",
             docs=_rest("stocks/corporate-actions/ipos")),
        Call("GET /stocks/financials/v1/income-statements", "companies' income statements (Advanced, or the Financials "
             "& Ratios plan)", "Stocks: fundamentals", docs=_rest("stocks/fundamentals/income-statements")),
        Call("GET /stocks/financials/v1/ratios", "companies' key ratios (Advanced, or the Financials & Ratios plan)",
             "Stocks: fundamentals", docs=_rest("stocks/fundamentals/ratios")),
        Call("GET /stocks/v1/short-interest", "stocks' short interest", "Stocks: fundamentals",
             docs=_rest("stocks/fundamentals/short-interest")),
        Call("GET /v3/reference/options/contracts", "the options contracts", "Options",
             docs=_rest("options/contracts/all-contracts")),
        Call("GET /v3/snapshot/options/{underlyingAsset}", "a snapshot of an underlying asset's option chain", "Options",
             docs=_rest("options/snapshots/option-chain-snapshot")),
        Call("GET /futures/v1/contracts", "the futures contracts, as of a day", "Futures", docs=_rest("futures/contracts")),
        Call("GET /v1/conversion/{from}/{to}", "one currency converted to another at the latest rate", "Forex",
             docs=_rest("forex/currency-conversion")),
        Call("GET /fed/v1/treasury-yields", "US Treasury yields by maturity", "Economy",
             docs=_rest("economy/treasury-yields")),
    ),
    verified="2026-11-11",
)

APIS = (MASSIVE_REST,)  # the plugin's, its feed's and its headlines' alike (one card: the app draws it once)
