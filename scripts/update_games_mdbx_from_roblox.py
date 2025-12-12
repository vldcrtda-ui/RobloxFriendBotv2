from __future__ import annotations

import argparse
import json
import re
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from app.services.games import GamesService

USER_AGENT = "Mozilla/5.0 (compatible; RobloxFriendBot/1.0)"
GAMES_BASE = "https://games.roblox.com"
MAX_BATCH_SIZE = 50

_LATIN_WORD_RE = re.compile(r"[A-Za-z][A-Za-z0-9']*")

_WORD_MAP = {
    "tycoon": "тайкун",
    "simulator": "симулятор",
    "obby": "обби",
    "escape": "побег",
    "tower": "башня",
    "world": "мир",
    "mansion": "особняк",
    "brainrot": "брейнрот",
}

_DIGRAPHS = [
    ("sch", "щ"),
    ("sh", "ш"),
    ("ch", "ч"),
    ("zh", "ж"),
    ("kh", "х"),
    ("ts", "ц"),
    ("yu", "ю"),
    ("ya", "я"),
    ("yo", "ё"),
    ("ph", "ф"),
    ("th", "т"),
    ("qu", "кв"),
]

_CHAR_MAP = {
    "a": "а",
    "b": "б",
    "c": "к",
    "d": "д",
    "e": "е",
    "f": "ф",
    "g": "г",
    "h": "х",
    "i": "и",
    "j": "дж",
    "k": "к",
    "l": "л",
    "m": "м",
    "n": "н",
    "o": "о",
    "p": "п",
    "q": "к",
    "r": "р",
    "s": "с",
    "t": "т",
    "u": "у",
    "v": "в",
    "w": "в",
    "x": "кс",
    "y": "й",
    "z": "з",
}


def _http_get_json(url: str, headers: dict[str, str], timeout: int = 20, retries: int = 20) -> object:
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            req = Request(url, headers=headers)
            with urlopen(req, timeout=timeout) as resp:  # nosec B310 (controlled URL)
                raw = resp.read()
                return json.loads(raw.decode("utf-8"))
        except HTTPError as e:
            last_error = e
            if e.code == 429:
                wait = 2.0 + float(attempt)
                for header_name in ("retry-after", "x-ratelimit-reset", "x-ratelimit-reset-after"):
                    raw_wait = e.headers.get(header_name)
                    if not raw_wait:
                        continue
                    try:
                        parsed = float(raw_wait)
                        if parsed > 600:
                            parsed = max(0.0, parsed - time.time())
                        wait = parsed
                        break
                    except Exception:
                        continue
                time.sleep(max(1.0, wait))
                continue
            if 500 <= e.code < 600:
                time.sleep(1 + attempt)
                continue
            raise
        except (URLError, TimeoutError) as e:
            last_error = e
            time.sleep(1 + attempt)
            continue
    raise RuntimeError(f"Failed to fetch {url}: {last_error}")


def _chunks(items: list[str], size: int) -> list[list[str]]:
    return [items[i : i + size] for i in range(0, len(items), size)]


def _fetch_names(universe_ids: list[str], accept_language: str, timeout: int = 20, retries: int = 20) -> dict[str, str]:
    params = {"universeIds": ",".join(universe_ids)}
    url = f"{GAMES_BASE}/v1/games?{urlencode(params)}"
    payload = _http_get_json(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept-Language": accept_language,
        },
        timeout=timeout,
        retries=retries,
    )
    if not isinstance(payload, dict):
        return {}
    out: dict[str, str] = {}
    for item in payload.get("data") or []:
        if not isinstance(item, dict):
            continue
        uid = item.get("id")
        name = item.get("name")
        if uid is None or not name:
            continue
        out[str(uid)] = str(name)
    return out


def _preserve_case(src: str, replacement: str) -> str:
    if not src:
        return replacement
    if src.isupper():
        return replacement.upper()
    if src[0].isupper():
        return replacement[:1].upper() + replacement[1:]
    return replacement


def _translit_en_to_ru(word: str) -> str:
    w = (word or "").casefold()
    out: list[str] = []
    i = 0
    while i < len(w):
        matched = False
        for pat, rep in _DIGRAPHS:
            if w.startswith(pat, i):
                out.append(rep)
                i += len(pat)
                matched = True
                break
        if matched:
            continue
        ch = w[i]
        out.append(_CHAR_MAP.get(ch, ch))
        i += 1
    return "".join(out)


def _rusify_mixed_ru_name(text: str) -> str:
    def repl(match: re.Match[str]) -> str:
        word = match.group(0)
        mapped = _WORD_MAP.get(word.casefold())
        replacement = mapped if mapped is not None else _translit_en_to_ru(word)
        return _preserve_case(word, replacement)

    return _LATIN_WORD_RE.sub(repl, text or "")


def main() -> int:
    parser = argparse.ArgumentParser(description="Update data/games.mdbx names from Roblox API (ru/en).")
    parser.add_argument("--mdbx", default=str(Path("data") / "games.mdbx"))
    parser.add_argument("--batch-size", type=int, default=MAX_BATCH_SIZE)
    parser.add_argument("--limit", type=int, default=0, help="Update only first N games (0 = all)")
    parser.add_argument("--sleep", type=float, default=0.2)
    parser.add_argument("--timeout", type=int, default=20)
    parser.add_argument("--retries", type=int, default=20)
    parser.add_argument("--ru", default="ru-RU", help="Accept-Language for Russian")
    parser.add_argument("--update-en", action="store_true", help="Also refresh name_en (slower)")
    parser.add_argument("--en", default="en-US", help="Accept-Language for English (used with --update-en)")
    parser.add_argument(
        "--rusify-latin",
        action="store_true",
        help="Convert remaining latin words in name_ru to Cyrillic (dictionary + translit).",
    )
    args = parser.parse_args()

    batch_size = max(1, min(int(args.batch_size), MAX_BATCH_SIZE))
    svc = GamesService(str(args.mdbx))
    games = svc.list()
    if not games:
        raise SystemExit("MDBX is empty; populate games first.")

    codes = [str(g.get("code") or "") for g in games if str(g.get("code") or "")]
    by_code = {str(g.get("code") or ""): g for g in games if str(g.get("code") or "")}

    limit = max(0, int(args.limit or 0))
    if limit:
        codes = codes[:limit]
    total = len(codes)
    ru_done = 0
    en_done = 0

    for chunk in _chunks(codes, batch_size):
        names_ru = _fetch_names(chunk, accept_language=str(args.ru), timeout=int(args.timeout), retries=int(args.retries))
        for code, name in names_ru.items():
            g = by_code.get(code)
            if g is None:
                continue
            g["name_ru"] = _rusify_mixed_ru_name(name) if args.rusify_latin else name
            ru_done += 1
        time.sleep(max(0.0, float(args.sleep)))

    if args.update_en:
        for chunk in _chunks(codes, batch_size):
            names_en = _fetch_names(
                chunk,
                accept_language=str(args.en),
                timeout=int(args.timeout),
                retries=int(args.retries),
            )
            for code, name in names_en.items():
                g = by_code.get(code)
                if g is None:
                    continue
                g["name_en"] = name
                en_done += 1
            time.sleep(max(0.0, float(args.sleep)))

    svc.rebuild(games)
    print(f"Updated {svc.count()} games. name_ru={ru_done}/{total}, name_en={'skipped' if not args.update_en else f'{en_done}/{total}'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
