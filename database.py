import os
import asyncio
import libsql_client


class Database:
    def __init__(self):
        self._url = os.environ["TURSO_DATABASE_URL"]
        self._auth_token = os.environ.get("TURSO_AUTH_TOKEN", "")
        asyncio.run(self._init_tables())

    def _make_client(self):
        return libsql_client.create_client(url=self._url, auth_token=self._auth_token)

    async def _init_tables(self):
        async with self._make_client() as c:
            await c.batch([
                "CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY)",
                """CREATE TABLE IF NOT EXISTS folders (
                    id      INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    name    TEXT    NOT NULL,
                    UNIQUE(user_id, name),
                    FOREIGN KEY(user_id) REFERENCES users(id)
                )""",
                """CREATE TABLE IF NOT EXISTS medias (
                    id         INTEGER PRIMARY KEY AUTOINCREMENT,
                    folder_id  INTEGER NOT NULL,
                    file_id    TEXT    NOT NULL,
                    media_type TEXT    NOT NULL,
                    caption    TEXT    DEFAULT '',
                    created_at TEXT    DEFAULT (datetime('now')),
                    FOREIGN KEY(folder_id) REFERENCES folders(id) ON DELETE CASCADE
                )""",
            ])

    def _run(self, coro):
        return asyncio.run(coro)

    def ensure_user(self, user_id: int):
        async def _():
            async with self._make_client() as c:
                await c.execute("INSERT OR IGNORE INTO users (id) VALUES (?)", [user_id])
        self._run(_())

    def get_folders(self, user_id: int) -> list[dict]:
        async def _():
            async with self._make_client() as c:
                rs = await c.execute(
                    "SELECT f.id, f.name, COUNT(m.id) FROM folders f "
                    "LEFT JOIN medias m ON m.folder_id = f.id "
                    "WHERE f.user_id = ? GROUP BY f.id ORDER BY f.name", [user_id])
                return [{"id": r[0], "name": r[1], "count": r[2]} for r in rs.rows]
        return self._run(_())

    def get_folder(self, user_id: int, folder_id: int) -> dict | None:
        async def _():
            async with self._make_client() as c:
                rs = await c.execute(
                    "SELECT id, name FROM folders WHERE id = ? AND user_id = ?", [folder_id, user_id])
                return {"id": rs.rows[0][0], "name": rs.rows[0][1]} if rs.rows else None
        return self._run(_())

    def folder_name_exists(self, user_id: int, name: str) -> bool:
        async def _():
            async with self._make_client() as c:
                rs = await c.execute(
                    "SELECT 1 FROM folders WHERE user_id = ? AND name = ?", [user_id, name])
                return len(rs.rows) > 0
        return self._run(_())

    def create_folder(self, user_id: int, name: str):
        async def _():
            async with self._make_client() as c:
                await c.execute("INSERT INTO folders (user_id, name) VALUES (?, ?)", [user_id, name])
        self._run(_())

    def rename_folder(self, user_id: int, folder_id: int, new_name: str):
        async def _():
            async with self._make_client() as c:
                await c.execute(
                    "UPDATE folders SET name = ? WHERE id = ? AND user_id = ?", [new_name, folder_id, user_id])
        self._run(_())

    def delete_folder(self, user_id: int, folder_id: int):
        async def _():
            async with self._make_client() as c:
                await c.execute(
                    "DELETE FROM folders WHERE id = ? AND user_id = ?", [folder_id, user_id])
        self._run(_())

    def get_medias(self, folder_id: int) -> list[dict]:
        async def _():
            async with self._make_client() as c:
                rs = await c.execute(
                    "SELECT id, file_id, media_type, caption, created_at FROM medias "
                    "WHERE folder_id = ? ORDER BY created_at DESC", [folder_id])
                return [{"id": r[0], "file_id": r[1], "media_type": r[2],
                         "caption": r[3], "created_at": r[4]} for r in rs.rows]
        return self._run(_())

    def get_media(self, media_id: int) -> dict | None:
        async def _():
            async with self._make_client() as c:
                rs = await c.execute(
                    "SELECT id, file_id, media_type, caption FROM medias WHERE id = ?", [media_id])
                return {"id": rs.rows[0][0], "file_id": rs.rows[0][1],
                        "media_type": rs.rows[0][2], "caption": rs.rows[0][3]} if rs.rows else None
        return self._run(_())

    def add_media(self, folder_id: int, file_id: str, media_type: str, caption: str):
        async def _():
            async with self._make_client() as c:
                await c.execute(
                    "INSERT INTO medias (folder_id, file_id, media_type, caption) VALUES (?, ?, ?, ?)",
                    [folder_id, file_id, media_type, caption])
        self._run(_())

    def delete_media(self, media_id: int):
        async def _():
            async with self._make_client() as c:
                await c.execute("DELETE FROM medias WHERE id = ?", [media_id])
        self._run(_())

    def count_medias(self, folder_id: int) -> int:
        async def _():
            async with self._make_client() as c:
                rs = await c.execute(
                    "SELECT COUNT(*) FROM medias WHERE folder_id = ?", [folder_id])
                return rs.rows[0][0] if rs.rows else 0
        return self._run(_())
