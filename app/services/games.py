from __future__ import annotations

import json
import re
from difflib import SequenceMatcher
from pathlib import Path

try:
    from mdbx import Cursor, Env, MDBXCursorOp, MDBXDBFlags, MDBXEnvFlags
    from mdbx.mdbx import MDBXPutFlags

    _HAS_MDBX = True
except Exception:  # pragma: no cover
    Cursor = Env = None  # type: ignore[assignment]
    MDBXCursorOp = MDBXDBFlags = MDBXEnvFlags = MDBXPutFlags = None  # type: ignore[assignment]
    _HAS_MDBX = False

_SPACE_RE = re.compile(r"\s+")

_EN_TO_RU = str.maketrans(
    "qwertyuiop[]asdfghjkl;'zxcvbnm,.",
    "йцукенгшщзхъфывапролджэячсмитьбю",
)
_RU_TO_EN = str.maketrans(
    "йцукенгшщзхъфывапролджэячсмитьбю",
    "qwertyuiop[]asdfghjkl;'zxcvbnm,.",
)
_RU_TO_LAT = {
    "а": "a",
    "б": "b",
    "в": "v",
    "г": "g",
    "д": "d",
    "е": "e",
    "ё": "yo",
    "ж": "zh",
    "з": "z",
    "и": "i",
    "й": "y",
    "к": "k",
    "л": "l",
    "м": "m",
    "н": "n",
    "о": "o",
    "п": "p",
    "р": "r",
    "с": "s",
    "т": "t",
    "у": "u",
    "ф": "f",
    "х": "h",
    "ц": "ts",
    "ч": "ch",
    "ш": "sh",
    "щ": "sch",
    "ъ": "",
    "ы": "y",
    "ь": "",
    "э": "e",
    "ю": "yu",
    "я": "ya",
}

MDBX_SCHEMA_VERSION = 2
MDBX_MAP_META = b"meta"
MDBX_MAP_GAMES = b"games"
MDBX_MAP_ORDER = b"order"  # rank(u32be) -> code(bytes)
MDBX_MAP_RANK = b"rank"  # code(bytes) -> rank(u32be)
MDBX_MAP_TOKEN = b"token"  # token(bytes) -> dupsort(rank(u32be)+code(bytes))


def _norm(text: str) -> str:
    text = (text or "").casefold().replace("_", " ").replace("-", " ")
    buf = [" " if not ch.isalnum() else ch for ch in text]
    return _SPACE_RE.sub(" ", "".join(buf)).strip()


def _translit_ru_to_lat(text: str) -> str:
    text = (text or "").casefold()
    return "".join(_RU_TO_LAT.get(ch, ch) for ch in text)


def _query_variants(query: str | None) -> list[str]:
    raw = (query or "").strip()
    if not raw:
        return []

    variants = [
        raw,
        raw.translate(_RU_TO_EN),
        raw.translate(_EN_TO_RU),
        _translit_ru_to_lat(raw),
        _translit_ru_to_lat(raw.translate(_RU_TO_EN)),
    ]
    out: list[str] = []
    for v in variants:
        nv = _norm(v)
        if nv and nv not in out:
            out.append(nv)
    return out


def _game_match_score(game: dict, query_variants: list[str]) -> float:
    code = str(game.get("code") or "")
    name_ru = str(game.get("name_ru") or "")
    name_en = str(game.get("name_en") or "")

    hay = _norm(f"{code} {name_ru} {name_en}")
    hay_lat = _norm(_translit_ru_to_lat(hay))

    targets = [
        _norm(code),
        _norm(name_ru),
        _norm(name_en),
        _norm(_translit_ru_to_lat(name_ru)),
        _norm(_translit_ru_to_lat(name_en)),
    ]

    best = 0.0
    for q in query_variants:
        if not q:
            continue
        tokens = q.split()
        if tokens:
            if all(t in hay or t in hay_lat for t in tokens):
                best = max(best, 1.0)
                continue
            matched = sum(1 for t in tokens if t in hay or t in hay_lat)
            if matched:
                best = max(best, (matched / len(tokens)) * 0.7)

        ratio = 0.0
        for target in targets:
            if not target:
                continue
            ratio = max(ratio, SequenceMatcher(None, q, target).ratio())
        best = max(best, ratio)

    return best


def _u32be(value: int) -> bytes:
    return int(value).to_bytes(4, byteorder="big", signed=False)


def _u32be_to_int(value: bytes | None) -> int | None:
    if not value or len(value) != 4:
        return None
    return int.from_bytes(value, byteorder="big", signed=False)


def _ensure_game_fields(game: dict) -> dict:
    out = dict(game)
    code = str(out.get("code") or "")
    out["code"] = code
    out["name_ru"] = str(out.get("name_ru") or out.get("name_en") or code)
    out["name_en"] = str(out.get("name_en") or out.get("name_ru") or code)
    return out


def _iter_tokens_for_game(game: dict) -> set[str]:
    code = str(game.get("code") or "").strip()
    name_ru = str(game.get("name_ru") or "")
    name_en = str(game.get("name_en") or "")

    token_sources = [
        _norm(code),
        _norm(name_ru),
        _norm(name_en),
        _norm(_translit_ru_to_lat(name_ru)),
        _norm(_translit_ru_to_lat(name_en)),
    ]

    tokens: set[str] = set()
    for src in token_sources:
        for t in src.split():
            if len(t) < 2:
                continue
            tokens.add(t)
            if len(t) >= 3:
                for n in range(3, min(len(t), 8) + 1):
                    tokens.add(t[:n])
    return tokens


class GamesService:
    def __init__(self, mdbx_path: str = "data/games.mdbx"):
        self.mdbx_path = Path(mdbx_path)

        self._env: Env | None = None
        self._meta = None
        self._games = None
        self._order = None
        self._rank = None
        self._token = None

        self._count: int = 0
        self._cache_by_code: dict[str, dict] = {}

        self.load()

    def load(self) -> None:
        if not _HAS_MDBX or Env is None:
            raise RuntimeError("libmdbx is not available")
        self._cache_by_code = {}

        if self._env is None:
            self._open_mdbx()
        self._open_maps()
        self._ensure_schema()
        self._count = self._read_count()

    def _open_mdbx(self) -> None:
        assert Env is not None and MDBXEnvFlags is not None
        self.mdbx_path.parent.mkdir(parents=True, exist_ok=True)
        flags = MDBXEnvFlags.MDBX_ENV_DEFAULTS | MDBXEnvFlags.MDBX_NOSUBDIR
        self._env = Env(
            str(self.mdbx_path),
            flags=flags,
            maxreaders=64,
            maxdbs=16,
        )

    def _close_mdbx(self) -> None:
        if self._env is not None:
            try:
                self._env.close()
            except Exception:
                pass
        self._env = None
        self._meta = self._games = self._order = self._rank = self._token = None

    def _open_maps(self) -> None:
        assert self._env is not None and MDBXDBFlags is not None
        with self._env.rw_transaction() as txn:
            self._meta = txn.open_map(MDBX_MAP_META, MDBXDBFlags.MDBX_CREATE)
            self._games = txn.open_map(MDBX_MAP_GAMES, MDBXDBFlags.MDBX_CREATE)
            self._order = txn.open_map(MDBX_MAP_ORDER, MDBXDBFlags.MDBX_CREATE)
            self._rank = txn.open_map(MDBX_MAP_RANK, MDBXDBFlags.MDBX_CREATE)
            self._token = txn.open_map(
                MDBX_MAP_TOKEN,
                MDBXDBFlags.MDBX_CREATE | MDBXDBFlags.MDBX_DUPSORT,
            )
            txn.commit()

    def _meta_get(self, key: bytes) -> bytes | None:
        if not self._env or not self._meta:
            return None
        with self._env.ro_transaction() as txn:
            return self._meta.get(txn, key)

    def _meta_set(self, txn, key: bytes, value: bytes) -> None:
        assert self._meta is not None and MDBXPutFlags is not None
        self._meta.put(txn, key, value, flags=MDBXPutFlags.MDBX_UPSERT)  # type: ignore[arg-type]

    def _ensure_schema(self) -> None:
        if not self._env or not self._meta:
            return
        schema_raw = self._meta_get(b"schema")
        if schema_raw == str(MDBX_SCHEMA_VERSION).encode("utf-8"):
            return

        games = self._read_all_games_in_order()
        self.rebuild(games)

    def _read_count(self) -> int:
        raw = self._meta_get(b"count") or b"0"
        try:
            return int(raw.decode("utf-8"))
        except Exception:
            return self._count_entries()

    def _count_entries(self) -> int:
        if not self._env or not self._order:
            return 0
        total = 0
        with self._env.ro_transaction() as txn:
            with Cursor(self._order, txn) as cur:  # type: ignore[arg-type]
                k, v = cur.get_full(_u32be(0), MDBXCursorOp.MDBX_SET_RANGE)  # type: ignore[arg-type]
                while v is not None:
                    total += 1
                    k, v = cur.get_full(None, MDBXCursorOp.MDBX_NEXT)  # type: ignore[arg-type]
        return total

    def _fetch_game_from_mdbx(self, txn, code_b: bytes) -> dict | None:
        assert self._games is not None
        raw = self._games.get(txn, code_b)
        if not raw:
            return None
        try:
            obj = json.loads(raw.decode("utf-8"))
            if isinstance(obj, dict):
                return _ensure_game_fields(obj)
        except Exception:
            return None
        return None

    def _read_all_games_in_order(self) -> list[dict]:
        if not self._env or not self._order or not self._games:
            return []
        out: list[dict] = []
        with self._env.ro_transaction() as txn:
            with Cursor(self._order, txn) as cur:  # type: ignore[arg-type]
                k, v = cur.get_full(_u32be(0), MDBXCursorOp.MDBX_SET_RANGE)  # type: ignore[arg-type]
                while v is not None:
                    game = self._fetch_game_from_mdbx(txn, v)
                    if game is not None:
                        out.append(game)
                    k, v = cur.get_full(None, MDBXCursorOp.MDBX_NEXT)  # type: ignore[arg-type]
        return out

    def rebuild(self, games: list[dict]) -> None:
        if not self._env or not self._meta or not self._games or not self._order or not self._rank or not self._token:
            raise RuntimeError("MDBX is not initialized")

        normalized = [_ensure_game_fields(g) for g in games if isinstance(g, dict)]
        with self._env.rw_transaction() as txn:
            self._games.drop(txn, delete=False)
            self._order.drop(txn, delete=False)
            self._rank.drop(txn, delete=False)
            self._token.drop(txn, delete=False)
            self._meta.drop(txn, delete=False)

            for rank, game in enumerate(normalized):
                code = str(game.get("code") or "")
                if not code:
                    continue
                code_b = code.encode("utf-8")
                rank_b = _u32be(rank)

                game_json = json.dumps(game, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
                self._games.put(txn, code_b, game_json, flags=MDBXPutFlags.MDBX_UPSERT)  # type: ignore[arg-type]
                self._order.put(txn, rank_b, code_b, flags=MDBXPutFlags.MDBX_UPSERT)  # type: ignore[arg-type]
                self._rank.put(txn, code_b, rank_b, flags=MDBXPutFlags.MDBX_UPSERT)  # type: ignore[arg-type]

                for token in _iter_tokens_for_game(game):
                    token_b = token.encode("utf-8")
                    self._token.put(txn, token_b, rank_b + code_b, flags=MDBXPutFlags.MDBX_UPSERT)  # type: ignore[arg-type]

            self._meta_set(txn, b"schema", str(MDBX_SCHEMA_VERSION).encode("utf-8"))
            self._meta_set(txn, b"count", str(len(normalized)).encode("utf-8"))
            txn.commit()

        self._cache_by_code = {}
        self._count = len(normalized)

    def count(self) -> int:
        return int(self._count)

    def list(self, limit: int | None = None, offset: int = 0) -> list[dict]:
        offset = max(0, int(offset or 0))
        if limit is not None:
            limit = max(0, int(limit))

        if not self._env or not self._order:
            return []
        if limit == 0:
            return []

        out: list[dict] = []
        with self._env.ro_transaction() as txn:
            assert self._games is not None
            with Cursor(self._order, txn) as cur:  # type: ignore[arg-type]
                k, v = cur.get_full(_u32be(offset), MDBXCursorOp.MDBX_SET_RANGE)  # type: ignore[arg-type]
                while v is not None and (limit is None or len(out) < limit):
                    game = self._fetch_game_from_mdbx(txn, v)
                    if game is not None:
                        out.append(game)
                    k, v = cur.get_full(None, MDBXCursorOp.MDBX_NEXT)  # type: ignore[arg-type]
        return out

    def get(self, code: str) -> dict | None:
        code = str(code or "").strip()
        if not code:
            return None

        cached = self._cache_by_code.get(code)
        if cached is not None:
            return dict(cached)

        if not self._env or not self._games:
            return None
        code_b = code.encode("utf-8")
        with self._env.ro_transaction() as txn:
            g = self._fetch_game_from_mdbx(txn, code_b)
        if g is None:
            return None
        self._cache_by_code[code] = dict(g)
        return dict(g)

    def label(self, code: str, lang: str) -> str:
        game = self.get(code)
        if not game:
            return code
        return str(game.get("name_en") if lang == "en" else game.get("name_ru"))

    def labels(self, codes: list[str], lang: str) -> list[str]:
        return [self.label(c, lang) for c in codes]

    def add(self, code: str, name_ru: str, name_en: str) -> None:
        code = str(code or "").strip()
        if not code or self.get(code):
            return

        if not self._env or not self._meta or not self._games or not self._order or not self._rank or not self._token:
            raise RuntimeError("MDBX is not initialized")

        rank = int(self._count)
        code_b = code.encode("utf-8")
        rank_b = _u32be(rank)
        game = _ensure_game_fields({"code": code, "name_ru": name_ru, "name_en": name_en, "playerCount": 0})
        game_json = json.dumps(game, ensure_ascii=False, separators=(",", ":")).encode("utf-8")

        with self._env.rw_transaction() as txn:
            self._games.put(txn, code_b, game_json, flags=MDBXPutFlags.MDBX_UPSERT)  # type: ignore[arg-type]
            self._order.put(txn, rank_b, code_b, flags=MDBXPutFlags.MDBX_UPSERT)  # type: ignore[arg-type]
            self._rank.put(txn, code_b, rank_b, flags=MDBXPutFlags.MDBX_UPSERT)  # type: ignore[arg-type]
            for token in _iter_tokens_for_game(game):
                self._token.put(txn, token.encode("utf-8"), rank_b + code_b, flags=MDBXPutFlags.MDBX_UPSERT)  # type: ignore[arg-type]
            self._meta_set(txn, b"schema", str(MDBX_SCHEMA_VERSION).encode("utf-8"))
            self._meta_set(txn, b"count", str(rank + 1).encode("utf-8"))
            txn.commit()

        self._count = rank + 1
        self._cache_by_code[code] = dict(game)

    def remove(self, code: str) -> bool:
        code = str(code or "").strip()
        if not code:
            return False
        if self.get(code) is None:
            return False

        games = [g for g in self.list() if str(g.get("code") or "") != code]
        self.rebuild(games)
        self._cache_by_code.pop(code, None)
        return True

    def page(self, page: int, page_size: int, exclude_codes: set[str] | None = None) -> tuple[list[dict], int]:
        exclude_codes = exclude_codes or set()
        page = max(0, int(page or 0))
        page_size = max(1, int(page_size or 20))
        total = self.count() - sum(1 for c in exclude_codes if self.get(c) is not None)
        total = max(0, total)
        if total == 0:
            return [], 0

        offset = page * page_size
        if offset >= total:
            page = max(0, (total - 1) // page_size)
            offset = page * page_size

        if not self._env or not self._order or not self._rank:
            return [], total

        exclude_ranks: list[int] = []
        with self._env.ro_transaction() as txn:
            for c in exclude_codes:
                rb = self._rank.get(txn, c.encode("utf-8"))
                r = _u32be_to_int(rb)
                if r is not None:
                    exclude_ranks.append(r)
        exclude_ranks.sort()

        start_rank = offset
        while True:
            before = 0
            for r in exclude_ranks:
                if r < start_rank:
                    before += 1
                else:
                    break
            new_rank = offset + before
            if new_rank == start_rank:
                break
            start_rank = new_rank

        out: list[dict] = []
        with self._env.ro_transaction() as txn:
            with Cursor(self._order, txn) as cur:  # type: ignore[arg-type]
                k, v = cur.get_full(_u32be(start_rank), MDBXCursorOp.MDBX_SET_RANGE)  # type: ignore[arg-type]
                while v is not None and len(out) < page_size:
                    code_s = v.decode("utf-8", errors="ignore")
                    if code_s and code_s not in exclude_codes:
                        game = self._fetch_game_from_mdbx(txn, v)
                        if game is not None:
                            out.append(game)
                    k, v = cur.get_full(None, MDBXCursorOp.MDBX_NEXT)  # type: ignore[arg-type]
        return out, total

    def search(self, query: str, page: int, page_size: int, exclude_codes: set[str] | None = None) -> tuple[list[dict], int]:
        exclude_codes = exclude_codes or set()
        page = max(0, int(page or 0))
        page_size = max(1, int(page_size or 20))
        variants = _query_variants(query)
        if not variants:
            return self.page(page, page_size, exclude_codes=exclude_codes)

        tokens: set[str] = set()
        for v in variants:
            tokens.update(v.split())
        index_keys = sorted({t for t in tokens if len(t) >= 3})

        if not self._env or not self._games or not self._order or not self._token:
            return [], 0

        candidates: dict[str, int] = {}
        max_candidates = 6000

        with self._env.ro_transaction() as txn:
            if index_keys:
                with Cursor(self._token, txn) as cur:  # type: ignore[arg-type]
                    for token in index_keys:
                        token_b = token.encode("utf-8")
                        k, v = cur.get_full(token_b, MDBXCursorOp.MDBX_SET_KEY)  # type: ignore[arg-type]
                        if k is None or v is None:
                            continue
                        while True:
                            if len(v) >= 5:
                                rank = _u32be_to_int(v[:4])
                                code_b = v[4:]
                                code_s = code_b.decode("utf-8", errors="ignore")
                                if code_s and code_s not in exclude_codes and rank is not None:
                                    prev = candidates.get(code_s)
                                    if prev is None or rank < prev:
                                        candidates[code_s] = rank
                            if len(candidates) >= max_candidates:
                                break
                            k2, v2 = cur.get_full(None, MDBXCursorOp.MDBX_NEXT_DUP)  # type: ignore[arg-type]
                            if k2 is None or v2 is None:
                                break
                            k, v = k2, v2
                        if len(candidates) >= max_candidates:
                            break

            if not candidates:
                take = 2000
                with Cursor(self._order, txn) as cur:  # type: ignore[arg-type]
                    k, v = cur.get_full(_u32be(0), MDBXCursorOp.MDBX_SET_RANGE)  # type: ignore[arg-type]
                    while v is not None and len(candidates) < take:
                        code_s = v.decode("utf-8", errors="ignore")
                        if code_s and code_s not in exclude_codes:
                            rank = _u32be_to_int(k)
                            if rank is not None:
                                candidates[code_s] = rank
                        k, v = cur.get_full(None, MDBXCursorOp.MDBX_NEXT)  # type: ignore[arg-type]

            scored: list[tuple[float, int, dict]] = []
            for code_s, _rank in candidates.items():
                game = self._fetch_game_from_mdbx(txn, code_s.encode("utf-8"))
                if game is None:
                    continue
                score = _game_match_score(game, variants)
                if score < 0.55:
                    continue
                pop = int(game.get("playerCount") or 0)
                scored.append((score, pop, game))

        scored.sort(key=lambda x: (x[0], x[1]), reverse=True)
        total = len(scored)
        if total == 0:
            return [], 0
        max_page = max(0, (total - 1) // page_size)
        page = max(0, min(page, max_page))
        start = page * page_size
        return [g for _, _, g in scored[start : start + page_size]], total


games_service = GamesService()

