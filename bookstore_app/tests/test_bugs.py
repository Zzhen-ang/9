"""缺陷复现测试。

以下用例按需求/安全规则断言。当前应用实现存在缺陷，
因此这些用例会失败，用于证明缺陷存在。
不修改任何应用源代码。
"""

from __future__ import annotations


# BUG-001：开放重定向绕过（next 参数）
# next 仅校验 startswith("/")，但 //evil.com 也以 / 开头，
# 浏览器将 //evil.com 解析为协议相对 URL，跳转到外部站点。
def test_login_next_protocol_relative_redirect_blocked(auth_client):
    from conftest import register, login

    register(auth_client)
    auth_client.get("/logout")
    resp = auth_client.post(
        "/login?next=//evil.com",
        data={"username": "alice", "password": "secret123"},
        follow_redirects=False,
    )
    location = resp.headers.get("Location", "")
    assert not location.startswith("//"), (
        f"BUG-001 开放重定向：next=//evil.com 被允许，Location={location}"
    )


# BUG-002：加购数量上限不一致
# update_cart 夹取到 [1, 99]，add_to_cart 用 quantity+1 无上限。
def test_add_to_cart_respects_quantity_upper_bound(auth_client, app):
    from app import get_db

    for _ in range(100):
        auth_client.post("/cart/add/1")
    with app.app_context():
        qty = get_db().execute(
            "SELECT quantity FROM cart_items WHERE user_id = ? AND book_id = ?",
            (1, 1),
        ).fetchone()["quantity"]
    assert qty <= 99, f"BUG-002 加购上限失效：quantity={qty}（应 <= 99）"


# BUG-003：状态变更操作允许 GET 请求（CSRF 向量）
# add_to_cart / remove_from_cart / logout 均接受 GET，
# 攻击者可通过 <img src> 等方式跨站触发状态变更。
def test_add_to_cart_rejects_get(auth_client, app):
    from app import get_db

    before = 0
    with app.app_context():
        before = get_db().execute(
            "SELECT COALESCE(SUM(quantity),0) c FROM cart_items WHERE user_id=1"
        ).fetchone()["c"]
    auth_client.get("/cart/add/1")  # GET 不应改变状态
    with app.app_context():
        after = get_db().execute(
            "SELECT COALESCE(SUM(quantity),0) c FROM cart_items WHERE user_id=1"
        ).fetchone()["c"]
    assert after == before, f"BUG-003 GET /cart/add/1 改变了购物车：{before} -> {after}"


def test_remove_from_cart_rejects_get(auth_client, app):
    from app import get_db

    auth_client.post("/cart/add/1")
    with app.app_context():
        before = get_db().execute(
            "SELECT COUNT(*) c FROM cart_items WHERE user_id=1"
        ).fetchone()["c"]
    auth_client.get("/cart/remove/1")  # GET 不应改变状态
    with app.app_context():
        after = get_db().execute(
            "SELECT COUNT(*) c FROM cart_items WHERE user_id=1"
        ).fetchone()["c"]
    assert after == before, f"BUG-003 GET /cart/remove/1 改变了购物车：{before} -> {after}"


def test_logout_rejects_get(auth_client):
    auth_client.get("/logout")  # GET 不应清除会话
    with auth_client.session_transaction() as sess:
        assert "user_id" in sess, "BUG-003 GET /logout 清除了用户会话"


# BUG-004：更新/删除不存在的购物车条目仍提示成功
def test_update_nonexistent_cart_item_reports_failure(auth_client):
    resp = auth_client.post(
        "/cart/update/999999", data={"quantity": "5"}, follow_redirects=True
    )
    assert "购物车已更新".encode("utf-8") not in resp.data, (
        "BUG-004 更新不存在的条目仍提示'购物车已更新'"
    )


def test_remove_nonexistent_cart_item_reports_failure(auth_client):
    resp = auth_client.get("/cart/remove/999999", follow_redirects=True)
    assert "已从购物车移除".encode("utf-8") not in resp.data, (
        "BUG-004 删除不存在的条目仍提示'已从购物车移除'"
    )


# BUG-005：Referer 头伪造导致开放重定向
# add_to_cart 使用 request.referrer 做重定向，Referer 可被伪造为外部 URL。
def test_add_to_cart_does_not_redirect_to_forged_referer(auth_client):
    resp = auth_client.post(
        "/cart/add/1",
        headers={"Referer": "http://evil.com/phish"},
        follow_redirects=False,
    )
    location = resp.headers.get("Location", "")
    assert "evil.com" not in location, (
        f"BUG-005 Referer 伪造重定向到外部站点：Location={location}"
    )
