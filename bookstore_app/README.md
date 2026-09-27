# 书香集 · 独立网上书城

这是一个完全独立的 Flask + SQLite 网上书城示例，不读取或依赖 `books_design`。首次启动会在项目目录创建 `bookstore.db`，自动建表并写入 42 本示例书籍。用户密码使用 Werkzeug 哈希保存。

## 运行

```bash
cd bookstore_app
python -m venv .venv
# Windows
.venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

打开 <http://127.0.0.1:5001/>。也可以通过 `PORT=8000`（Windows PowerShell 使用 `$env:PORT=8000`）更换端口。

## 功能

- 首页品牌栏、搜索、分类导航、推荐横幅和本地 SVG 书封（内置 42 本书）
- 书名/作者搜索、分类筛选、书籍详情和相关推荐
- 注册、登录、退出，密码哈希存储
- 登录后的购物车增删改和结算
- 订单创建、订单列表和订单详情

数据库位置可用 `BOOKSTORE_DATABASE` 环境变量覆盖，密钥可用 `BOOKSTORE_SECRET_KEY` 覆盖。

## 下载真实书籍封面

`download_covers.py` 使用公开的 [Open Library Search API](https://openlibrary.org/developers/api)
搜索书名（如果 `books` 表存在 ISBN 列则优先使用 ISBN），再从公开 Covers URL 下载 JPG/PNG。
成功的封面保存到 `static/covers/real/`，并将相对路径写回 `books.cover`；没有匹配或网络失败
的书会保留原来的 `book-N.svg`/`cover-N.svg` 动态或本地封面。每次运行都会覆盖
`cover-download-results.jsonl`，逐本记录查询、匹配、URL 和失败原因，因此可以安全重复运行。

```bash
cd bookstore_app
python download_covers.py
# 网络较慢时可延长超时；需要重新下载已有真实封面时：
python download_covers.py --timeout 30 --force
```

脚本设置了超时并捕获 API、下载和单本数据错误；即使完全离线也会正常结束，不会影响
`python app.py` 启动。封面路由会按文件类型提供 SVG、JPG 和 PNG。
