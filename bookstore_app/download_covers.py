"""Download Open Library covers for the books in bookstore.db.

The script is deliberately independent from Flask startup: a slow or
unavailable network must never prevent the bookstore from starting.  A failed
match simply leaves the book's existing generated SVG cover unchanged.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import sys
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_DATABASE = Path(os.environ.get("BOOKSTORE_DATABASE", BASE_DIR / "bookstore.db"))
REAL_COVERS_DIR = BASE_DIR / "static" / "covers" / "real"
SEARCH_URL = "https://openlibrary.org/search.json"
USER_AGENT = "bookstore-app-cover-downloader/1.0 (public Open Library API)"
MAX_IMAGE_BYTES = 12 * 1024 * 1024


def normalise(value: str) -> str:
    """Make title/author comparison tolerant of punctuation and case."""
    return re.sub(r"[\W_]+", "", value or "", flags=re.UNICODE).casefold()


def words(value: str) -> set[str]:
    return {part for part in re.findall(r"[\w\u4e00-\u9fff]+", value or "", re.UNICODE) if len(part) > 1}


def request_bytes(url: str, timeout: float) -> tuple[bytes | None, str]:
    request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "image/*"})
    try:
        with urlopen(request, timeout=timeout) as response:
            status = getattr(response, "status", 200)
            if status != 200:
                return None, f"http_{status}"
            data = response.read(MAX_IMAGE_BYTES + 1)
            if len(data) > MAX_IMAGE_BYTES:
                return None, "image_too_large"
            return data, "ok"
    except HTTPError as error:
        return None, f"http_{error.code}"
    except (OSError, URLError, TimeoutError) as error:
        return None, type(error).__name__.lower()


def request_json(params: dict[str, str], timeout: float) -> tuple[dict | None, str]:
    url = f"{SEARCH_URL}?{urlencode(params)}"
    request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    try:
        with urlopen(request, timeout=timeout) as response:
            status = getattr(response, "status", 200)
            if status != 200:
                return None, f"http_{status}"
            return json.loads(response.read().decode("utf-8")), "ok"
    except HTTPError as error:
        return None, f"http_{error.code}"
    except (OSError, URLError, TimeoutError, UnicodeError, json.JSONDecodeError) as error:
        return None, type(error).__name__.lower()


def isbn_from_row(row: sqlite3.Row, columns: set[str]) -> str:
    for column in ("isbn", "isbn13", "isbn_13", "isbn10", "isbn_10"):
        if column in columns and row[column]:
            value = str(row[column]).strip()
            value = re.sub(r"[^0-9Xx]", "", value)
            if value:
                return value
    return ""


def choose_match(book: sqlite3.Row, docs: list[dict]) -> tuple[dict | None, int]:
    title = normalise(book["title"])
    author = normalise(book["author"])
    title_words = words(book["title"])
    author_words = words(book["author"])
    ranked: list[tuple[int, dict]] = []
    for doc in docs:
        candidate_title = str(doc.get("title") or "")
        candidate_author = " ".join(str(item) for item in (doc.get("author_name") or []))
        candidate = normalise(candidate_title)
        score = 0
        if candidate == title:
            score += 100
        elif title and (title in candidate or candidate in title):
            score += 70
        else:
            score += 25 * len(title_words & words(candidate_title))
        if author and normalise(candidate_author) == author:
            score += 35
        elif author_words & words(candidate_author):
            score += 15
        if doc.get("cover_i"):
            score += 5
        if doc.get("cover_i"):
            ranked.append((score, doc))
    if not ranked:
        return None, 0
    score, match = max(ranked, key=lambda item: item[0])
    # Search was already constrained by title/ISBN. Requiring a modest score
    # avoids attaching a random cover when Open Library returns fuzzy results.
    return (match, score) if score >= 30 else (None, score)


def download_book(book: sqlite3.Row, isbn: str, timeout: float) -> dict:
    result = {
        "book_id": book["id"],
        "title": book["title"],
        "author": book["author"],
        "previous_cover": book["cover"],
        "strategy": "isbn" if isbn else "title",
        "query": isbn or book["title"],
        "status": "no_match",
    }
    if isbn:
        params = {"isbn": isbn, "limit": "10", "fields": "title,author_name,cover_i,isbn"}
    else:
        params = {
            "title": book["title"],
            "limit": "10",
            "fields": "title,author_name,cover_i,isbn",
        }
    data, api_status = request_json(params, timeout)
    result["api_status"] = api_status
    if not data:
        result["status"] = "api_failed"
        return result
    match, score = choose_match(book, data.get("docs") or [])
    result["match_score"] = score
    if not match:
        result["status"] = "no_match"
        return result
    cover_id = match.get("cover_i")
    cover_url = f"https://covers.openlibrary.org/b/id/{cover_id}-L.jpg?default=false"
    result.update(
        matched_title=match.get("title"),
        matched_authors=match.get("author_name") or [],
        cover_url=cover_url,
    )
    image, image_status = request_bytes(cover_url, timeout)
    result["image_status"] = image_status
    if not image:
        result["status"] = "download_failed"
        return result
    if image.startswith(b"\xff\xd8\xff"):
        extension = "jpg"
    elif image.startswith(b"\x89PNG\r\n\x1a\n"):
        extension = "png"
    else:
        result["status"] = "not_an_image"
        return result
    destination = REAL_COVERS_DIR / f"book-{book['id']}.{extension}"
    temporary = destination.with_suffix(destination.suffix + ".part")
    try:
        temporary.write_bytes(image)
        os.replace(temporary, destination)
    except OSError as error:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass
        result["status"] = f"save_failed:{type(error).__name__.lower()}"
        return result
    result.update(status="downloaded", cover=f"real/{destination.name}", bytes=len(image))
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Download Open Library covers for bookstore books")
    parser.add_argument("--database", type=Path, default=DEFAULT_DATABASE)
    parser.add_argument("--timeout", type=float, default=12.0, help="HTTP timeout in seconds")
    parser.add_argument("--delay", type=float, default=0.15, help="Delay between API requests")
    parser.add_argument("--force", action="store_true", help="redownload books that already have a real file")
    parser.add_argument(
        "--results",
        type=Path,
        default=BASE_DIR / "cover-download-results.jsonl",
        help="JSONL file receiving one result per book",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    database = args.database
    REAL_COVERS_DIR.mkdir(parents=True, exist_ok=True)
    args.results.parent.mkdir(parents=True, exist_ok=True)
    try:
        db = sqlite3.connect(database)
        db.row_factory = sqlite3.Row
        columns = {row["name"].lower() for row in db.execute("PRAGMA table_info(books)")}
        books = db.execute("SELECT * FROM books ORDER BY id").fetchall()
    except (OSError, sqlite3.Error) as error:
        print(f"Cannot open bookstore database: {error}", file=sys.stderr)
        return 1
    if not books:
        print("No books found; nothing to download.")
        db.close()
        return 0

    downloaded = 0
    with args.results.open("w", encoding="utf-8") as log:
        for book in books:
            current = str(book["cover"] or "")
            current_path = BASE_DIR / "static" / "covers" / current
            if not args.force and current.startswith("real/") and current_path.is_file():
                result = {
                    "book_id": book["id"],
                    "title": book["title"],
                    "author": book["author"],
                    "previous_cover": current,
                    "strategy": "existing",
                    "query": "",
                    "status": "already_downloaded",
                    "cover": current,
                }
            else:
                try:
                    result = download_book(book, isbn_from_row(book, columns), args.timeout)
                except Exception as error:  # one bad record must not stop the batch
                    result = {
                        "book_id": book["id"],
                        "title": book["title"],
                        "author": book["author"],
                        "status": f"unexpected_error:{type(error).__name__.lower()}",
                    }
                if result.get("status") == "downloaded":
                    db.execute("UPDATE books SET cover = ? WHERE id = ?", (result["cover"], book["id"]))
                    db.commit()
                    downloaded += 1
            log.write(json.dumps(result, ensure_ascii=False) + "\n")
            log.flush()
            print(f"[{result['status']}] {book['id']}: {book['title']}")
            if args.delay:
                time.sleep(args.delay)
    db.close()
    print(f"Finished: {downloaded} new real cover(s); results: {args.results}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
