from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

USER_AGENT = "Mozilla/5.0 (compatible; RobloxFriendBot/1.0)"
GAMES_BASE = "https://games.roblox.com"
MAX_BATCH_SIZE = 50


def _http_get_json(url: str, headers: dict[str, str], timeout: int = 20, retries: int = 6) -> object:
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
    if size <= 0:
        return [items]
    return [items[i : i + size] for i in range(0, len(items), size)]


def _fetch_names(universe_ids: list[str], accept_language: str, timeout: int = 20, retries: int = 6) -> dict[str, str]:
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


def main() -> int:
    parser = argparse.ArgumentParser(description="Fill name_ru/name_en in data/games.json using Roblox localization.")
    parser.add_argument("--input", default=str(Path("data") / "games.json"))
    parser.add_argument("--output", default="")
    parser.add_argument("--batch-size", type=int, default=MAX_BATCH_SIZE)
    parser.add_argument("--sleep", type=float, default=0.2, help="Delay between requests to avoid rate limits")
    parser.add_argument("--timeout", type=int, default=20)
    parser.add_argument("--retries", type=int, default=6)
    parser.add_argument("--ru", default="ru-RU", help="Accept-Language for Russian")
    parser.add_argument("--update-en", action="store_true", help="Also refresh name_en (slower)")
    parser.add_argument("--en", default="en-US", help="Accept-Language for English (used with --update-en)")
    args = parser.parse_args()
    batch_size = max(1, min(int(args.batch_size), MAX_BATCH_SIZE))

    in_path = Path(args.input)
    out_path = Path(args.output) if str(args.output).strip() else in_path

    raw = json.loads(in_path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise SystemExit("Input JSON must be a list")

    games: list[dict] = [g for g in raw if isinstance(g, dict)]
    codes: list[str] = []
    for g in games:
        code = str(g.get("code") or "").strip()
        if not code:
            continue
        g["code"] = code
        codes.append(code)

    total = len(codes)
    if total == 0:
        raise SystemExit("No games found in input JSON")

    ru_total = 0
    en_total = 0
    by_code = {g["code"]: g for g in games if g.get("code")}

    for chunk in _chunks(codes, batch_size):
        names_ru = _fetch_names(chunk, accept_language=str(args.ru), timeout=int(args.timeout), retries=int(args.retries))
        for code, name in names_ru.items():
            game = by_code.get(code)
            if game is None:
                continue
            game["name_ru"] = name
            ru_total += 1
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
                game = by_code.get(code)
                if game is None:
                    continue
                game["name_en"] = name
                en_total += 1
            time.sleep(max(0.0, float(args.sleep)))

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(games, ensure_ascii=False, indent=2), encoding="utf-8")

    en_part = f", en={en_total}/{total}" if args.update_en else ", en=skipped"
    print(f"Updated: ru={ru_total}/{total}{en_part}. Saved to {out_path}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
