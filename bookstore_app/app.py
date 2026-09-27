"""A small, self-contained online bookstore built with Flask and SQLite."""

from __future__ import annotations

import os
import mimetypes
import sqlite3
from html import escape
from datetime import datetime
from functools import wraps
from pathlib import Path

from flask import (
    Flask,
    flash,
    g,
    redirect,
    render_template,
    request,
    Response,
    send_from_directory,
    session,
    url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash


# Ensure .svg is served as the standard image/svg+xml MIME type. Python's
# ``mimetypes`` module otherwise guesses ``image/svg`` (no ``+xml``), which
# some browsers refuse to render as an inline image.
mimetypes.add_type("image/svg+xml", ".svg")

BASE_DIR = Path(__file__).resolve().parent
DATABASE = Path(os.environ.get("BOOKSTORE_DATABASE", BASE_DIR / "bookstore.db"))
COVERS_DIR = BASE_DIR / "static" / "covers"

app = Flask(__name__)
app.config.update(
    SECRET_KEY=os.environ.get("BOOKSTORE_SECRET_KEY", "bookstore-development-key"),
    DATABASE=str(DATABASE),
)


@app.get("/covers/<path:filename>")
def cover(filename: str):
    """Serve generated SVG covers and downloaded image covers."""
    if filename.startswith("book-") and filename.endswith(".svg"):
        try:
            book_id = int(filename[5:-4])
        except ValueError:
            book_id = 0
        book = get_db().execute("SELECT title, author, category FROM books WHERE id = ?", (book_id,)).fetchone()
        if book is not None:
            colors = ("#b84b43", "#315b68", "#7a3f55", "#3e6d62", "#b36b32", "#4b527d")
            color = colors[(book_id - 1) % len(colors)]
            svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 600 820">
<rect width="600" height="820" fill="{color}"/><circle cx="470" cy="155" r="145" fill="#f3c37a" opacity=".85"/>
<path d="M0 590Q220 470 600 620V820H0Z" fill="#202c3b" opacity=".75"/>
<text x="48" y="86" fill="#fff" font-size="24" letter-spacing="5">{escape(book["category"])}</text>
<text x="48" y="475" fill="#fff" font-size="44" font-family="serif">{escape(book["title"])}</text>
<text x="50" y="535" fill="#ffe5c2" font-size="23">{escape(book["author"])}</text>
<text x="48" y="748" fill="#f8dfc9" font-size="18" letter-spacing="4">BOOKSHELF COLLECTION</text></svg>"""
            return Response(svg, mimetype="image/svg+xml")
    # Let Flask infer the MIME type so downloaded JPG/PNG files are displayed
    # correctly. ``send_from_directory`` also prevents path traversal.
    return send_from_directory(COVERS_DIR, filename)


SEED_BOOKS = [
    ("山茶文具店", "小川糸", "文学", 42.00, "在镰仓的小店里，替人写信，也替人找回生活的温度。", "cover-01.svg"),
    ("云边有个小卖部", "张嘉佳", "文学", 39.80, "关于故乡、亲情和成长的温柔故事。", "cover-02.svg"),
    ("人类简史", "尤瓦尔·赫拉利", "社科", 68.00, "从认知革命到科技革命，重新理解人类文明。", "cover-03.svg"),
    ("小王子", "安托万·德·圣埃克苏佩里", "少儿", 29.90, "写给大人也写给孩子的经典童话。", "cover-04.svg"),
    ("非暴力沟通", "马歇尔·卢森堡", "生活", 49.00, "用观察、感受、需要和请求改善人与人的连接。", "cover-05.svg"),
    ("百年孤独", "加西亚·马尔克斯", "文学", 55.00, "布恩迪亚家族七代人的传奇史诗。", "cover-06.svg"),
    ("原则", "瑞·达利欧", "经管", 88.00, "一套来自真实人生和工作实践的决策方法。", "cover-07.svg"),
    ("刻意练习", "安德斯·艾利克森", "成长", 45.00, "突破天赋迷思，建立高质量练习系统。", "cover-08.svg"),
    ("万历十五年", "黄仁宇", "历史", 36.00, "以一个年份观察明代社会的制度与人情。", "cover-09.svg"),
    ("Python编程从入门到实践", "埃里克·马瑟斯", "科技", 79.00, "适合初学者的项目式 Python 学习指南。", "cover-10.svg"),
    ("解忧杂货店", "东野圭吾", "小说", 45.00, "投进杂货店的烦恼信，会收到怎样的回答？", "cover-11.svg"),
    ("给青年的十二封信", "朱光潜", "成长", 32.00, "关于读书、做人和生活的诚恳叮咛。", "cover-12.svg"),
    ("史记", "司马迁", "历史", 59.00, "记录上古至西汉的纪传体通史，阅读中国历史的经典入口。", "book-13.svg"),
    ("资治通鉴", "司马光", "历史", 72.00, "以编年体串联重要历史事件，从兴衰成败中理解时代。", "book-14.svg"),
    ("明朝那些事儿", "当年明月", "历史", 49.90, "用轻松生动的方式讲述明朝二百多年的历史风云。", "book-15.svg"),
    ("人类群星闪耀时", "斯蒂芬·茨威格", "历史", 42.00, "聚焦历史转折时刻，书写改变世界的关键瞬间。", "book-16.svg"),
    ("三国演义", "罗贯中", "小说", 45.00, "英雄辈出、谋略纵横的中国古典长篇小说。", "book-17.svg"),
    ("红楼梦", "曹雪芹", "小说", 59.80, "以贾府兴衰展现人物命运与中国传统社会的复杂肌理。", "book-18.svg"),
    ("西游记", "吴承恩", "小说", 39.90, "唐僧师徒西天取经的奇幻冒险与成长旅程。", "book-19.svg"),
    ("围城", "钱钟书", "小说", 38.00, "以幽默锐利的笔触观察婚姻、知识分子与人生困境。", "book-20.svg"),
    ("活着", "余华", "小说", 32.00, "在时代变迁中讲述普通人的坚韧与生命力量。", "book-21.svg"),
    ("挪威的森林", "村上春树", "小说", 49.00, "关于青春、孤独、记忆与失去的细腻成长故事。", "book-22.svg"),
    ("额尔古纳河右岸", "迟子建", "文学", 45.00, "鄂温克族最后一位酋长女人的家族史诗与北方记忆。", "book-23.svg"),
    ("长安的荔枝", "马伯庸", "文学", 39.00, "小人物在盛唐长安完成一项看似不可能的任务。", "book-24.svg"),
    ("我们仨", "杨绛", "文学", 36.00, "记录一个家庭的相守、离别与温柔回忆。", "book-25.svg"),
    ("月亮与六便士", "毛姆", "文学", 36.00, "关于理想、艺术与人生选择的经典小说。", "book-26.svg"),
    ("乡土中国", "费孝通", "社科", 28.00, "从社会结构与日常生活理解中国乡土社会。", "book-27.svg"),
    ("枪炮、病菌与钢铁", "贾雷德·戴蒙德", "社科", 68.00, "解释不同文明发展路径差异的全球视野之作。", "book-28.svg"),
    ("思考，快与慢", "丹尼尔·卡尼曼", "社科", 69.00, "认识直觉与理性，理解判断和决策中的认知偏差。", "book-29.svg"),
    ("窗边的小豆豆", "黑柳彻子", "少儿", 32.00, "关于童真、教育和成长的温暖校园故事。", "book-30.svg"),
    ("夏洛的网", "E·B·怀特", "少儿", 28.00, "一只小猪和一只蜘蛛之间关于友谊与守护的故事。", "book-31.svg"),
    ("DK博物大百科", "英国DK出版社", "少儿", 128.00, "用精美图解带孩子探索自然、科学与人类文明。", "book-32.svg"),
    ("掌控习惯", "詹姆斯·克利尔", "成长", 49.00, "用微小而持续的改变建立长期有效的好习惯。", "book-33.svg"),
    ("高效能人士的七个习惯", "史蒂芬·柯维", "成长", 59.00, "从主动积极到协同合作，建立可持续的个人效能系统。", "book-34.svg"),
    ("被讨厌的勇气", "岸见一郎", "成长", 39.80, "通过哲学对话重新理解自由、关系与自我选择。", "book-35.svg"),
    ("小家，越住越大", "逯薇", "生活", 58.00, "用清晰方法解决收纳、动线与家庭空间规划问题。", "book-36.svg"),
    ("食帖：孤独的美食家", "食帖番组", "生活", 69.00, "从食物与城市出发，发现日常生活里的美好滋味。", "book-37.svg"),
    ("断舍离", "山下英子", "生活", 39.80, "整理物品，也整理与生活的关系，让空间重新呼吸。", "book-38.svg"),
    ("人工智能简史", "梅拉妮·米歇尔", "科技", 59.00, "从图灵到深度学习，通俗梳理人工智能的发展历程。", "book-39.svg"),
    ("算法图解", "巴尔加瓦", "科技", 45.00, "用直观案例学习搜索、排序、图和机器学习基础。", "book-40.svg"),
    ("运营之光", "黄有璨", "经管", 59.00, "系统拆解互联网产品运营的方法、策略与实践。", "book-41.svg"),
    ("从零开始做运营", "张亮", "经管", 45.00, "帮助新人建立用户、内容、活动和数据运营思维。", "book-42.svg"),
]


def get_db() -> sqlite3.Connection:
    """Return the request-local database connection."""
    if "db" not in g:
        Path(app.config["DATABASE"]).parent.mkdir(parents=True, exist_ok=True)
        g.db = sqlite3.connect(app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(_error: BaseException | None = None) -> None:
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db() -> None:
    """Create tables and seed books once on first startup."""
    db = get_db()
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS books (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            author TEXT NOT NULL,
            category TEXT NOT NULL,
            price REAL NOT NULL CHECK (price >= 0),
            description TEXT NOT NULL,
            cover TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS cart_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            book_id INTEGER NOT NULL REFERENCES books(id) ON DELETE CASCADE,
            quantity INTEGER NOT NULL DEFAULT 1 CHECK (quantity > 0),
            UNIQUE(user_id, book_id)
        );
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            total REAL NOT NULL CHECK (total >= 0),
            status TEXT NOT NULL DEFAULT '待发货',
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS order_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
            book_id INTEGER NOT NULL REFERENCES books(id),
            title TEXT NOT NULL,
            price REAL NOT NULL,
            quantity INTEGER NOT NULL
        );
        """
    )
    existing_titles = {
        row["title"] for row in db.execute("SELECT title FROM books").fetchall()
    }
    new_books = [book for book in SEED_BOOKS if book[0] not in existing_titles]
    if new_books:
        db.executemany(
            """
            INSERT INTO books (title, author, category, price, description, cover)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            new_books,
        )
    # Keep a cover selected by download_covers.py. This also makes startup safe
    # after a user has replaced one of the generated fallback covers.
    db.executemany(
        """
        UPDATE books SET cover = ?
        WHERE title = ? AND (cover IS NULL OR cover = '')
        """,
        [(book[5], book[0]) for book in SEED_BOOKS],
    )
    db.commit()


@app.context_processor
def inject_navigation() -> dict[str, object]:
    categories = get_db().execute(
        "SELECT DISTINCT category FROM books ORDER BY category"
    ).fetchall()
    cart_count = 0
    if session.get("user_id"):
        row = get_db().execute(
            "SELECT COALESCE(SUM(quantity), 0) AS count FROM cart_items WHERE user_id = ?",
            (session["user_id"],),
        ).fetchone()
        cart_count = row["count"]
    return {"nav_categories": categories, "cart_count": cart_count}


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            flash("请先登录后继续。", "warning")
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)

    return wrapped


@app.route("/")
def index():
    query = request.args.get("q", "").strip()
    category = request.args.get("category", "").strip()
    sql = "SELECT * FROM books WHERE 1=1"
    params: list[str] = []
    if query:
        sql += " AND (title LIKE ? OR author LIKE ? OR description LIKE ?)"
        wildcard = f"%{query}%"
        params.extend([wildcard, wildcard, wildcard])
    if category:
        sql += " AND category = ?"
        params.append(category)
    sql += " ORDER BY id"
    books = get_db().execute(sql, params).fetchall()
    featured = get_db().execute("SELECT * FROM books ORDER BY id LIMIT 4").fetchall()
    return render_template(
        "index.html",
        books=books,
        featured=featured,
        query=query,
        selected_category=category,
    )


@app.route("/book/<int:book_id>")
def book_detail(book_id: int):
    book = get_db().execute("SELECT * FROM books WHERE id = ?", (book_id,)).fetchone()
    if book is None:
        return render_template("404.html"), 404
    related = get_db().execute(
        "SELECT * FROM books WHERE category = ? AND id != ? ORDER BY id LIMIT 4",
        (book["category"], book_id),
    ).fetchall()
    return render_template("book_detail.html", book=book, related=related)


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")
        if not username or len(username) < 2:
            flash("用户名至少需要 2 个字符。", "error")
        elif len(password) < 6:
            flash("密码至少需要 6 个字符。", "error")
        elif password != confirm:
            flash("两次输入的密码不一致。", "error")
        else:
            db = get_db()
            try:
                cursor = db.execute(
                    "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                    (username, generate_password_hash(password)),
                )
                db.commit()
            except sqlite3.IntegrityError:
                flash("该用户名已经注册，请换一个。", "error")
            else:
                session.clear()
                session["user_id"] = cursor.lastrowid
                session["username"] = username
                flash("注册成功，欢迎来到书香集。", "success")
                return redirect(url_for("index"))
    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = get_db().execute(
            "SELECT * FROM users WHERE username = ?", (username,)
        ).fetchone()
        if user is None or not check_password_hash(user["password_hash"], password):
            flash("用户名或密码不正确。", "error")
        else:
            session.clear()
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            flash("登录成功。", "success")
            destination = request.args.get("next", "")
            return redirect(destination if destination.startswith("/") else url_for("index"))
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("你已安全退出。", "success")
    return redirect(url_for("index"))


@app.route("/cart")
@login_required
def cart():
    items = get_db().execute(
        """
        SELECT cart_items.id, cart_items.quantity, books.id AS book_id,
               books.title, books.author, books.price, books.cover,
               books.price * cart_items.quantity AS subtotal
        FROM cart_items JOIN books ON books.id = cart_items.book_id
        WHERE cart_items.user_id = ? ORDER BY cart_items.id
        """,
        (session["user_id"],),
    ).fetchall()
    total = sum(item["subtotal"] for item in items)
    return render_template("cart.html", items=items, total=total)


@app.route("/cart/add/<int:book_id>", methods=["GET", "POST"])
@login_required
def add_to_cart(book_id: int):
    book = get_db().execute("SELECT id FROM books WHERE id = ?", (book_id,)).fetchone()
    if book is None:
        return render_template("404.html"), 404
    db = get_db()
    db.execute(
        """
        INSERT INTO cart_items (user_id, book_id, quantity) VALUES (?, ?, 1)
        ON CONFLICT(user_id, book_id) DO UPDATE SET quantity = quantity + 1
        """,
        (session["user_id"], book_id),
    )
    db.commit()
    flash("已加入购物车。", "success")
    return redirect(request.referrer or url_for("cart"))


@app.post("/cart/update/<int:item_id>")
@login_required
def update_cart(item_id: int):
    try:
        quantity = int(request.form.get("quantity", "1"))
    except ValueError:
        quantity = 1
    quantity = max(1, min(quantity, 99))
    db = get_db()
    db.execute(
        "UPDATE cart_items SET quantity = ? WHERE id = ? AND user_id = ?",
        (quantity, item_id, session["user_id"]),
    )
    db.commit()
    flash("购物车已更新。", "success")
    return redirect(url_for("cart"))


@app.route("/cart/remove/<int:item_id>", methods=["GET", "POST"])
@login_required
def remove_from_cart(item_id: int):
    db = get_db()
    db.execute(
        "DELETE FROM cart_items WHERE id = ? AND user_id = ?",
        (item_id, session["user_id"]),
    )
    db.commit()
    flash("商品已从购物车移除。", "success")
    return redirect(url_for("cart"))


@app.route("/checkout", methods=["GET", "POST"])
@login_required
def checkout():
    db = get_db()
    items = db.execute(
        """
        SELECT cart_items.book_id, cart_items.quantity, books.title, books.price,
               books.price * cart_items.quantity AS subtotal
        FROM cart_items JOIN books ON books.id = cart_items.book_id
        WHERE cart_items.user_id = ?
        """,
        (session["user_id"],),
    ).fetchall()
    if not items:
        flash("购物车还是空的，先去挑几本书吧。", "warning")
        return redirect(url_for("index"))
    total = sum(item["subtotal"] for item in items)
    if request.method == "POST":
        order_cursor = db.execute(
            "INSERT INTO orders (user_id, total, status, created_at) VALUES (?, ?, ?, ?)",
            (session["user_id"], total, "待发货", datetime.now().strftime("%Y-%m-%d %H:%M")),
        )
        order_id = order_cursor.lastrowid
        db.executemany(
            """
            INSERT INTO order_items (order_id, book_id, title, price, quantity)
            VALUES (?, ?, ?, ?, ?)
            """,
            [
                (order_id, item["book_id"], item["title"], item["price"], item["quantity"])
                for item in items
            ],
        )
        db.execute("DELETE FROM cart_items WHERE user_id = ?", (session["user_id"],))
        db.commit()
        flash("订单创建成功，感谢你的购买！", "success")
        return redirect(url_for("order_detail", order_id=order_id))
    return render_template("checkout.html", items=items, total=total)


@app.route("/orders")
@login_required
def orders():
    user_orders = get_db().execute(
        """
        SELECT orders.*, COUNT(order_items.id) AS item_count
        FROM orders LEFT JOIN order_items ON order_items.order_id = orders.id
        WHERE orders.user_id = ?
        GROUP BY orders.id ORDER BY orders.id DESC
        """,
        (session["user_id"],),
    ).fetchall()
    return render_template("orders.html", orders=user_orders)


@app.route("/orders/<int:order_id>")
@login_required
def order_detail(order_id: int):
    order = get_db().execute(
        "SELECT * FROM orders WHERE id = ? AND user_id = ?",
        (order_id, session["user_id"]),
    ).fetchone()
    if order is None:
        return render_template("404.html"), 404
    items = get_db().execute(
        "SELECT * FROM order_items WHERE order_id = ? ORDER BY id", (order_id,)
    ).fetchall()
    return render_template("order_detail.html", order=order, items=items)


@app.errorhandler(404)
def not_found(_error):
    return render_template("404.html"), 404


with app.app_context():
    init_db()


if __name__ == "__main__":
    app.run(
        host=os.environ.get("HOST", "127.0.0.1"),
        port=int(os.environ.get("PORT", "5001")),
        debug=os.environ.get("FLASK_DEBUG", "").lower() == "1",
    )
