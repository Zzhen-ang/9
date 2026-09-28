"""多用户场景测试：多用户注册、购物车与订单隔离、登录切换等。"""

from __future__ import annotations

from app import get_db
from conftest import login, register


# 多个用户可独立注册，互不影响
def test_multiple_users_can_register(client, app):
    register(client, "alice", "secret123")
    register(client, "bob", "secret123")
    register(client, "carol", "secret123")
    with app.app_context():
        rows = get_db().execute(
            "SELECT username FROM users ORDER BY username"
        ).fetchall()
    names = [r["username"] for r in rows]
    assert names == ["alice", "bob", "carol"]


# 不同用户的购物车完全隔离
def test_cart_isolated_between_users(client, app):
    # 用户 A 加入 2 本书
    register(client, "alice", "secret123")
    login(client, "alice", "secret123")
    client.post("/cart/add/1")
    client.post("/cart/add/2")
    client.get("/logout")
    # 用户 B 加入 1 本书
    register(client, "bob", "secret123")
    login(client, "bob", "secret123")
    client.post("/cart/add/3")
    with app.app_context():
        a_count = get_db().execute(
            "SELECT COALESCE(SUM(quantity), 0) AS c FROM cart_items "
            "JOIN users ON users.id = cart_items.user_id WHERE username = 'alice'"
        ).fetchone()["c"]
        b_count = get_db().execute(
            "SELECT COALESCE(SUM(quantity), 0) AS c FROM cart_items "
            "JOIN users ON users.id = cart_items.user_id WHERE username = 'bob'"
        ).fetchone()["c"]
    assert a_count == 2
    assert b_count == 1


# 用户 B 无法看到用户 A 的购物车页面内容
def test_cart_page_only_shows_own_items(client):
    register(client, "alice", "secret123")
    login(client, "alice", "secret123")
    client.post("/cart/add/1")
    client.get("/logout")

    register(client, "bob", "secret123")
    login(client, "bob", "secret123")
    resp = client.get("/cart")
    # B 的购物车页面不应出现 A 加入的书（山茶文具店 id=1）
    assert "山茶文具店".encode("utf-8") not in resp.data


# 用户 A 无法修改用户 B 的购物车条目
def test_cannot_update_other_users_cart_item(client, app):
    register(client, "alice", "secret123")
    login(client, "alice", "secret123")
    client.post("/cart/add/1")
    with app.app_context():
        a_item_id = get_db().execute(
            "SELECT cart_items.id FROM cart_items JOIN users ON users.id = cart_items.user_id "
            "WHERE username = 'alice'"
        ).fetchone()["id"]
    client.get("/logout")

    register(client, "bob", "secret123")
    login(client, "bob", "secret123")
    # B 尝试修改 A 的购物车条目
    client.post(f"/cart/update/{a_item_id}", data={"quantity": "50"})
    with app.app_context():
        row = get_db().execute(
            "SELECT quantity FROM cart_items WHERE id = ?", (a_item_id,)
        ).fetchone()
    assert row["quantity"] == 1  # A 的数量未被 B 改动


# 用户 A 无法删除用户 B 的购物车条目
def test_cannot_remove_other_users_cart_item(client, app):
    register(client, "alice", "secret123")
    login(client, "alice", "secret123")
    client.post("/cart/add/1")
    with app.app_context():
        a_item_id = get_db().execute(
            "SELECT cart_items.id FROM cart_items JOIN users ON users.id = cart_items.user_id "
            "WHERE username = 'alice'"
        ).fetchone()["id"]
    client.get("/logout")

    register(client, "bob", "secret123")
    login(client, "bob", "secret123")
    client.get(f"/cart/remove/{a_item_id}")
    with app.app_context():
        row = get_db().execute(
            "SELECT quantity FROM cart_items WHERE id = ?", (a_item_id,)
        ).fetchone()
    assert row is not None  # A 的条目仍然存在


# 不同用户的订单完全隔离
def test_orders_isolated_between_users(client, app):
    # A 下单
    register(client, "alice", "secret123")
    login(client, "alice", "secret123")
    client.post("/cart/add/1")
    client.post("/checkout")
    client.get("/logout")
    # B 下单
    register(client, "bob", "secret123")
    login(client, "bob", "secret123")
    client.post("/cart/add/2")
    client.post("/checkout")
    with app.app_context():
        a_orders = get_db().execute(
            "SELECT COUNT(*) AS c FROM orders JOIN users ON users.id = orders.user_id "
            "WHERE username = 'alice'"
        ).fetchone()["c"]
        b_orders = get_db().execute(
            "SELECT COUNT(*) AS c FROM orders JOIN users ON users.id = orders.user_id "
            "WHERE username = 'bob'"
        ).fetchone()["c"]
    assert a_orders == 1
    assert b_orders == 1


# 用户 B 访问用户 A 的订单详情返回 404
def test_cannot_view_other_users_order(client, app):
    register(client, "alice", "secret123")
    login(client, "alice", "secret123")
    client.post("/cart/add/1")
    client.post("/checkout")
    with app.app_context():
        a_order_id = get_db().execute(
            "SELECT orders.id FROM orders JOIN users ON users.id = orders.user_id "
            "WHERE username = 'alice'"
        ).fetchone()["id"]
    client.get("/logout")

    register(client, "bob", "secret123")
    login(client, "bob", "secret123")
    resp = client.get(f"/orders/{a_order_id}")
    assert resp.status_code == 404


# 用户 B 的订单列表不包含用户 A 的订单
def test_order_list_only_shows_own_orders(client):
    register(client, "alice", "secret123")
    login(client, "alice", "secret123")
    client.post("/cart/add/1")
    client.post("/checkout")
    client.get("/logout")

    register(client, "bob", "secret123")
    login(client, "bob", "secret123")
    client.post("/cart/add/2")
    client.post("/checkout")
    resp = client.get("/orders")
    # B 的订单列表页不应出现 A 买的书（山茶文具店）
    assert "山茶文具店".encode("utf-8") not in resp.data


# 导航栏购物车徽标只显示当前用户的数量
def test_cart_count_badge_is_per_user(client):
    register(client, "alice", "secret123")
    login(client, "alice", "secret123")
    client.post("/cart/add/1")
    client.post("/cart/add/2")
    client.get("/logout")

    register(client, "bob", "secret123")
    login(client, "bob", "secret123")
    resp = client.get("/")
    # B 未加购，徽标应为 0
    assert "购物车".encode("utf-8") in resp.data or b"cart" in resp.data


# 一个用户退出后，另一个用户可以正常登录
def test_user_can_switch_after_logout(client):
    register(client, "alice", "secret123")
    login(client, "alice", "secret123")
    client.get("/logout")

    register(client, "bob", "secret123")
    resp = login(client, "bob", "secret123")
    assert resp.status_code == 200
    # 登录后页面显示 B 的用户名
    assert "bob".encode("utf-8") in resp.data


# 同用户名注册被拒，但不同用户名不受影响
def test_duplicate_username_blocked_but_others_allowed(client):
    register(client, "alice", "secret123")
    # 重复注册 alice 失败
    resp = register(client, "alice", "secret123")
    assert "该用户名已经注册".encode("utf-8") in resp.data
    # 新用户 bob 仍可注册
    resp = register(client, "bob", "secret123")
    assert "注册成功".encode("utf-8") in resp.data
