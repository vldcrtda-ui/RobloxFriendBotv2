# Roblox Match Bot (Telegram, aiogram)

Бот для подбора напарников в Roblox и рандом‑чатов. Реализован по спецификации `BOT_EXPERIENCE.md`.

## Запуск в Docker

1. Скопируйте пример окружения:
   ```bash
   cp .env.example .env
   ```
2. В `.env` укажите `BOT_TOKEN` и при желании `ADMIN_IDS`.
3. Запустите:
   ```bash
   docker compose up --build
   ```

База данных по умолчанию — SQLite в `data/bot.db` (монтируется volume).

## Локальный запуск (без Docker)

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
set BOT_TOKEN=...
python -m app.main
```

## Команды

Пользовательские: `/start`, `/browse`, `/search`, `/chat`, `/profile`, `/blocklist`, `/exit_chat`, `/cancel`, `/help`.

Админские (IDs из `ADMIN_IDS`): `/admin` (inline‑панель), `/metrics`, `/ban`, `/unban`, `/broadcast`, `/games`, `/active_chats`, `/chat_history`, `/banstatus`.

В админ‑панели доступны кнопки для:
- просмотра метрик;
- поиска пользователя по ID/нику и действий: бан/разбан/удаление/завершение чата;
- списка активных чатов, истории и закрытия;
- просмотра жалоб и перехода к модерации пользователя;
- управления играми (добавить/удалить/перезагрузить JSON);
- рассылки;
- ручного запуска и статистики реэнгейджмента.
