"""用户注册、登录、退出相关测试。"""

from __future__ import annotations

from conftest import login, register


def test_register_get_returns_form(client):
    """GET /register 返回注册表单页面。"""
    response = client.get("/register")
    assert response.status_code == 200
    assert b"register" in response.data.lower() or b"\xe6\xb3\xa8\xe5\x86\x8c" in response.data


def test_register_success_creates_user_and_logs_in(client, app):
    """注册成功后写入用户并自动登录，重定向到首页。"""
    response = register(client, username="bob", password="hunter22")
    assert response.status_code == 200  # follow_redirects 后落在首页

    with app.app_context():
        from app import get_db

        user = get_db().execute("SELECT * FROM users WHERE username = ?", ("bob",)).fetchone()
        assert user is not None
        assert user["username"] == "bob"

    # session 已写入登录态
    with client.session_transaction() as sess:
        assert sess.get("user_id") is not None
        assert sess.get("username") == "bob"


def test_register_short_username_rejected(client, app):
    """用户名少于 2 个字符时注册失败。"""
    response = client.post(
        "/register",
        data={"username": "a", "password": "secret123", "confirm_password": "secret123"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    with app.app_context():
        from app import get_db

        assert get_db().execute("SELECT COUNT(*) AS c FROM users").fetchone()["c"] == 0


def test_register_short_password_rejected(client):
    """密码少于 6 个字符时注册失败。"""
    response = client.post(
        "/register",
        data={"username": "carol", "password": "12345", "confirm_password": "12345"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    with client.session_transaction() as sess:
        assert sess.get("user_id") is None


def test_register_password_mismatch_rejected(client):
    """两次密码不一致时注册失败。"""
    client.post(
        "/register",
        data={"username": "dave", "password": "secret123", "confirm_password": "different"},
        follow_redirects=True,
    )
    with client.session_transaction() as sess:
        assert sess.get("user_id") is None


def test_register_duplicate_username_rejected(client, app):
    """重复用户名注册被拒绝。"""
    register(client, username="alice", password="secret123")
    # 同名再注册一次
    client.post(
        "/register",
        data={"username": "alice", "password": "secret123", "confirm_password": "secret123"},
        follow_redirects=True,
    )
    with app.app_context():
        from app import get_db

        count = get_db().execute(
            "SELECT COUNT(*) AS c FROM users WHERE username = ?", ("alice",)
        ).fetchone()["c"]
        assert count == 1


def test_login_get_returns_form(client):
    """GET /login 返回登录表单页面。"""
    response = client.get("/login")
    assert response.status_code == 200


def test_login_success(client):
    """已注册用户登录成功，写入 session 并重定向首页。"""
    register(client, username="erin", password="secret123")
    response = login(client, username="erin", password="secret123")
    assert response.status_code == 200
    with client.session_transaction() as sess:
        assert sess.get("username") == "erin"


def test_login_wrong_password_fails(client):
    """密码错误时登录失败，不写入 session。"""
    register(client, username="frank", password="secret123")
    # 注册会自动登录，先退出回到未登录状态，再尝试错误密码登录。
    client.get("/logout")
    client.post(
        "/login",
        data={"username": "frank", "password": "wrong-password"},
        follow_redirects=True,
    )
    with client.session_transaction() as sess:
        assert sess.get("user_id") is None


def test_login_unknown_user_fails(client):
    """不存在的用户登录失败。"""
    client.post(
        "/login",
        data={"username": "ghost", "password": "secret123"},
        follow_redirects=True,
    )
    with client.session_transaction() as sess:
        assert sess.get("user_id") is None


def test_login_next_redirect(auth_client):
    """登录成功后跟随合法的 next 参数跳转。"""
    # auth_client 已登录 alice，先退出再用 next 登录
    auth_client.get("/logout")
    response = auth_client.post(
        "/login?next=/cart",
        data={"username": "alice", "password": "secret123"},
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert response.location.endswith("/cart")


def test_login_open_redirect_prevented(auth_client):
    """next 不是以 / 开头的相对路径时回退到首页，防止开放重定向。"""
    auth_client.get("/logout")
    response = auth_client.post(
        "/login?next=http://evil.com",
        data={"username": "alice", "password": "secret123"},
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert response.location.endswith("/")  # 回到首页而非外站


def test_logout_clears_session(auth_client):
    """退出登录后 session 被清空。"""
    assert auth_client.get("/logout", follow_redirects=True).status_code == 200
    with auth_client.session_transaction() as sess:
        assert sess.get("user_id") is None


def test_logout_redirects_to_index(auth_client):
    """退出登录后重定向到首页。"""
    response = auth_client.get("/logout", follow_redirects=False)
    assert response.status_code == 302
    assert response.location.endswith("/")
