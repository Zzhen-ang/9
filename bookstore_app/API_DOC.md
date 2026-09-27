# 书香集 Bookstore 接口文档

> 适用代码版本：`bookstore_app/app.py`
> 技术栈：Flask + SQLite + Jinja2 模板 + Flask Session（基于 Cookie）
> 文档定位：描述项目暴露的全部 HTTP 接口，包含路径、方法、入参、权限、响应，便于 Postman / 接口测试使用。

---

## 1. 通用约定

| 项 | 说明 |
| --- | --- |
| 基础地址 | `http://<host>:<port>`，默认 `http://127.0.0.1:5001`（可通过环境变量 `HOST`、`PORT` 修改） |
| 数据格式 | 请求体使用 `application/x-www-form-urlencoded`（HTML 表单提交）；响应统一为 `text/html`（Jinja 渲染页面）或 `image/svg+xml` |
| 鉴权方式 | 基于 Flask `session`（Cookie，名称默认 `session`）。登录成功后服务端写入 `user_id`、`username`；会话密钥由环境变量 `BOOKSTORE_SECRET_KEY` 控制 |
| 业务消息 | 通过 Flask `flash()` 机制在前端模板中渲染，分类包括 `success` / `warning` / `error` |
| 鉴权装饰器 | `@login_required`：未登录请求会 `302` 跳转 `/login?next=<原路径>`，并 `flash` 提示“请先登录后继续。” |
| 统一异常 | 访问不存在的资源（图书、订单）渲染 `404.html`，HTTP 状态码 `404` |

### 1.1 路由清单

| # | Method | Path | 鉴权 | 描述 |
| --- | --- | --- | --- | --- |
| 1 | GET | `/covers/<path:filename>` | 否 | 提供图书封面（自动生成 SVG 或读取静态文件） |
| 2 | GET | `/` | 否 | 首页：图书列表，支持搜索 + 分类筛选 |
| 3 | GET | `/book/<int:book_id>` | 否 | 图书详情页 |
| 4 | GET / POST | `/register` | 否 | 用户注册（POST 提交） |
| 5 | GET / POST | `/login` | 否 | 用户登录（POST 提交） |
| 6 | GET | `/logout` | 否 | 退出登录 |
| 7 | GET | `/cart` | 必需 | 查看购物车 |
| 8 | GET / POST | `/cart/add/<int:book_id>` | 必需 | 加入购物车 |
| 9 | POST | `/cart/update/<int:item_id>` | 必需 | 修改购物车条目数量 |
| 10 | GET / POST | `/cart/remove/<int:item_id>` | 必需 | 删除购物车条目 |
| 11 | GET / POST | `/checkout` | 必需 | 结算（下单） |
| 12 | GET | `/orders` | 必需 | 我的订单列表 |
| 13 | GET | `/orders/<int:order_id>` | 必需 | 订单详情 |

---

## 2. 详细接口说明

> 标注 🔒 的接口必须在已登录状态下访问，未登录会 `302 → /login?next=<path>`。

---

### 2.1 `GET /covers/<filename>`

提供图书封面资源。

- **路径参数**
  - `filename`：封面文件名。支持两类：
    - 自动生成的 SVG：`book-<id>.svg`（如 `book-13.svg`），服务端会根据 `id` 在 `books` 表中查到 `title/author/category`，即时渲染 SVG 字符串返回。
    - 静态文件：`static/covers/` 目录下的其他文件（已下载的真实封面图或预生成 SVG），由 Flask `send_from_directory` 返回。
- **响应**
  - `200 image/svg+xml` 或 `200 image/*`：封面二进制内容。
  - `404`：当 `book-<id>.svg` 在数据库中找不到对应图书，或静态文件不存在时。
- **安全**
  - 使用 `send_from_directory`，受 Flask 路径遍历保护。
  - SVG 文本通过 `html.escape()` 转义后拼接，避免注入。

---

### 2.2 `GET /`

首页：图书列表 + 顶部轮播“精选 4 本”。

- **Query 参数**
  | 名称 | 类型 | 必填 | 说明 |
  | --- | --- | --- | --- |
  | `q` | string | 否 | 关键字搜索，对 `title` / `author` / `description` 做 `LIKE %q%` 模糊匹配 |
  | `category` | string | 否 | 分类精确匹配，例如 `文学` / `历史` |
- **响应**
  - `200 text/html`：渲染 `templates/index.html`，包含：
    - `books`：筛选后的图书列表（按 `id` 升序）
    - `featured`：精选 4 本（按 `id` 升序前 4 本）
    - `query`、`selected_category`：回显输入
- **示例**
  ```
  GET /?q=历史&category=历史
  ```

---

### 2.3 `GET /book/<book_id>`

图书详情页。

- **路径参数**
  - `book_id`：整数图书 ID（`int` 路由转换器会自动校验）。
- **响应**
  - `200 text/html`：渲染 `templates/book_detail.html`，字段 `book`（图书详情）、`related`（同分类下排除自身的 4 本）。
  - `404`：图书不存在，渲染 `templates/404.html`。
- **示例**
  ```
  GET /book/13
  ```

---

### 2.4 `GET / POST /register`

用户注册。GET 返回注册表单页；POST 处理表单。

- **POST Form 参数**
  | 名称 | 类型 | 必填 | 校验 | 说明 |
  | --- | --- | --- | --- | --- |
  | `username` | string | 是 | ≥ 2 字符，去首尾空白 | 用户名，唯一 |
  | `password` | string | 是 | ≥ 6 字符 | 明文密码，服务端使用 `werkzeug.security.generate_password_hash` 哈希存储 |
  | `confirm_password` | string | 是 | 必须与 `password` 完全一致 | 二次输入 |
- **响应**
  - `200`：注册失败时回写 `register.html`，并通过 `flash` 输出错误：
    - 用户名 < 2 字符：`用户名至少需要 2 个字符。`
    - 密码 < 6 字符：`密码至少需要 6 个字符。`
    - 两次密码不一致：`两次输入的密码不一致。`
    - 用户名重复（SQLite `IntegrityError`）：`该用户名已经注册，请换一个。`
  - `302 → /`：注册成功，自动登录并写入 `session["user_id"]` / `session["username"]`，`flash` `注册成功，欢迎来到书香集。`
- **Postman 测试注意**
  - 勾选 `Follow redirects` 观察自动登录后的 `Set-Cookie: session=...`，后续请求需复用该 Cookie。

---

### 2.5 `GET / POST /login`

用户登录。GET 返回登录表单页；POST 处理表单。

- **POST Form 参数**
  | 名称 | 类型 | 必填 | 说明 |
  | --- | --- | --- | --- |
  | `username` | string | 是 | 用户名，去首尾空白 |
  | `password` | string | 是 | 明文密码 |
- **可选 Query 参数**
  - `next`：登录成功后跳转目标（仅允许以 `/` 开头的相对路径，避免开放重定向）。
- **响应**
  - `200`：登录失败回写 `login.html`，`flash` `用户名或密码不正确。`
  - `302`：
    - 默认 → `/`
    - `next` 合法 → `next` 指定路径
    - `flash` `登录成功。`
- **服务端动作**
  - `session.clear()` 后写入 `user_id`、`username`。
  - 使用 `werkzeug.security.check_password_hash` 校验。

---

### 2.6 `GET /logout`

退出登录。

- **响应**
  - `302 → /`，`session.clear()`，`flash` `你已安全退出。`

---

### 2.7 🔒 `GET /cart`

查看当前用户的购物车。

- **响应**
  - `200 text/html`：渲染 `templates/cart.html`，字段：
    - `items`：列表，每项含 `id`（cart_items.id）、`book_id`、`title`、`author`、`price`、`cover`、`subtotal = price * quantity`
    - `total`：所有 `subtotal` 之和（Python 端计算，未持久化）
- **依赖**
  - 需要 `session["user_id"]`。

---

### 2.8 🔒 `GET|POST /cart/add/<book_id>`

将指定图书加入购物车，数量 +1。

- **路径参数**
  - `book_id`：图书 ID。
- **请求体**
  - GET/POST 均可，服务端不读取 form，只看 `request.referrer`。
- **响应**
  - `302`：成功加入后跳回 `request.referrer`（来源页），无来源则跳 `/cart`，`flash` `已加入购物车。`
  - `404`：图书不存在，渲染 `404.html`。
- **数据库行为**
  - `INSERT INTO cart_items ... ON CONFLICT(user_id, book_id) DO UPDATE SET quantity = quantity + 1`，即对同一 (user, book) 自动累加。
  - `quantity` 默认 `1`，有上限吗？SQL 层 `CHECK (quantity > 0)`，但此处累加不做上限校验（理论可累加到 99 以上）。

---

### 2.9 🔒 `POST /cart/update/<item_id>`

修改购物车条目数量。

- **路径参数**
  - `item_id`：购物车条目 ID。
- **Form 参数**
  | 名称 | 类型 | 必填 | 说明 |
  | --- | --- | --- | --- |
  | `quantity` | string/int | 是 | 服务端 `int(...)`，转换失败则取 `1`；最终 `clamp` 到 `[1, 99]` |
- **响应**
  - `302 → /cart`，`flash` `购物车已更新。`
  - 仅当 `item.user_id == session["user_id"]` 才执行 `UPDATE`，否则相当于空操作（不影响他人数据，但前端无差异提示）。

---

### 2.10 🔒 `GET|POST /cart/remove/<item_id>`

删除购物车条目。

- **路径参数**
  - `item_id`：购物车条目 ID。
- **响应**
  - `302 → /cart`，`flash` `商品已从购物车移除。`
  - 仅删除 `user_id` 匹配的记录。

---

### 2.11 🔒 `GET|POST /checkout`

结算页（GET）/ 下单（POST）。

- **GET 行为**
  - 读取当前用户购物车；为空时 `flash` `购物车还是空的，先去挑几本书吧。` 并 `302 → /`。
  - 否则渲染 `templates/checkout.html`，展示 `items` 与 `total`。
- **POST 行为**
  - 同样先取购物车；为空则 `302 → /`。
  - 计算 `total`，开启事务：
    1. `INSERT INTO orders (user_id, total, status, created_at) VALUES (?, ?, '待发货', '<YYYY-MM-DD HH:MM>')`，得到 `order_id`。
    2. `INSERT INTO order_items` 逐行写入订单明细（含 `book_id, title, price, quantity`，便于下单后保留历史快照，即使图书信息后续变更也不影响订单展示）。
    3. `DELETE FROM cart_items WHERE user_id = ?` 清空购物车。
  - `302 → /orders/<order_id>`，`flash` `订单创建成功，感谢你的购买！`

> 注意：POST 不需要额外表单字段，结算页确认即下单。

---

### 2.12 🔒 `GET /orders`

当前用户订单列表。

- **响应**
  - `200 text/html`：渲染 `templates/orders.html`，`orders` 字段每项包含：
    - `id`、`user_id`、`total`、`status`、`created_at`
    - `item_count`：通过 `LEFT JOIN order_items` + `COUNT()` 得到
  - 排序：`orders.id DESC`。

---

### 2.13 🔒 `GET /orders/<order_id>`

订单详情。

- **路径参数**
  - `order_id`：订单 ID。
- **响应**
  - `200 text/html`：渲染 `templates/order_detail.html`，字段：
    - `order`：订单主体
    - `items`：订单明细列表，按 `order_items.id` 升序
  - `404`：订单不存在或不属于当前用户，渲染 `404.html`。

---

## 3. 数据模型

> 实际为 SQLite 表，由 `init_db()` 自动创建并预置图书种子数据。

### 3.1 `users`

| 列 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `id` | INTEGER | PK, AUTOINCREMENT | 用户 ID |
| `username` | TEXT | NOT NULL, UNIQUE | 用户名 |
| `password_hash` | TEXT | NOT NULL | `werkzeug.security.generate_password_hash` 输出 |
| `created_at` | TEXT | NOT NULL, DEFAULT `CURRENT_TIMESTAMP` | 注册时间 |

### 3.2 `books`

| 列 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `id` | INTEGER | PK, AUTOINCREMENT | 图书 ID |
| `title` | TEXT | NOT NULL | 书名 |
| `author` | TEXT | NOT NULL | 作者 |
| `category` | TEXT | NOT NULL | 分类 |
| `price` | REAL | NOT NULL, CHECK ≥ 0 | 价格（元） |
| `description` | TEXT | NOT NULL | 简介 |
| `cover` | TEXT | NOT NULL | 封面文件名（指向 `static/covers/`，或 `book-<id>.svg` 走动态） |

### 3.3 `cart_items`

| 列 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `id` | INTEGER | PK, AUTOINCREMENT | 条目 ID |
| `user_id` | INTEGER | FK → `users.id` ON DELETE CASCADE | 所属用户 |
| `book_id` | INTEGER | FK → `books.id` ON DELETE CASCADE | 图书 |
| `quantity` | INTEGER | NOT NULL, DEFAULT 1, CHECK > 0 | 数量 |
| 联合唯一 | `(user_id, book_id)` | | 同一用户同一图书只占一行 |

### 3.4 `orders`

| 列 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `id` | INTEGER | PK, AUTOINCREMENT | 订单 ID |
| `user_id` | INTEGER | FK → `users.id` ON DELETE CASCADE | 用户 |
| `total` | REAL | NOT NULL, CHECK ≥ 0 | 订单总金额 |
| `status` | TEXT | NOT NULL, DEFAULT `待发货` | 订单状态 |
| `created_at` | TEXT | NOT NULL | 下单时间，格式 `YYYY-MM-DD HH:MM` |

### 3.5 `order_items`

| 列 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `id` | INTEGER | PK, AUTOINCREMENT | 明细 ID |
| `order_id` | INTEGER | FK → `orders.id` ON DELETE CASCADE | 所属订单 |
| `book_id` | INTEGER | FK → `books.id` | 图书 |
| `title` | TEXT | NOT NULL | 下单时书名快照 |
| `price` | REAL | NOT NULL | 下单时单价快照 |
| `quantity` | INTEGER | NOT NULL | 数量 |

---

## 4. 错误与状态码

| 场景 | HTTP | 行为 |
| --- | --- | --- |
| 资源不存在（图书/订单） | 404 | 渲染 `templates/404.html` |
| 表单校验失败 | 200 | 回写原页面 + `flash` 错误 |
| 用户名重复 | 200 | 回写注册页 + `flash` |
| 登录失败 | 200 | 回写登录页 + `flash` |
| 未登录访问鉴权页 | 302 | 跳转 `/login?next=<path>` + `flash` 提示 |
| 添加不存在图书到购物车 | 404 | 渲染 `404.html` |
| 退出成功 | 302 | 跳转 `/` + `flash` |

---

## 5. Postman 测试指引

1. **环境变量**
   - `base_url = http://127.0.0.1:5001`
   - 启动服务：`python app.py`（默认监听 `5001` 端口）。
3. **Cookie 复用**
   - 注册或登录成功后，在 Postman 中勾选“自动跟随重定向”，并将响应 Cookie 保存到 Cookie Manager，后续鉴权接口同源发送即可。
4. **典型测试序列**
   1. `POST /register` 创建账号 → 检查 `302 → /` 与 `session` Cookie。
   2. `GET /` 验证首页可访问且含登录态信息。
   3. `GET /book/1` → `POST /cart/add/1` → `GET /cart` 验证条目出现。
   4. `POST /cart/update/<id>` 调整数量 → `GET /cart` 复核。
   5. `POST /checkout` → `GET /orders/<order_id>` 验证订单生成、购物车清空。
5. **CSRF 提示**
   - 项目未启用 CSRF 防护（仅靠同源 + Session Cookie）。如需模拟跨站请求，把 `Referer` 改掉即可通过，可用于课堂演示“无 CSRF 防护的风险”。

---

## 6. 附录：种子图书覆盖的分类

`SEED_BOOKS` 中出现的分类（可作为 `category` 入参的合法值示例）：

`文学`、`社科`、`少儿`、`生活`、`经管`、`成长`、`历史`、`科技`、`小说`

> 分类以数据库实际值为准；`init_db()` 在每次启动时按 `title` 去重，不会重复插入。