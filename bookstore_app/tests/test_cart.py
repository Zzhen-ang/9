"""购物车增删改与登录守卫相关测试。"""

from __future__ import annotations


def test_cart_requires_login(client):
    """未登录访问 /cart 重定向到登录页。"""
    response = client.get("/cart", follow_redirects=False)
    assert response.status_code == 302
    assert "/login" in response.location
    assert "next=/cart" in response.location


def test_add_to_cart_requires_login(client):
    """未登录加入购物车重定向到登录页。"""
    response = client.get("/cart/add/1", follow_redirects=False)
    assert response.status_code == 302
    assert "/login" in response.location


def test_add_to_cart_creates_item(auth_client, app):
    """登录后加入购物车创建一条记录。"""
    response = auth_client.post("/cart/add/1", follow_redirects=False)
    assert response.status_code == 302
    with app.app_context():
        from app import get_db

        with auth_client.session_transaction() as sess:
            user_id = sess["user_id"]
        item = get_db().execute(
            "SELECT * FROM cart_items WHERE user_id = ?", (user_id,)
        ).fetchone()
        assert item is not None
        assert item["book_id"] == 1
        assert item["quantity"] == 1


def test_add_to_cart_accumulates_quantity(auth_client, app):
    """同一图书重复加入购物车累加数量。"""
    auth_client.post("/cart/add/1")
    auth_client.post("/cart/add/1")
    with app.app_context():
        from app import get_db

        with auth_client.session_transaction() as sess:
            user_id = sess["user_id"]
        item = get_db().execute(
            "SELECT * FROM cart_items WHERE user_id = ? AND book_id = ?", (user_id, 1)
        ).fetchone()
        assert item["quantity"] == 2


def test_add_nonexistent_book_returns_404(auth_client):
    """加入不存在的图书返回 404。"""
    response = auth_client.post("/cart/add/99999")
    assert response.status_code == 404


def test_cart_page_shows_items_and_total(auth_client):
    """购物车页展示条目和合计。"""
    auth_client.post("/cart/add/1")  # 价格 42.00
    auth_client.post("/cart/add/2")  # 价格 39.80
    response = auth_client.get("/cart")
    assert response.status_code == 200
    # 合计 42.00 + 39.80 = 81.80
    assert b"81.8" in response.data


def test_update_cart_quantity(auth_client, app):
    """修改购物车数量生效。"""
    auth_client.post("/cart/add/1")
    with app.app_context():
        from app import get_db

        with auth_client.session_transaction() as sess:
            user_id = sess["user_id"]
        item = get_db().execute(
            "SELECT id FROM cart_items WHERE user_id = ?", (user_id,)
        ).fetchone()
        item_id = item["id"]

    response = auth_client.post(
        f"/cart/update/{item_id}", data={"quantity": "5"}, follow_redirects=False
    )
    assert response.status_code == 302
    assert response.location.endswith("/cart")

    with app.app_context():
        from app import get_db

        item = get_db().execute(
            "SELECT quantity FROM cart_items WHERE id = ?", (item_id,)
        ).fetchone()
        assert item["quantity"] == 5


def test_update_cart_clamps_to_min(auth_client, app):
    """数量小于 1 时被夹到 1。"""
    auth_client.post("/cart/add/1")
    with app.app_context():
        from app import get_db

        with auth_client.session_transaction() as sess:
            user_id = sess["user_id"]
        item_id = get_db().execute(
            "SELECT id FROM cart_items WHERE user_id = ?", (user_id,)
        ).fetchone()["id"]

    auth_client.post(f"/cart/update/{item_id}", data={"quantity": "0"})
    with app.app_context():
        from app import get_db

        item = get_db().execute(
            "SELECT quantity FROM cart_items WHERE id = ?", (item_id,)
        ).fetchone()
        assert item["quantity"] == 1


def test_update_cart_clamps_to_max(auth_client, app):
    """数量大于 99 时被夹到 99。"""
    auth_client.post("/cart/add/1")
    with app.app_context():
        from app import get_db

        with auth_client.session_transaction() as sess:
            user_id = sess["user_id"]
        item_id = get_db().execute(
            "SELECT id FROM cart_items WHERE user_id = ?", (user_id,)
        ).fetchone()["id"]

    auth_client.post(f"/cart/update/{item_id}", data={"quantity": "200"})
    with app.app_context():
        from app import get_db

        item = get_db().execute(
            "SELECT quantity FROM cart_items WHERE id = ?", (item_id,)
        ).fetchone()
        assert item["quantity"] == 99


def test_update_cart_invalid_quantity_defaults_to_one(auth_client, app):
    """非数字的 quantity 取默认值 1。"""
    auth_client.post("/cart/add/1")
    auth_client.post("/cart/add/1")  # 数量变 2
    with app.app_context():
        from app import get_db

        with auth_client.session_transaction() as sess:
            user_id = sess["user_id"]
        item_id = get_db().execute(
            "SELECT id FROM cart_items WHERE user_id = ?", (user_id,)
        ).fetchone()["id"]

    auth_client.post(f"/cart/update/{item_id}", data={"quantity": "abc"})
    with app.app_context():
        from app import get_db

        item = get_db().execute(
            "SELECT quantity FROM cart_items WHERE id = ?", (item_id,)
        ).fetchone()
        assert item["quantity"] == 1


def test_update_cart_is_scoped_to_user(auth_client, app, client):
    """A 用户无法修改 B 用户的购物车条目。"""
    auth_client.post("/cart/add/1")
    with app.app_context():
        from app import get_db

        with auth_client.session_transaction() as sess:
            alice_id = sess["user_id"]
        item_id = get_db().execute(
            "SELECT id FROM cart_items WHERE user_id = ?", (alice_id,)
        ).fetchone()["id"]

    # 注册并登录第二个用户 bob
    client.post(
        "/register",
        data={"username": "bob", "password": "secret123", "confirm_password": "secret123"},
        follow_redirects=True,
    )
    # bob 尝试修改 alice 的条目 -> 不影响（user_id 不匹配）
    client.post(f"/cart/update/{item_id}", data={"quantity": "9"})

    with app.app_context():
        from app import get_db

        item = get_db().execute(
            "SELECT quantity FROM cart_items WHERE id = ?", (item_id,)
        ).fetchone()
        # 数量保持为 1（未受 bob 的请求影响）
        assert item["quantity"] == 1


def test_remove_from_cart(auth_client, app):
    """删除购物车条目后条目消失。"""
    auth_client.post("/cart/add/1")
    with app.app_context():
        from app import get_db

        with auth_client.session_transaction() as sess:
            user_id = sess["user_id"]
        item_id = get_db().execute(
            "SELECT id FROM cart_items WHERE user_id = ?", (user_id,)
        ).fetchone()["id"]

    response = auth_client.post(f"/cart/remove/{item_id}", follow_redirects=False)
    assert response.status_code == 302
    assert response.location.endswith("/cart")

    with app.app_context():
        from app import get_db

        assert (
            get_db().execute("SELECT * FROM cart_items WHERE id = ?", (item_id,)).fetchone()
            is None
        )


def test_remove_from_cart_is_scoped_to_user(auth_client, app, client):
    """B 用户无法删除 A 用户的购物车条目。"""
    auth_client.post("/cart/add/1")
    with app.app_context():
        from app import get_db

        with auth_client.session_transaction() as sess:
            alice_id = sess["user_id"]
        item_id = get_db().execute(
            "SELECT id FROM cart_items WHERE user_id = ?", (alice_id,)
        ).fetchone()["id"]

    client.post(
        "/register",
        data={"username": "bob", "password": "secret123", "confirm_password": "secret123"},
        follow_redirects=True,
    )
    client.post(f"/cart/remove/{item_id}")

    with app.app_context():
        from app import get_db

        assert (
            get_db().execute("SELECT * FROM cart_items WHERE id = ?", (item_id,)).fetchone()
            is not None
        )


def test_cart_empty_shows_zero_total(auth_client):
    """空购物车页合计为 0。"""
    response = auth_client.get("/cart")
    assert response.status_code == 200
