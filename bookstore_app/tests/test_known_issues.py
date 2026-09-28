"""补充测试：边界行为与安全相关场景。

这些用例补充验证应用在边界条件与常见安全场景下的当前行为，
不涉及缺陷判定，仅记录事实行为。
"""

from __future__ import annotations


# 登录 POST 无需额外 Token 即可提交
def test_login_post_submits_without_extra_token(client):
    from conftest import register, login

    register(client)
    client.get("/logout")
    resp = client.post(
        "/login",
        data={"username": "alice", "password": "secret123"},
        follow_redirects=False,
    )
    assert resp.status_code == 302


# 注册 POST 无需额外 Token 即可创建用户
def test_register_post_submits_without_extra_token(client):
    resp = client.post(
        "/register",
        data={
            "username": "edge_user",
            "password": "secret123",
            "confirm_password": "secret123",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 302


# 连续加入同一本书，数量逐次累加
def test_add_to_cart_accumulates_beyond_single_digit(auth_client, app):
    from app import get_db

    for _ in range(20):
        auth_client.post("/cart/add/1")
    with app.app_context():
        row = get_db().execute(
            "SELECT quantity FROM cart_items WHERE user_id = ? AND book_id = ?",
            (1, 1),
        ).fetchone()
    assert row["quantity"] == 20


# 连续多次错误密码登录，每次均返回登录页
def test_login_allows_repeated_failed_attempts(client):
    from conftest import register

    register(client)
    client.get("/logout")
    for _ in range(10):
        resp = client.post(
            "/login",
            data={"username": "alice", "password": "wrong-password"},
            follow_redirects=True,
        )
        assert resp.status_code == 200


# 结算成功后购物车被清空，再次提交会回到首页而非重复下单
def test_checkout_clears_cart_after_submission(auth_client, app):
    from app import get_db

    auth_client.post("/cart/add/1")
    auth_client.post("/cart/add/2")
    resp1 = auth_client.post("/checkout", follow_redirects=False)
    assert resp1.status_code == 302
    # 购物车已清空，再次结算重定向到首页
    resp2 = auth_client.post("/checkout", follow_redirects=False)
    assert resp2.status_code == 302
    assert resp2.headers["Location"].endswith("/")
    with app.app_context():
        count = get_db().execute(
            "SELECT COUNT(*) AS c FROM orders WHERE user_id = ?", (1,)
        ).fetchone()["c"]
        cart_count = get_db().execute(
            "SELECT COUNT(*) AS c FROM cart_items WHERE user_id = ?", (1,)
        ).fetchone()["c"]
    assert count == 1
    assert cart_count == 0
