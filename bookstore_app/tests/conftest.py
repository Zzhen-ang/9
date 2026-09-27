"""共享测试夹具。

通过环境变量 ``BOOKSTORE_DATABASE`` 把数据库指向一个临时文件，避免测试触碰
项目自带的 ``bookstore.db``。该环境变量必须在导入 ``app`` 模块之前设置，因为
模块在导入时会执行 ``init_db()``。
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

import pytest

# 在导入 app 之前把数据库指向临时文件，确保 init_db() 写入临时库。
_TMP_DB = Path(tempfile.gettempdir()) / "bookstore_test.db"
os.environ["BOOKSTORE_DATABASE"] = str(_TMP_DB)
os.environ["BOOKSTORE_SECRET_KEY"] = "bookstore-test-key"

# 让测试能够 import app 包。
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import app as app_module  # noqa: E402  顺序：env -> sys.path -> import


@pytest.fixture()
def db_path(tmp_path) -> Path:
    """每个测试使用独立的临时数据库文件。"""
    return tmp_path / "test.db"


@pytest.fixture()
def app(db_path):
    """返回配置为使用临时数据库的 Flask 应用实例。"""
    app_module.app.config.update(
        DATABASE=str(db_path),
        SECRET_KEY="bookstore-test-key",
        TESTING=True,
    )
    with app_module.app.app_context():
        app_module.init_db()
    yield app_module.app


@pytest.fixture()
def client(app):
    """Flask 测试客户端。"""
    return app.test_client()


@pytest.fixture()
def runner(app):
    """Flask CLI 测试 runner。"""
    return app.test_cli_runner()


def register(client, username: str = "alice", password: str = "secret123"):
    """注册一个账号并返回响应。"""
    return client.post(
        "/register",
        data={"username": username, "password": password, "confirm_password": password},
        follow_redirects=True,
    )


def login(client, username: str = "alice", password: str = "secret123"):
    """登录并返回响应。"""
    return client.post(
        "/login",
        data={"username": username, "password": password},
        follow_redirects=True,
    )


@pytest.fixture()
def auth_client(client):
    """已注册并登录的客户端，同时返回创建的用户名。"""
    register(client)
    login(client)
    return client
