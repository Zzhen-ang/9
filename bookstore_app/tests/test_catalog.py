"""首页、图书详情、封面资源相关测试。"""

from __future__ import annotations

from app import SEED_BOOKS


def test_index_returns_200(client):
    """首页可访问。"""
    response = client.get("/")
    assert response.status_code == 200


def test_index_lists_all_seed_books(client):
    """首页默认列出全部种子图书。"""
    response = client.get("/")
    # 第一本种子书的标题
    first_title = SEED_BOOKS[0][0].encode("utf-8")
    assert first_title in response.data
    # 最后一本种子书的标题
    last_title = SEED_BOOKS[-1][0].encode("utf-8")
    assert last_title in response.data


def test_index_search_by_title(client):
    """按书名关键字搜索能筛出对应图书。

    首页固定渲染前 4 本作为“精选”横幅，因此用第 5 本（不在精选中）作为搜索
    目标，并断言另一本非精选、非匹配图书不出现在结果里。
    """
    target = SEED_BOOKS[4]   # 非暴力沟通 (id 5)
    absent = SEED_BOOKS[5]   # 百年孤独 (id 6)
    response = client.get("/?q=" + target[0])
    assert response.status_code == 200
    assert target[0].encode("utf-8") in response.data
    assert absent[0].encode("utf-8") not in response.data


def test_index_search_by_author(client):
    """按作者搜索能筛出对应图书。"""
    # 用不在精选横幅中的作者
    author = SEED_BOOKS[4][1]
    response = client.get("/?q=" + author)
    assert response.status_code == 200
    assert author.encode("utf-8") in response.data


def test_index_category_filter(client):
    """按分类筛选只返回该分类的图书。

    精选横幅固定展示前 4 本，所以选一本 id >= 5 且分类不同的图书作为“不应
    出现”的样本。
    """
    category = SEED_BOOKS[0][2]  # 文学
    response = client.get("/?category=" + category)
    assert response.status_code == 200
    assert SEED_BOOKS[0][0].encode("utf-8") in response.data
    other = next(b for b in SEED_BOOKS[4:] if b[2] != category)
    assert other[0].encode("utf-8") not in response.data


def test_index_search_and_category_combined(client):
    """同时传入 q 和 category 时两者叠加过滤。"""
    response = client.get("/?q=nonexistent&category=文学")
    # 没有匹配图书，页面仍正常渲染
    assert response.status_code == 200


def test_book_detail_existing(client):
    """存在的图书详情页返回 200 并包含图书信息。"""
    response = client.get("/book/1")
    assert response.status_code == 200
    assert SEED_BOOKS[0][0].encode("utf-8") in response.data
    assert SEED_BOOKS[0][1].encode("utf-8") in response.data


def test_book_detail_related_books_same_category(client):
    """详情页的推荐图书来自同一分类。"""
    # book 1 的分类是 文学，存在多本同分类图书
    response = client.get("/book/1")
    assert response.status_code == 200
    # 同分类的“云边有个小卖部”(id 2) 应作为相关推荐出现
    assert SEED_BOOKS[1][0].encode("utf-8") in response.data


def test_book_detail_not_found(client):
    """不存在的图书 ID 返回 404。"""
    response = client.get("/book/99999")
    assert response.status_code == 404


def test_cover_dynamic_svg_for_seed_book(client):
    """book-13.svg 走动态生成，返回 SVG 并包含书名。"""
    # id 13 是第一本使用 book-N.svg 的种子书（史记）
    book = SEED_BOOKS[12]  # 第 13 本
    response = client.get("/covers/book-13.svg")
    assert response.status_code == 200
    assert response.mimetype == "image/svg+xml"
    assert book[0].encode("utf-8") in response.data  # 书名出现在 SVG 中


def test_cover_dynamic_svg_for_unknown_book(client):
    """book-<不存在的 id>.svg 因数据库无记录，交给 send_from_directory -> 404。"""
    response = client.get("/covers/book-99999.svg")
    assert response.status_code == 404


def test_cover_static_svg_file(client):
    """cover-01.svg 作为静态文件正常返回。"""
    response = client.get("/covers/cover-01.svg")
    assert response.status_code == 200
    assert response.mimetype == "image/svg+xml"


def test_cover_missing_file_returns_404(client):
    """不存在的封面文件返回 404。"""
    response = client.get("/covers/does-not-exist.png")
    assert response.status_code == 404


def test_cover_path_traversal_blocked(client):
    """封面路由阻止路径遍历。"""
    # send_from_directory 会拒绝跳出根目录的请求
    response = client.get("/covers/../app.py")
    assert response.status_code in (400, 404)


def test_seed_books_all_inserted(client, app):
    """init_db 后所有种子图书都已写入数据库。"""
    with app.app_context():
        from app import get_db

        count = get_db().execute("SELECT COUNT(*) AS c FROM books").fetchone()["c"]
        assert count == len(SEED_BOOKS)


def test_seed_books_price_non_negative(client, app):
    """所有种子图书价格非负（符合 CHECK 约束）。"""
    with app.app_context():
        from app import get_db

        rows = get_db().execute("SELECT MIN(price) AS mn, MAX(price) AS mx FROM books").fetchone()
        assert rows["mn"] >= 0
        assert rows["mx"] >= 0


def test_invalid_book_id_route_rejects_non_integer(client):
    """非整数 book_id 走 int 转换器 -> 404。"""
    response = client.get("/book/not-a-number")
    assert response.status_code == 404
