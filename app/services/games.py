from __future__ import annotations

import json
from pathlib import Path


class GamesService:
    def __init__(self, path: str = "data/games.json"):
        self.path = Path(path)
        self._games: list[dict] = []
        self.load()

    def load(self) -> None:
        try:
            self._games = json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            self._games = []

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self._games, ensure_ascii=False, indent=2), encoding="utf-8")

    def list(self) -> list[dict]:
        return list(self._games)

    def get(self, code: str) -> dict | None:
        for g in self._games:
            if g.get("code") == code:
                return g
        return None

    def label(self, code: str, lang: str) -> str:
        game = self.get(code)
        if not game:
            return code
        return game.get("name_en") if lang == "en" else game.get("name_ru")

    def labels(self, codes: list[str], lang: str) -> list[str]:
        return [self.label(c, lang) for c in codes]

    def add(self, code: str, name_ru: str, name_en: str) -> None:
        if self.get(code):
            return
        self._games.append({"code": code, "name_ru": name_ru, "name_en": name_en})
        self.save()

    def remove(self, code: str) -> bool:
        before = len(self._games)
        self._games = [g for g in self._games if g.get("code") != code]
        if len(self._games) != before:
            self.save()
            return True
        return False


games_service = GamesService()

