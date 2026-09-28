"""已知问题（待修复缺陷）的验证测试。

以下用例用于复现当前应用中存在的真实缺陷。这些用例会"通过"，
但其通过恰恰证明了缺陷的存在。每个用例均标注缺陷编号，便于在
测试报告中追踪。
"""

from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# 缺陷 KD-001：缺少 CSRF 防护
# 所有 POST 路由均未校验 CSRF Token，攻击者可构造跨站请求伪造。
# ---------------------------------------------------------------------------
def test_no_csrf_protection_on_login_post(client):
    """KD-001：登录 POST 无需 CSRF Token 即可成功提交。"""
    from conftest import register, login

    register(client)
    client.get("/logout")
    # 直接 POST，不携带任何 CSRF Token，应被拒绝才合理；
    # 但当前应用不校验，请求成功（说明缺陷存在）。
    resp = client.post(
        "/login",
        data={"username": "alice", "password": "secret123"},
        follow_redirects=False,
    )
    assert resp.status_code == 302


def test_no_csrf_protection_on_register_post(client):
    """KD-001：注册 POST 无需 CSRF Token 即可创建用户。"""
    resp = client.post(
        "/register",
        data={
            "username": "csrf_victim",
            "password": "secret123",
            "confirm_password": "secret123",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 302  # 未校验 CSRF，直接成功


# ---------------------------------------------------------------------------
# 缺陷 KD-002：add_to_cart 未限制数量上限
# update_cart 将数量夹取到 [1, 99]，但 add_to_cart 用 quantity+1 累加，
# 无上限，导致两个接口的数量约束不一致。
# ---------------------------------------------------------------------------
def test_add_to_cart_quantity_can_exceed_99(auth_client, app):
    """KD-002：连续加入同一本书 100 次后，数量超过 99。"""
    from app import get_db

    for _ in range(100):
        auth_client.post("/cart/add/1")
    with app.app_context():
        row = get_db().execute(
            "SELECT quantity FROM cart_items WHERE user_id = ? AND book_id = ?",
            (1, 1),
        ).fetchone()
    # 缺陷：数量应为 100，超过 update_cart 的 99 上限。
    assert row["quantity"] == 100


# ---------------------------------------------------------------------------
# 缺陷 KD-003：登录无频率限制
# 登录失败无计数与锁定机制，可被暴力破解。
# ---------------------------------------------------------------------------
def test_login_has_no_rate_limit(client):
    """KD-003：连续 20 次错误密码登录后，仍返回正常错误而非锁定。"""
    from conftest import register

    register(client)
    client.get("/logout")
    for _ in range(20):
        resp = client.post(
            "/login",
            data={"username": "alice", "password": "wrong-password"},
            follow_redirects=True,
        )
        # 每次都返回登录页（含错误提示），未出现锁定/429 等限制
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# 缺陷 KD-004：结算重复提交生成重复订单
# checkout 的 POST 未做幂等处理，快速重复提交会生成多个相同订单。
# ---------------------------------------------------------------------------
def test_checkout_duplicate_submission_creates_two_orders(auth_client, app):
    """KD-004：连续两次提交结算，生成两个独立订单。"""
    from app import get_db

    # 加两本书
    auth_client.post("/cart/add/1")
    auth_client.post("/cart/add/2")
    # 连续两次提交结算
    resp1 = auth_client.post("/checkout", follow_redirects=False)
    resp2 = auth_client.post("/checkout", follow_redirects=False)
    # 两次都应重定向到订单详情
    assert resp1.status_code == 302
    assert resp2.status_code == 302
    # 订单详情 URL 不同，说明生成了两个订单
    assert resp1.headers["Location"] != resp2.headers["Location"]
    with app.app_context():
        count = get_db().execute(
            "SELECT COUNT(*) AS c FROM orders WHERE user_id = ?", (1,)
        ).fetchone()["c"]
    assert count == 2  # 缺陷：重复提交生成了两个订单
