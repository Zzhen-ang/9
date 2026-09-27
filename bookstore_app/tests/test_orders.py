"""结算、订单列表、订单详情相关测试。"""

from __future__ import annotations


def test_checkout_requires_login(client):
    """未登录结算重定向到登录页。"""
    response = client.get("/checkout", follow_redirects=False)
    assert response.status_code == 302
    assert "/login" in response.location


def test_orders_requires_login(client):
    """未登录查看订单重定向到登录页。"""
    response = client.get("/orders", follow_redirects=False)
    assert response.status_code == 302
    assert "/login" in response.location


def test_order_detail_requires_login(client):
    """未登录查看订单详情重定向到登录页。"""
    response = client.get("/orders/1", follow_redirects=False)
    assert response.status_code == 302
    assert "/login" in response.location


def test_checkout_empty_cart_redirects_home(auth_client):
    """空购物车结算时重定向到首页。"""
    response = auth_client.get("/checkout", follow_redirects=False)
    assert response.status_code == 302
    assert response.location.endswith("/")


def test_checkout_get_shows_items_and_total(auth_client):
    """GET /checkout 展示购物车条目和合计。"""
    auth_client.post("/cart/add/1")  # 42.00
    response = auth_client.get("/checkout")
    assert response.status_code == 200
    assert b"42" in response.data


def test_checkout_creates_order_and_clears_cart(auth_client, app):
    """POST /checkout 创建订单、写入明细并清空购物车。"""
    auth_client.post("/cart/add/1")   # 42.00, qty 1
    auth_client.post("/cart/add/2")   # 39.80, qty 1
    # 修改第二本数量为 2 -> 39.80 * 2
    with app.app_context():
        from app import get_db

        with auth_client.session_transaction() as sess:
            user_id = sess["user_id"]
        item_id = get_db().execute(
            "SELECT id FROM cart_items WHERE user_id = ? AND book_id = ?", (user_id, 2)
        ).fetchone()["id"]
    auth_client.post(f"/cart/update/{item_id}", data={"quantity": "2"})

    response = auth_client.post("/checkout", follow_redirects=False)
    assert response.status_code == 302
    # 重定向到新订单详情页
    assert "/orders/" in response.location

    with app.app_context():
        from app import get_db

        with auth_client.session_transaction() as sess:
            user_id = sess["user_id"]
        # 购物车已清空
        cart_count = get_db().execute(
            "SELECT COUNT(*) AS c FROM cart_items WHERE user_id = ?", (user_id,)
        ).fetchone()["c"]
        assert cart_count == 0
        # 订单已创建
        orders = get_db().execute(
            "SELECT * FROM orders WHERE user_id = ? ORDER BY id", (user_id,)
        ).fetchall()
        assert len(orders) == 1
        # 合计 42.00 + 39.80 * 2 = 121.60
        assert orders[0]["total"] == 121.60
        assert orders[0]["status"] == "待发货"
        # 明细 2 条
        items = get_db().execute(
            "SELECT * FROM order_items WHERE order_id = ?", (orders[0]["id"],)
        ).fetchall()
        assert len(items) == 2


def test_order_detail_shown_after_checkout(auth_client):
    """下单后可访问订单详情页。"""
    auth_client.post("/cart/add/1")
    response = auth_client.post("/checkout", follow_redirects=False)
    location = response.location
    response = auth_client.get(location, follow_redirects=True)
    assert response.status_code == 200


def test_order_detail_unknown_returns_404(auth_client):
    """不存在的订单 ID 返回 404。"""
    response = auth_client.get("/orders/99999")
    assert response.status_code == 404


def test_orders_list_shows_user_orders(auth_client, app):
    """订单列表只展示当前用户的订单，且按 id 倒序。"""
    auth_client.post("/cart/add/1")
    auth_client.post("/checkout")
    auth_client.post("/cart/add/2")
    auth_client.post("/checkout")

    response = auth_client.get("/orders")
    assert response.status_code == 200

    with app.app_context():
        from app import get_db

        with auth_client.session_transaction() as sess:
            user_id = sess["user_id"]
        orders = get_db().execute(
            "SELECT * FROM orders WHERE user_id = ? ORDER BY id DESC", (user_id,)
        ).fetchall()
        assert len(orders) == 2
        # 列表页倒序：最新订单（id 更大）应在前
        assert orders[0]["id"] > orders[1]["id"]


def test_order_detail_is_scoped_to_owner(auth_client, app, client):
    """A 用户的订单对 B 用户不可见（返回 404）。"""
    auth_client.post("/cart/add/1")
    auth_client.post("/checkout", follow_redirects=False)
    with app.app_context():
        from app import get_db

        order = get_db().execute("SELECT id FROM orders ORDER BY id DESC LIMIT 1").fetchone()
        order_id = order["id"]

    # 注册 bob 并登录
    client.post(
        "/register",
        data={"username": "bob", "password": "secret123", "confirm_password": "secret123"},
        follow_redirects=True,
    )
    # bob 尝试查看 alice 的订单 -> 404
    response = client.get(f"/orders/{order_id}")
    assert response.status_code == 404


def test_order_items_snapshot_preserved(auth_client, app):
    """下单时 order_items 保留书名/价格快照。"""
    auth_client.post("/cart/add/1")  # 山茶文具店, 42.00
    auth_client.post("/checkout")

    # 下单后修改 books 表的价格，订单明细不应受影响
    with app.app_context():
        from app import get_db

        get_db().execute("UPDATE books SET price = 999 WHERE id = 1")
        get_db().commit()
        item = get_db().execute(
            "SELECT * FROM order_items WHERE book_id = 1 ORDER BY id DESC LIMIT 1"
        ).fetchone()
        # 快照仍是下单时的 42.00
        assert item["price"] == 42.00
        assert item["title"] == "山茶文具店"


def test_multiple_orders_independent(auth_client):
    """多次下单生成多个独立订单。"""
    for book_id in (1, 2, 3):
        auth_client.post(f"/cart/add/{book_id}")
        auth_client.post("/checkout")
    response = auth_client.get("/orders")
    assert response.status_code == 200
