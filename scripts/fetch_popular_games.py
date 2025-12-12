from __future__ import annotations

import argparse
import json
import time
import uuid
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

USER_AGENT = "Mozilla/5.0 (compatible; RobloxFriendBot/1.0)"
BASE = "https://apis.roblox.com"


def _http_get_json(path: str, params: dict[str, str], timeout: int = 20, retries: int = 6) -> object:
    url = f"{BASE}/{path.lstrip('/')}?{urlencode(params)}"
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            req = Request(url, headers={"User-Agent": USER_AGENT})
            with urlopen(req, timeout=timeout) as resp:  # nosec B310 (controlled URL)
                raw = resp.read()
                return json.loads(raw.decode("utf-8"))
        except HTTPError as e:
            last_error = e
            if e.code == 429:
                wait = 2 + attempt
                try:
                    wait = int(e.headers.get("x-ratelimit-reset") or wait)
                except Exception:
                    pass
                time.sleep(wait)
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


def _slp_queries(session_id: str) -> list[str]:
    payload = _http_get_json("search-api/search-landing-page", {"sessionId": session_id})
    if not isinstance(payload, dict):
        return []
    queries: list[str] = []
    for sort in payload.get("sorts") or []:
        if not isinstance(sort, dict):
            continue
        for q in sort.get("queries") or []:
            if isinstance(q, dict) and isinstance(q.get("query"), str) and q["query"].strip():
                queries.append(q["query"].strip())
    # Dedup while preserving order
    seen: set[str] = set()
    out: list[str] = []
    for q in queries:
        key = q.casefold()
        if key in seen:
            continue
        seen.add(key)
        out.append(q)
    return out


def _omni_search(session_id: str, query: str, page_token: str | None = None) -> tuple[list[dict], str]:
    params: dict[str, str] = {"sessionId": session_id, "searchQuery": query}
    if page_token:
        params["pageToken"] = page_token
    payload = _http_get_json("search-api/omni-search", params)
    if not isinstance(payload, dict):
        return [], ""
    next_token = str(payload.get("nextPageToken") or "")
    results = payload.get("searchResults") or []
    games: list[dict] = []
    for group in results:
        if not isinstance(group, dict):
            continue
        for item in group.get("contents") or []:
            if isinstance(item, dict) and isinstance(item.get("universeId"), int) and item.get("name"):
                games.append(item)
    return games, next_token


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch popular Roblox experiences into data/games.json")
    parser.add_argument("--count", type=int, default=10_000)
    parser.add_argument(
        "--pool-mult",
        type=int,
        default=2,
        help="Collect at least count*pool-mult uniques, then take top count by playerCount.",
    )
    parser.add_argument(
        "--queries",
        default="",
        help="Comma-separated seed queries (default: use Roblox search landing page + common letters).",
    )
    parser.add_argument("--output", default=str(Path("data") / "games.json"))
    parser.add_argument("--sleep", type=float, default=0.3, help="Delay between requests to avoid rate limits")
    args = parser.parse_args()

    session_id = str(uuid.uuid4())
    seeds: list[str] = []
    if args.queries.strip():
        seeds.extend([q.strip() for q in str(args.queries).split(",") if q.strip()])
    else:
        seeds.extend(_slp_queries(session_id))
        seeds.extend(["a", "e", "o", "i", "u", "y", "r", "s", "t", "n", "l"])

    # Dedup while preserving order
    seen: set[str] = set()
    queries: list[str] = []
    for q in seeds:
        key = q.casefold()
        if key in seen:
            continue
        seen.add(key)
        queries.append(q)

    games_by_universe: dict[int, dict] = {}
    total_requests = 0
    target_pool = max(int(args.count), int(args.count) * max(1, int(args.pool_mult)))

    for q in queries:
        page_token: str | None = None
        while True:
            games, next_token = _omni_search(session_id, q, page_token=page_token)
            total_requests += 1
            for g in games:
                uid = g.get("universeId")
                name = g.get("name") or ""
                if not isinstance(uid, int) or not name:
                    continue
                player_count = int(g.get("playerCount") or 0)
                existing = games_by_universe.get(uid)
                if not existing or player_count > int(existing.get("playerCount") or 0):
                    games_by_universe[uid] = {
                        "code": str(uid),
                        "name_ru": str(name),
                        "name_en": str(name),
                        "playerCount": player_count,
                        "totalUpVotes": int(g.get("totalUpVotes") or 0),
                        "totalDownVotes": int(g.get("totalDownVotes") or 0),
                        "rootPlaceId": int(g.get("rootPlaceId") or 0),
                        "creatorName": str(g.get("creatorName") or ""),
                    }

            if len(games_by_universe) >= target_pool:
                break
            if not next_token:
                break
            page_token = next_token
            time.sleep(max(0.0, float(args.sleep)))
        if len(games_by_universe) >= target_pool:
            break

    games = list(games_by_universe.values())
    games.sort(key=lambda x: (int(x.get("playerCount") or 0), int(x.get("totalUpVotes") or 0)), reverse=True)
    games = games[: int(args.count)]

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(games, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Saved {len(games)} games to {out_path} (requests={total_requests}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
