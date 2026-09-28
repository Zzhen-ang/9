"""缺陷复现测试。

这些用例按需求/安全规则断言，当前应用实现存在缺陷，
因此这些用例会失败，用于证明缺陷存在。
"""

from __future__ import annotations


# BUG-001：开放重定向绕过
# next 参数仅校验 startswith("/")，但 //evil.com 也以 / 开头，
# 浏览器会将 //evil.com 解析为协议相对 URL，跳转到外部站点。
def test_login_next_protocol_relative_redirect_blocked(auth_client):
    """登录后 next=//evil.com 不应跳转到外部站点。"""
    from conftest import register, login

    register(auth_client)
    auth_client.get("/logout")
    resp = auth_client.post(
        "/login?next=//evil.com",
        data={"username": "alice", "password": "secret123"},
        follow_redirects=False,
    )
    location = resp.headers.get("Location", "")
    # 缺陷：当前会跳转到 //evil.com（外部站点），应被拒绝并回退首页
    assert not location.startswith("//"), (
        f"开放重定向漏洞：next=//evil.com 被允许，Location={location}"
    )


# BUG-002：加购数量上限不一致
# update_cart 将数量夹取到 [1, 99]，但 add_to_cart 用 quantity+1 无上限。
def test_add_to_cart_respects_quantity_upper_bound(auth_client, app):
    """连续加购同一本书，数量不应超过 99。"""
    from app import get_db

    for _ in range(100):
        auth_client.post("/cart/add/1")
    with app.app_context():
        qty = get_db().execute(
            "SELECT quantity FROM cart_items WHERE user_id = ? AND book_id = ?",
            (1, 1),
        ).fetchone()["quantity"]
    # 缺陷：当前 qty=100，应被限制在 99
    assert qty <= 99, f"加购数量上限失效：quantity={qty}（应 <= 99）"
