#!/usr/bin/env python3
"""Watch X for new AI subscription promotions and alert on new matches."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import quote_plus

import requests
from dotenv import load_dotenv

try:
    from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
    from playwright.sync_api import sync_playwright
except ImportError:  # pragma: no cover
    PlaywrightTimeoutError = Exception
    sync_playwright = None


DEFAULT_FOCUS_TERMS = [
    "Claude Code",
    "Claude Pro",
    "Claude Plus",
    "Codex",
    "ChatGPT Pro",
    "ChatGPT Plus",
    "GPT-5",
    "GPT-4o",
    "OpenAI o3",
    "GLM-5",
    "Kimi K1",
    "Kimi Explorer",
    "Hermes Agent",
    "OpenClaw",
    "Qwen Max",
    "Qwen Plus",
    "Midjourney",
    "Copilot Pro",
]

DEFAULT_PROMO_TERMS = [
    "promo code",
    "promo link",
    "promotion code",
    "discount code",
    "discount link",
    "coupon code",
    "deal on",
    "deal for",
    "limited time offer",
    "% off",
    "special offer",
    "annual plan",
    "annual subscription",
    "monthly plan",
    "monthly subscription",
    "extended trial",
    "free trial",
    "early access",
    "early bird",
    "beta invite",
    "beta access",
    "beta testing invite",
    "join the waitlist",
    "join waitlist",
    "subscribe now",
    "subscribe today",
    "upgrade to",
    "plan starting at",
    "starting at $",
    "price drop",
]

DEFAULT_ENDPOINTS = [
    "https://api.x.com/2/tweets/search/recent",
    "https://api.twitter.com/2/tweets/search/recent",
]


class BotError(Exception):
    """Base error class for the bot."""


class RateLimitError(BotError):
    """Raised when X API rate limit is hit."""

    def __init__(self, message: str, wait_seconds: int = 0) -> None:
        super().__init__(message)
        self.wait_seconds = max(0, wait_seconds)


def configure_console_encoding() -> None:
    """Prevent Windows console encode crashes for unicode tweet text."""
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if stream is None:
            continue
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass


@dataclass
class Config:
    auth_mode: str
    x_bearer_token: str
    cookie_file: Path
    state_file: Path
    output_file: Path
    interval_minutes: int
    max_results: int
    language: str
    focus_terms: List[str]
    promo_terms: List[str]
    extra_query: str
    telegram_bot_token: str
    telegram_chat_id: str
    dry_run: bool
    headless: bool
    search_scrolls: int
    search_wait_ms: int
    browser_engine: str
    cloak_humanize: bool
    exclude_terms: List[str]
    blocklist_usernames: List[str]


def parse_csv_env(name: str, fallback: List[str]) -> List[str]:
    raw = os.getenv(name, "")
    if not raw.strip():
        return fallback
    parts = [item.strip() for item in raw.split(",")]
    return [item for item in parts if item]


def quote_term(term: str) -> str:
    t = term.strip().replace('"', '\\"')
    if not t:
        return t
    if any(ch.isspace() for ch in t):
        return f'"{t}"'
    return t


def build_query(focus_terms: List[str], promo_terms: List[str], language: str, extra_query: str) -> str:
    focus_block = "(" + " OR ".join(quote_term(term) for term in focus_terms) + ")"
    promo_block = "(" + " OR ".join(quote_term(term) for term in promo_terms) + ")"
    query = f"{focus_block} {promo_block} -is:retweet"
    if language:
        query += f" lang:{language}"
    if extra_query.strip():
        query += f" {extra_query.strip()}"
    return query


def parse_bool(raw: str, default: bool = False) -> bool:
    text = raw.strip().lower()
    if not text:
        return default
    if text in ("1", "true", "yes", "y", "on"):
        return True
    if text in ("0", "false", "no", "n", "off"):
        return False
    return default


def truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        return parse_bool(value, default=False)
    return False


def normalize_samesite(value: Any) -> Optional[str]:
    raw = str(value or "").strip().lower()
    mapping = {"lax": "Lax", "strict": "Strict", "none": "None"}
    return mapping.get(raw)


def normalize_cookie(cookie: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if not isinstance(cookie, dict):
        return None

    name = str(cookie.get("name", "")).strip()
    if not name:
        return None
    value = str(cookie.get("value", ""))
    path = str(cookie.get("path", "/")).strip() or "/"
    domain = str(cookie.get("domain", "")).strip()
    url = str(cookie.get("url", "")).strip()

    normalized: Dict[str, Any] = {"name": name, "value": value, "path": path}
    if domain:
        normalized["domain"] = domain
    elif url:
        normalized["url"] = url
    else:
        normalized["domain"] = ".x.com"

    expires_raw = cookie.get("expires", cookie.get("expirationDate"))
    if expires_raw not in (None, ""):
        try:
            expires_num = int(float(expires_raw))
            if expires_num > 0:
                normalized["expires"] = expires_num
        except (TypeError, ValueError):
            pass

    normalized["secure"] = truthy(cookie.get("secure", False))
    if "httpOnly" in cookie:
        normalized["httpOnly"] = truthy(cookie.get("httpOnly", False))

    same_site = normalize_samesite(cookie.get("sameSite"))
    if same_site:
        normalized["sameSite"] = same_site

    return normalized


def parse_netscape_cookie_file(path: Path) -> List[Dict[str, Any]]:
    cookies: List[Dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        text = line.strip()
        if not text or text.startswith("#"):
            continue

        parts = text.split("\t")
        if len(parts) < 7:
            parts = re.split(r"\s+", text)
        if len(parts) < 7:
            continue

        domain, _, cpath, secure_flag, expires_raw, name, value = parts[:7]
        cookie: Dict[str, Any] = {
            "name": name,
            "value": value,
            "domain": domain,
            "path": cpath or "/",
            "secure": str(secure_flag).upper() == "TRUE",
        }
        if str(expires_raw).isdigit() and int(expires_raw) > 0:
            cookie["expires"] = int(expires_raw)

        normalized = normalize_cookie(cookie)
        if normalized:
            cookies.append(normalized)
    return cookies


def load_cookie_file(cookie_file: Path) -> Tuple[Optional[Dict[str, Any]], List[Dict[str, Any]], str]:
    if not cookie_file.exists():
        raise BotError(
            f"COOKIE_FILE not found: {cookie_file}. Export your X session cookie/storage file first."
        )

    raw = cookie_file.read_text(encoding="utf-8", errors="ignore")
    parsed_json: Optional[Any] = None
    try:
        parsed_json = json.loads(raw)
    except json.JSONDecodeError:
        parsed_json = None

    if isinstance(parsed_json, dict):
        cookies_raw = parsed_json.get("cookies")
        if isinstance(cookies_raw, list):
            normalized = [normalize_cookie(c) for c in cookies_raw]
            cookies = [c for c in normalized if c]
            storage_state = {"cookies": cookies, "origins": parsed_json.get("origins", [])}
            return storage_state, [], "storage_state_json"
        raise BotError("COOKIE_FILE JSON must include a 'cookies' array.")

    if isinstance(parsed_json, list):
        normalized = [normalize_cookie(c) for c in parsed_json if isinstance(c, dict)]
        cookies = [c for c in normalized if c]
        if not cookies:
            raise BotError("COOKIE_FILE JSON array contains no valid cookies.")
        return None, cookies, "cookies_json_array"

    cookies = parse_netscape_cookie_file(cookie_file)
    if cookies:
        return None, cookies, "netscape_cookie_txt"

    raise BotError(
        "COOKIE_FILE format not recognized. Use Playwright storage state JSON, "
        "cookies JSON array, or Netscape cookies.txt."
    )


def resolve_auth_mode(cli_mode: str, token: str, cookie_file_raw: str) -> str:
    mode = (cli_mode or os.getenv("AUTH_MODE", "auto")).strip().lower()
    if mode not in ("auto", "api", "cookies"):
        raise BotError("AUTH_MODE must be one of: auto, api, cookies.")

    if mode == "auto":
        if token:
            return "api"
        if cookie_file_raw:
            return "cookies"
        raise BotError("Set X_BEARER_TOKEN (API mode) or COOKIE_FILE (cookie mode).")
    return mode


def load_config(args: argparse.Namespace) -> Config:
    load_dotenv(dotenv_path=Path(__file__).resolve().parent / ".env", override=True)

    token = os.getenv("X_BEARER_TOKEN", "").strip()
    cookie_file_raw = os.getenv("COOKIE_FILE", "").strip()
    auth_mode = resolve_auth_mode(args.auth_mode, token, cookie_file_raw)
    if auth_mode == "api" and not token:
        raise BotError("Missing X_BEARER_TOKEN for API mode.")
    if auth_mode == "cookies" and not cookie_file_raw:
        raise BotError("Missing COOKIE_FILE for cookies mode.")

    interval = args.interval_minutes if args.interval_minutes else int(os.getenv("RUN_EVERY_MINUTES", "60"))
    max_results = int(os.getenv("MAX_RESULTS", "50"))
    if max_results < 1 or max_results > 100:
        raise BotError("MAX_RESULTS must be between 1 and 100.")

    if auth_mode == "api" and max_results < 10:
        raise BotError("In API mode, MAX_RESULTS must be between 10 and 100.")

    browser_engine = (args.browser_engine or os.getenv("BROWSER_ENGINE", "playwright")).strip().lower()
    if browser_engine not in ("playwright", "cloak"):
        raise BotError("BROWSER_ENGINE must be one of: playwright, cloak.")

    return Config(
        auth_mode=auth_mode,
        x_bearer_token=token,
        cookie_file=Path(cookie_file_raw).resolve() if cookie_file_raw else Path("x_storage_state.json").resolve(),
        state_file=Path(os.getenv("STATE_FILE", "state.json")).resolve(),
        output_file=Path(os.getenv("OUTPUT_FILE", "alerts.jsonl")).resolve(),
        interval_minutes=max(1, interval),
        max_results=max_results,
        language=os.getenv("LANGUAGE_FILTER", "en").strip(),
        focus_terms=parse_csv_env("FOCUS_TERMS", DEFAULT_FOCUS_TERMS),
        promo_terms=parse_csv_env("PROMO_TERMS", DEFAULT_PROMO_TERMS),
        extra_query=os.getenv("EXTRA_QUERY", ""),
        exclude_terms=parse_csv_env("EXCLUDE_TERMS", DEFAULT_EXCLUDE_TERMS),
        blocklist_usernames=parse_csv_env("BLOCKLIST_USERNAMES", BLOCKLIST_USERNAMES),
        telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN", "").strip(),
        telegram_chat_id=os.getenv("TELEGRAM_CHAT_ID", "").strip(),
        dry_run=args.dry_run,
        headless=parse_bool(os.getenv("HEADLESS", "true"), default=True),
        search_scrolls=max(1, int(os.getenv("SEARCH_SCROLLS", "3"))),
        search_wait_ms=max(500, int(os.getenv("SEARCH_WAIT_MS", "1800"))),
        browser_engine=browser_engine,
        cloak_humanize=parse_bool(os.getenv("CLOAK_HUMANIZE", "true"), default=True),
    )


def load_state(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {"since_id": None, "seen_ids": []}
    try:
        with path.open("r", encoding="utf-8") as f:
            state = json.load(f)
    except (OSError, json.JSONDecodeError):
        return {"since_id": None, "seen_ids": []}

    state.setdefault("since_id", None)
    state.setdefault("seen_ids", [])
    if not isinstance(state.get("seen_ids"), list):
        state["seen_ids"] = []
    return state


def save_state(path: Path, state: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    state["updated_at"] = datetime.now(timezone.utc).isoformat()
    with path.open("w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)


def username_map(payload: Dict[str, Any]) -> Dict[str, str]:
    users = payload.get("includes", {}).get("users", [])
    mapping: Dict[str, str] = {}
    for user in users:
        uid = str(user.get("id", ""))
        uname = str(user.get("username", ""))
        if uid and uname:
            mapping[uid] = uname
    return mapping


def parse_rate_limit_wait(response: requests.Response) -> int:
    retry_after = response.headers.get("retry-after")
    if retry_after and retry_after.isdigit():
        return max(0, int(retry_after))

    reset = response.headers.get("x-rate-limit-reset")
    if reset and reset.isdigit():
        return max(0, int(reset) - int(time.time()))
    return 0


def fetch_recent_posts_api(token: str, query: str, since_id: Optional[str], max_results: int) -> Tuple[Dict[str, Any], str]:
    params: Dict[str, str] = {
        "query": query,
        "max_results": str(max_results),
        "tweet.fields": "created_at,author_id,lang,entities",
        "expansions": "author_id",
        "user.fields": "username",
    }
    if since_id:
        params["since_id"] = since_id

    headers = {"Authorization": f"Bearer {token}"}
    last_error: Optional[str] = None

    for endpoint in DEFAULT_ENDPOINTS:
        try:
            response = requests.get(endpoint, headers=headers, params=params, timeout=30)
        except requests.RequestException as exc:
            last_error = f"{endpoint}: request failed ({exc})"
            continue

        if response.status_code == 200:
            return response.json(), endpoint

        if response.status_code == 429:
            wait_seconds = parse_rate_limit_wait(response)
            raise RateLimitError(
                f"Rate limited by X API at {endpoint}. status=429, wait={wait_seconds}s",
                wait_seconds=wait_seconds,
            )

        if response.status_code in (401, 403):
            raise BotError(
                "X API authentication/plan issue. "
                f"status={response.status_code}, response={response.text[:600]}"
            )

        last_error = f"{endpoint}: status={response.status_code}, body={response.text[:300]}"

    raise BotError(last_error or "Unable to fetch data from X API endpoints.")


def launch_cookie_browser(config: Config) -> Tuple[Any, Any, str]:
    if config.browser_engine == "playwright":
        if sync_playwright is None:
            raise BotError(
                "Playwright is not installed. Run: pip install playwright and python -m playwright install chromium"
            )
        pw = sync_playwright().start()
        browser = pw.chromium.launch(headless=config.headless)
        return browser, pw, "playwright"

    if config.browser_engine == "cloak":
        try:
            from cloakbrowser import launch as cloak_launch
        except ImportError as exc:
            raise BotError(
                "CloakBrowser engine selected but package is missing. Run: pip install cloakbrowser"
            ) from exc

        try:
            browser = cloak_launch(headless=config.headless, humanize=config.cloak_humanize)
        except Exception as exc:
            raise BotError(f"CloakBrowser failed to launch: {exc}") from exc
        return browser, None, "cloakbrowser"

    raise BotError(f"Unsupported browser engine: {config.browser_engine}")


def fetch_recent_posts_cookies(config: Config, query: str) -> Tuple[List[Dict[str, Any]], str]:
    storage_state, cookies, file_type = load_cookie_file(config.cookie_file)
    search_url = f"https://x.com/search?q={quote_plus(query)}&f=live"
    browser, pw, engine_used = launch_cookie_browser(config)
    context = None
    try:
        if storage_state:
            context = browser.new_context(storage_state=storage_state)
        else:
            context = browser.new_context()

        page = context.new_page()
        if cookies:
            context.add_cookies(cookies)

        page.goto(search_url, wait_until="domcontentloaded", timeout=60000)
        if "/i/flow/login" in page.url:
            raise BotError(
                "Cookie session is not logged in to X anymore. Re-export cookie/storage state and retry."
            )

        try:
            page.wait_for_selector("article", timeout=25000)
        except PlaywrightTimeoutError:
            # Continue anyway; page may have loaded but no matching tweets.
            pass

        for _ in range(config.search_scrolls):
            page.mouse.wheel(0, 2600)
            page.wait_for_timeout(config.search_wait_ms)

        rows = page.evaluate(
            """() => {
            const items = [];
            const seen = new Set();
            const articles = Array.from(document.querySelectorAll('article'));
            for (const article of articles) {
              const anchor = article.querySelector('a[href*="/status/"]');
              if (!anchor) continue;
              const href = anchor.getAttribute('href') || '';
              const match = href.match(/\\/([^/]+)\\/status\\/(\\d+)/);
              if (!match) continue;
              const username = match[1] || '';
              const id = match[2] || '';
              if (!id || seen.has(id)) continue;
              seen.add(id);

              const timeEl = article.querySelector('time');
              const createdAt = timeEl ? timeEl.getAttribute('datetime') : null;
              const textNodes = Array.from(article.querySelectorAll('[data-testid="tweetText"] span'))
                .map((el) => el.textContent || '');
              let text = textNodes.join(' ').trim();
              if (!text) {
                text = (article.innerText || '').trim();
              }

              const links = Array.from(article.querySelectorAll('a[href]'))
                .map((el) => el.getAttribute('href') || '')
                .filter((x) => x.startsWith('http://') || x.startsWith('https://') || x.startsWith('/'))
                .map((x) => x.startsWith('/') ? `https://x.com${x}` : x);

              items.push({
                id,
                created_at: createdAt,
                username,
                text,
                url: `https://x.com/${username}/status/${id}`,
                links: Array.from(new Set(links)).slice(0, 8),
              });
            }
            return items;
            }"""
        )
        if not isinstance(rows, list):
            rows = []

        alerts: List[Dict[str, Any]] = []
        for row in rows[: config.max_results]:
            text = str(row.get("text", ""))
            alerts.append(
                {
                    "id": str(row.get("id", "")),
                    "created_at": row.get("created_at"),
                    "author_id": "",
                    "username": str(row.get("username", "")),
                    "text": text,
                    "url": str(row.get("url", "")),
                    "links": list(row.get("links", [])) if isinstance(row.get("links"), list) else [],
                    "matched_focus_terms": find_matches(text, config.focus_terms),
                    "matched_promo_terms": find_matches(text, config.promo_terms),
                }
            )
        alerts = [a for a in alerts if a.get("id")]

        # Persist refreshed cookies/local storage for next run.
        context.storage_state(path=str(config.cookie_file))

        return alerts, f"x.com search ({file_type}, engine={engine_used})"
    finally:
        if context is not None:
            context.close()
        browser.close()
        if pw is not None:
            pw.stop()


DEFAULT_EXCLUDE_TERMS = [
    "layoff",
    "severance",
    "shareholder",
    "earnings call",
    "fda approved",
    "fda clearance",
    "ipo",
    "going public",
    "gcse",
    "sag-aftra",
]

BLOCKLIST_USERNAMES = [
    # Known news-bot / aggregator patterns (case-insensitive prefixes).
    "news",
    "breaking",
    "daily",
    "alerts",
    "digest",
    "watch",
    "tracker",
    "updates",
    "wire",
    "press",
    "reuters",
    "apnews",
]


def find_matches(text: str, terms: List[str]) -> List[str]:
    lowered = text.lower()
    hits = [term for term in terms if term.lower() in lowered]
    return hits[:6]


def passes_quality_filter(
    matched_focus: List[str],
    matched_promo: List[str],
    text: str,
    username: str,
    exclude_terms: Optional[List[str]] = None,
    blocklist_usernames: Optional[List[str]] = None,
) -> Tuple[bool, str]:
    """Gate that decides whether an alert is worth surfacing.

    Returns (passes, reason) where reason explains why it was kept or dropped.
    """
    if exclude_terms is None:
        exclude_terms = DEFAULT_EXCLUDE_TERMS
    if blocklist_usernames is None:
        blocklist_usernames = BLOCKLIST_USERNAMES

    # 1) Must have at least one promo term match.
    if not matched_promo:
        return False, "no_promo_match"

    # 2) Exclude noisy domains.
    lowered = text.lower()
    for t in exclude_terms:
        if t.lower() in lowered:
            return False, f"excluded_term:{t}"

    # 3) Exclude bot-like accounts.
    uname_lower = username.lower()
    for block in blocklist_usernames:
        if uname_lower.startswith(block.lower()):
            return False, f"blocklisted_username:{block}"

    return True, "passes"


def extract_urls(tweet: Dict[str, Any]) -> List[str]:
    entities = tweet.get("entities", {})
    urls = entities.get("urls", [])
    extracted: List[str] = []
    for url_item in urls:
        expanded = url_item.get("expanded_url") or url_item.get("url")
        if expanded:
            extracted.append(str(expanded))
    return extracted


def to_alert_records(payload: Dict[str, Any], focus_terms: List[str], promo_terms: List[str]) -> List[Dict[str, Any]]:
    users = username_map(payload)
    tweets = payload.get("data", [])
    alerts: List[Dict[str, Any]] = []
    for tweet in tweets:
        tweet_id = str(tweet.get("id", ""))
        author_id = str(tweet.get("author_id", ""))
        username = users.get(author_id, "")
        url = f"https://x.com/{username}/status/{tweet_id}" if username else f"https://x.com/i/web/status/{tweet_id}"
        text = str(tweet.get("text", ""))
        alerts.append(
            {
                "id": tweet_id,
                "created_at": tweet.get("created_at"),
                "author_id": author_id,
                "username": username,
                "text": text,
                "url": url,
                "links": extract_urls(tweet),
                "matched_focus_terms": find_matches(text, focus_terms),
                "matched_promo_terms": find_matches(text, promo_terms),
            }
        )
    return alerts


def id_sort_key(value: str) -> Tuple[int, Any]:
    if value.isdigit():
        return (0, int(value))
    return (1, value)


def dedupe_and_update_state(
    alerts: List[Dict[str, Any]],
    state: Dict[str, Any],
    newest_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    seen = set(str(sid) for sid in state.get("seen_ids", []))
    fresh: List[Dict[str, Any]] = []
    for alert in alerts:
        alert_id = str(alert["id"])
        if alert_id not in seen:
            fresh.append(alert)
            seen.add(alert_id)

    if newest_id:
        state["since_id"] = str(newest_id)
    elif alerts:
        ids = [str(a["id"]) for a in alerts]
        state["since_id"] = sorted(ids, key=id_sort_key)[-1]

    # Keep a bounded memory of recent IDs.
    state["seen_ids"] = sorted(seen, key=id_sort_key)[-5000:]
    return fresh


def print_alert(alert: Dict[str, Any]) -> None:
    created = alert.get("created_at") or "n/a"
    username = alert.get("username") or "unknown"
    text = " ".join(str(alert.get("text", "")).split())
    if len(text) > 220:
        text = text[:217] + "..."
    focus = ", ".join(alert.get("matched_focus_terms", [])) or "n/a"
    promo = ", ".join(alert.get("matched_promo_terms", [])) or "n/a"

    print(f"[NEW] {created}  @{username}")
    print(f"      {alert['url']}")
    print(f"      focus={focus} | promo={promo}")
    print(f"      {text}")
    if alert.get("links"):
        print(f"      links: {' | '.join(alert['links'][:3])}")


def append_alerts(path: Path, alerts: List[Dict[str, Any]]) -> None:
    if not alerts:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        for alert in alerts:
            f.write(json.dumps(alert, ensure_ascii=False) + "\n")


def send_telegram_alert(bot_token: str, chat_id: str, alert: Dict[str, Any]) -> None:
    if not bot_token or not chat_id:
        return

    text = str(alert.get("text", "")).strip()
    if len(text) > 1500:
        text = text[:1497] + "..."
    username = alert.get("username") or "unknown"
    message = (
        f"New AI promo mention on X\n"
        f"@{username}\n"
        f"{alert['url']}\n\n"
        f"{text}"
    )
    api_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {"chat_id": chat_id, "text": message, "disable_web_page_preview": False}
    try:
        requests.post(api_url, json=payload, timeout=15)
    except requests.RequestException:
        # Keep the bot alive even if Telegram fails.
        return


def run_once(config: Config) -> int:
    state = load_state(config.state_file)
    query = build_query(config.focus_terms, config.promo_terms, config.language, config.extra_query)
    if config.auth_mode == "api":
        payload, used_endpoint = fetch_recent_posts_api(
            token=config.x_bearer_token,
            query=query,
            since_id=state.get("since_id"),
            max_results=config.max_results,
        )
        all_alerts = to_alert_records(payload, config.focus_terms, config.promo_terms)
        fresh_alerts = dedupe_and_update_state(
            alerts=all_alerts,
            state=state,
            newest_id=str(payload.get("meta", {}).get("newest_id") or ""),
        )
    else:
        all_alerts, used_endpoint = fetch_recent_posts_cookies(config, query)
        fresh_alerts = dedupe_and_update_state(alerts=all_alerts, state=state, newest_id=None)
    save_state(config.state_file, state)

    # Quality filter: only surface alerts that pass the content gate.
    quality_alerts: List[Dict[str, Any]] = []
    dropped_counts: Dict[str, int] = {}
    exclude_terms = config.exclude_terms if config.exclude_terms else DEFAULT_EXCLUDE_TERMS
    for alert in fresh_alerts:
        text = str(alert.get("text", ""))
        username = str(alert.get("username", ""))
        mf = alert.get("matched_focus_terms", [])
        mp = alert.get("matched_promo_terms", [])
        ok, reason = passes_quality_filter(
            mf, mp, text, username, exclude_terms, config.blocklist_usernames
        )
        if ok:
            quality_alerts.append(alert)
        else:
            dropped_counts[reason] = dropped_counts.get(reason, 0) + 1

    now = datetime.now(timezone.utc).isoformat()
    print(f"\n[{now}] Mode={config.auth_mode} Source={used_endpoint}")
    print(f"Query: {query}")
    print(f"Matches this run: total={len(all_alerts)} fresh={len(fresh_alerts)} quality={len(quality_alerts)}")
    if dropped_counts:
        print(f"Dropped: {dict(dropped_counts)}")

    for alert in quality_alerts:
        print_alert(alert)

    if not config.dry_run:
        append_alerts(config.output_file, quality_alerts)
        for alert in quality_alerts:
            send_telegram_alert(config.telegram_bot_token, config.telegram_chat_id, alert)

    return len(quality_alerts)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Watch X every hour for AI subscription promotion posts."
    )
    parser.add_argument("--once", action="store_true", help="Run a single check and exit.")
    parser.add_argument(
        "--interval-minutes",
        type=int,
        default=0,
        help="Polling interval in minutes for continuous mode. Default from RUN_EVERY_MINUTES or 60.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Do not write alerts file and do not send Telegram notifications.",
    )
    parser.add_argument(
        "--auth-mode",
        choices=["auto", "api", "cookies"],
        default="auto",
        help="Auth mode: API bearer token or cookie file browser mode.",
    )
    parser.add_argument(
        "--browser-engine",
        choices=["playwright", "cloak"],
        default="",
        help="Browser engine for cookie mode. Default from BROWSER_ENGINE env.",
    )
    return parser.parse_args()


def main() -> int:
    configure_console_encoding()
    args = parse_args()
    try:
        config = load_config(args)
    except BotError as exc:
        print(f"[CONFIG ERROR] {exc}", file=sys.stderr)
        return 2

    if args.once:
        try:
            run_once(config)
            return 0
        except RateLimitError as exc:
            print(f"[RATE LIMIT] {exc}", file=sys.stderr)
            return 3
        except BotError as exc:
            print(f"[BOT ERROR] {exc}", file=sys.stderr)
            return 1
        except Exception as exc:  # pragma: no cover
            print(f"[UNEXPECTED] {exc}", file=sys.stderr)
            return 1

    print(
        "Starting continuous watch mode. "
        f"Interval={config.interval_minutes} minutes, state={config.state_file}, output={config.output_file}"
    )
    while True:
        loop_start = time.time()
        try:
            run_once(config)
        except RateLimitError as exc:
            wait_for = exc.wait_seconds if exc.wait_seconds > 0 else config.interval_minutes * 60
            print(f"[RATE LIMIT] {exc}. Sleeping {wait_for} seconds.")
            time.sleep(wait_for)
            continue
        except BotError as exc:
            print(f"[BOT ERROR] {exc}")
        except Exception as exc:  # pragma: no cover
            print(f"[UNEXPECTED] {exc}")

        elapsed = int(time.time() - loop_start)
        sleep_for = max(10, config.interval_minutes * 60 - elapsed)
        print(f"Sleeping {sleep_for} seconds...\n")
        time.sleep(sleep_for)


if __name__ == "__main__":
    raise SystemExit(main())
