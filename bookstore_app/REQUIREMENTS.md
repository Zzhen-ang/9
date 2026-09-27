# 书香集 · 需求规格说明书（SRS）

> 文档版本：v1.0  
> 适用系统：`bookstore_app`  
> 文档目的：明确“书香集”网上书城的功能边界、数据需求、非功能要求与验收标准，作为开发、测试、部署的依据。

---

## 1. 引言

### 1.1 编写目的

本文档描述“书香集（Bookstore）”网上书城示例项目的完整需求规格，作为后续开发、接口测试、教学演示与验收的统一参考。

### 1.2 项目背景

- 项目位于 `bookstore_app/` 目录，是一套**完全独立运行**的 Flask + SQLite 网上书城示例，不读取或依赖外部 `books_design` 项目。
- 首次启动会自动创建 `bookstore.db`、建表、写入 42 本种子图书。
- 主要面向机器学习大实训教学场景，用于演示 Web 应用完整闭环（注册→浏览→购物车→订单）与接口测试方法。

### 1.3 术语与缩略语

| 术语 | 说明 |
| --- | --- |
| SRS | Software Requirements Specification，需求规格说明书 |
| FR / NFR | Functional Requirement / Non-Functional Requirement |
| 种子数据 | 启动时由 `init_db()` 自动写入的初始图书 |
| 购物车条目 | `cart_items` 表中的一行，代表用户对某本图书的一次持有 |
| 订单快照 | 下单时将图书 `title`、`price` 写入 `order_items`，避免后续图书信息变动影响历史订单 |
| Session | Flask 基于签名 Cookie 的服务端会话，本项目用于登录态 |

### 1.4 参考资料

- 项目源码：`bookstore_app/app.py`
- 项目说明：`bookstore_app/README.md`
- 接口文档：`bookstore_app/API_DOC.md`
- 依赖声明：`bookstore_app/requirements.txt`（`Flask>=3.0,<4.0`、`pytest>=7.0`）
- 封面下载脚本：`bookstore_app/download_covers.py`

---

## 2. 项目概述

### 2.1 产品定位

“书香集”是一个**轻量、自包含的网上书城 Demo**，覆盖账号体系、图书浏览、购物车、下单、订单管理的完整闭环，可作为 Web 课程、接口测试课程的实战案例。

### 2.2 用户角色

| 角色 | 描述 | 主要操作 |
| --- | --- | --- |
| 游客（未登录） | 未注册或未登录的访问者 | 浏览首页、搜索、查看详情、注册、登录 |
| 注册用户 | 已注册并登录的访问者 | 游客全部权限 + 购物车增删改、结算、订单查询 |
| 系统 | 服务端进程 | 自动建表、初始化种子图书、生成动态 SVG 封面 |

> 本系统不区分管理员角色，商品管理依赖种子数据与 `download_covers.py` 离线维护。

### 2.3 运行环境

| 项 | 要求 |
| --- | --- |
| 操作系统 | Windows / macOS / Linux 均可 |
| Python 版本 | Python 3.10+（已使用 `from __future__ import annotations`、PEP 604 `\|` 语法） |
| Web 框架 | Flask ≥ 3.0，< 4.0 |
| 数据库 | SQLite（单文件 `bookstore.db`，由 `BOOKSTORE_DATABASE` 环境变量覆盖） |
| 浏览器 | 任意现代浏览器（HTML + CSS + 少量原生 JS） |
| 网络 | 默认完全离线可运行；下载真实封面需联网调用 Open Library API |

### 2.4 假设与约束

- **AC-1**：服务仅在内网/本机运行，默认 `host=127.0.0.1`、`port=5001`，不直接暴露公网。
- **AC-2**：使用 SQLite 单文件，无并发写场景假设（开发/Demo 用途）。
- **AC-3**：未引入 CSRF Token、验证码、密码强度策略的高级防护。
- **AC-4**：登录态仅靠 Flask Session（签名 Cookie），不依赖外部缓存或数据库 Session 存储。
- **AC-5**：价格以“元”为单位，浮点存储（REAL）。
- **AC-6**：分类、书目数据由种子数据决定，运行期不提供后台编辑入口。

---

## 3. 功能需求

> 每条 FR 包含：编号、描述、输入、处理、输出、验收要点。

### FR-01 用户注册

- **描述**：游客可凭用户名 + 密码注册成为注册用户，注册成功自动登录。
- **输入**：表单字段
  - `username`：字符串，≥ 2 字符，去首尾空白。
  - `password`：字符串，≥ 6 字符。
  - `confirm_password`：字符串，必须与 `password` 一致。
- **处理**
  - 用户名查重 → `users.username UNIQUE`。
  - 密码通过 `werkzeug.security.generate_password_hash` 哈希存储。
  - 注册成功后 `session` 写入 `user_id`、`username`。
- **输出**
  - 成功：`302 → /`，flash 成功提示。
  - 失败：原页面 + flash 错误提示（用户名过短 / 密码过短 / 两次密码不一致 / 用户名重复）。
- **验收要点**
  - 用户名 `a` → 拒绝。
  - 密码 `12345` → 拒绝。
  - 两次密码不一致 → 拒绝。
  - 重复用户名 → 拒绝。
  - 合法输入 → 登录态生效，`session["user_id"]` 非空。

### FR-02 用户登录

- **描述**：已注册用户通过用户名 + 密码登录。
- **输入**：表单 `username`、`password`；可选 `?next=`（仅允许以 `/` 开头的相对路径）。
- **处理**：使用 `check_password_hash` 校验，成功写入 Session。
- **输出**
  - 成功：`302 → next 或 /`。
  - 失败：原页面 + flash `用户名或密码不正确。`
- **验收要点**
  - 不存在用户 / 错误密码均提示统一文案（防止账号枚举提示）。
  - `next=https://evil.com` 必须回退到 `/`，避免开放重定向。

### FR-03 用户退出

- **描述**：当前已登录用户点击退出，清空 Session。
- **处理**：`session.clear()`。
- **输出**：`302 → /`，flash 退出成功提示。
- **验收要点**：退出后访问 `/cart` 必须被重定向到登录页。

### FR-04 首页浏览

- **描述**：展示品牌栏、搜索框、分类导航、推荐横幅、图书网格。
- **输入**：可选 Query `q`、`category`。
- **处理**
  - 推荐横幅固定取前 4 本（按 `id` 升序）。
  - 列表按 `q`（书名/作者/简介模糊匹配）与 `category`（精确）筛选。
- **输出**：HTML 页面，包含 `books`、`featured`、`query`、`selected_category`。
- **验收要点**
  - 无任何筛选时，返回全部图书。
  - `q=历史` 同时命中书名/作者/简介中的任一字段。
  - `category` 非法值返回空列表（而非报错）。

### FR-05 图书详情

- **描述**：访问 `/book/<id>` 查看单本图书的完整信息。
- **输入**：路径参数 `book_id`。
- **输出**
  - 成功：详情页 + 同分类相关推荐 4 本（排除自己）。
  - 失败：`404.html`。
- **验收要点**：传 `id=0`、`id=99999` 等不存在 ID 必须返回 404。

### FR-06 购物车 · 加入

- **描述**：登录用户在图书详情页触发“加入购物车”。
- **输入**：路径参数 `book_id`。
- **处理**
  - 不存在图书 → 404。
  - 已存在 → 数量 `+1`；不存在 → 新增 `quantity=1`。
- **输出**：`302` 回 `referrer`（无则 `/cart`），flash 加入成功。
- **验收要点**：连续加入同一本书 3 次，购物车中数量应为 3。

### FR-07 购物车 · 查看

- **描述**：登录用户查看自己的购物车与合计金额。
- **输出**：HTML，包含 `items`（带 `subtotal = price * quantity`）和 `total`。
- **验收要点**：合计金额 = 所有 `subtotal` 之和，精度按 REAL 计算。

### FR-08 购物车 · 修改数量

- **描述**：登录用户在购物车页修改条目数量。
- **输入**：`POST /cart/update/<item_id>`，表单 `quantity`。
- **处理**：`int(...)` 转换失败取 `1`；最终 `clamp` 到 `[1, 99]`；仅更新当前用户的条目。
- **输出**：`302 → /cart`，flash 更新成功。
- **验收要点**
  - `quantity=0` → 实际写入 1。
  - `quantity=999` → 实际写入 99。
  - 非数字 → 写入 1。
  - 修改他人条目 → 无副作用（不影响）。

### FR-09 购物车 · 删除条目

- **描述**：登录用户删除某条购物车条目。
- **输入**：路径参数 `item_id`。
- **输出**：`302 → /cart`，flash 删除成功。
- **验收要点**：删除他人条目不报错且不影响他人数据。

### FR-10 结算下单

- **描述**：登录用户将购物车一次性生成为订单。
- **输入**：`POST /checkout`（无需额外字段）。
- **处理**
  - 购物车为空 → 跳转首页 + flash 警告。
  - 否则：开启事务，创建 `orders` 行 + 批量写 `order_items`（含 `title/price` 快照），清空购物车。
  - 订单 `status = '待发货'`，`created_at = YYYY-MM-DD HH:MM`。
- **输出**：`302 → /orders/<order_id>`，flash 下单成功。
- **验收要点**
  - 下单成功后购物车应清空。
  - 订单明细的 `title/price` 即使后续图书变动也保持原值。
  - 同一次结算订单总金额 = 购物车合计。

### FR-11 订单列表

- **描述**：登录用户查看自己的全部订单。
- **输出**：HTML，按订单 `id DESC` 排序，每行含 `item_count`。
- **验收要点**：仅展示当前用户订单，不展示他人订单。

### FR-12 订单详情

- **描述**：登录用户查看指定订单的明细。
- **输入**：路径参数 `order_id`。
- **输出**
  - 成功：详情页，含 `order` 与 `items`。
  - 不存在 / 不属于当前用户：`404.html`。
- **验收要点**：访问他人订单 ID 必须返回 404。

### FR-13 封面资源

- **描述**：通过 `/covers/<filename>` 提供图书封面。
- **处理**
  - 文件名匹配 `book-<id>.svg` 时，按 `id` 在数据库中查找，动态生成 SVG（含分类、书名、作者、底色等）。
  - 其他文件名走 `static/covers/` 静态目录（支持 JPG/PNG/SVG）。
- **输出**
  - 成功：`200`，对应 MIME。
  - 失败：`404`。
- **验收要点**：SVG 内容中书名、作者、分类经 `html.escape` 转义，防止 XSS。

### FR-14 种子数据初始化

- **描述**：服务启动时自动建表并写入 42 本示例图书。
- **处理**
  - 创建 5 张表（`users / books / cart_items / orders / order_items`），启用外键约束 `PRAGMA foreign_keys = ON`。
  - 按 `title` 去重插入新书。
  - 补齐空封面字段为种子配置中的封面名。
- **输出**：可立即访问首页看到完整书目。
- **验收要点**：重复启动不会重复插入已有图书。

---

## 4. 非功能需求

### NFR-01 性能

- 启动时间：单实例启动（含建表 + 种子插入）应在 3 秒内完成。
- 单次请求响应：本地环境下 HTML 路由 P95 应低于 200ms。
- 数据库：单 SQLite 文件，并发读 OK，写入限于下单/购物车变更，量级在 Demo 范围。

### NFR-02 安全

| 项 | 要求 |
| --- | --- |
| 密码存储 | 必须哈希（`werkzeug.security`），禁止明文存储 |
| Session 密钥 | 默认仅用于开发，生产需通过 `BOOKSTORE_SECRET_KEY` 注入强随机密钥 |
| XSS | 动态 SVG 中书名/作者/分类必须经过 `html.escape` 转义 |
| 路径遍历 | 封面路由使用 `send_from_directory`，禁止 `../` 越权 |
| 开放重定向 | `/login` 的 `next` 参数必须以 `/` 开头才允许跳转 |
| CSRF | **未实现**（教学场景有意保留，便于演示风险） |
| SQL 注入 | 使用参数化 SQL（`?` 占位符），禁止拼接字符串 |

### NFR-03 可用性

- 表单校验错误必须给出中文提示（`flash`），不允许仅返回 HTTP 状态码。
- 所有写操作成功后跳转到合理页面（购物车 / 订单详情 / 首页）。
- 顶部导航展示登录态与购物车数量徽标，未登录购物车数量为 0。

### NFR-04 可维护性

- 路由集中在 `app.py`，职责清晰：模板渲染 + SQL 操作。
- 种子数据以 `SEED_BOOKS` 常量声明，便于增删。
- 表结构集中在 `init_db()` 中，迁移靠重建脚本/Drop 表。
- 静态资源（封面、JS、CSS）按目录归类。

### NFR-05 兼容性

- Python 3.10+（`int | None`、`from __future__ import annotations`）。
- Flask 3.x，Werkzeug 与 Flask 版本配套。
- 浏览器：Chrome / Edge / Firefox / Safari 当前主流版本。

### NFR-06 数据完整性

| 表 | 关键约束 |
| --- | --- |
| `users` | `username` UNIQUE |
| `books` | `price >= 0` |
| `cart_items` | `quantity > 0`，`(user_id, book_id)` 联合唯一 |
| `orders` | `total >= 0` |
| `order_items` | 外键引用 `orders / books`，删除订单时级联清理 |

外键：`PRAGMA foreign_keys = ON`，删除用户会级联清理其购物车和订单。

---

## 5. 数据需求

详细字段参见 API 文档 §3，关键要点：

- 5 张表 + 启用外键约束。
- 价格使用 REAL（浮点），Demo 场景可接受；如需严格金额，应改为整数“分”。
- `order_items` 必须存 `title`、`price` 快照，避免订单展示受图书信息变更影响。
- 启动时若数据库目录不存在需自动创建（`Path(parent).mkdir(parents=True, exist_ok=True)`）。

---

## 6. 接口需求

详细路由、参数、响应参见 [`API_DOC.md`](./API_DOC.md)。本节列出约束性结论：

- 所有写操作（购物车变更、下单）必须鉴权（`@login_required`）。
- 表单提交走 `application/x-www-form-urlencoded`，便于 Postman 直接测试。
- 重定向目标
  - 登录后 → `next` 或 `/`。
  - 加购物车 → `referrer` 或 `/cart`。
  - 购物车变更 → `/cart`。
  - 下单 → `/orders/<order_id>`。
  - 退出 → `/`。

---

## 7. 验收标准（Acceptance Criteria）

### 7.1 功能验收

| 编号 | 场景 | 预期 |
| --- | --- | --- |
| AC-F01 | 启动 `python app.py` | 自动创建 `bookstore.db`，首页可见 42 本书 |
| AC-F02 | 注册 `u1 / pw123456` | 自动登录并跳首页，导航显示用户名 |
| AC-F03 | 退出后访问 `/cart` | 跳转 `/login?next=/cart` |
| AC-F04 | 登录 `u1 / 错误密码` | flash 用户名或密码不正确 |
| AC-F05 | 加入同一本书 3 次 | 购物车数量显示 3 |
| AC-F06 | 修改购物车数量为 `0`、`999`、`abc` | 分别落库为 `1`、`99`、`1` |
| AC-F07 | 结算空购物车 | flash 警告并跳首页，不下单 |
| AC-F08 | 正常结算 | 生成订单 + 明细 + 清空购物车，跳订单详情 |
| AC-F09 | 访问他人订单 ID | 返回 404 |
| AC-F10 | `/book/0` / `/book/99999` | 返回 404 |
| AC-F11 | `/covers/book-13.svg` | 返回 200 + SVG，含对应书名/作者/分类 |
| AC-F12 | `/covers/../app.py` | 404 或被路径遍历保护阻断 |

### 7.2 安全验收

| 编号 | 场景 | 预期 |
| --- | --- | --- |
| AC-S01 | 检查 `bookstore.db` 中 `password_hash` | 应为 `pbkdf2:`/`scrypt:` 开头哈希，非明文 |
| AC-S02 | `?next=https://evil.com` | 登录后跳 `/` |
| AC-S03 | 动态 SVG 中书名含 `<script>` | 应被转义为 `&lt;script&gt;`，无脚本执行 |
| AC-S04 | 退出后再访问 `/orders` | 跳转登录页 |

### 7.3 可维护性验收

| 编号 | 场景 | 预期 |
| --- | --- | --- |
| AC-M01 | 重复启动服务 | 不重复插入种子图书 |
| AC-M02 | 删除 `bookstore.db` 后重启 | 自动重建并恢复 42 本种子图书 |
| AC-M03 | 关闭网络运行 `download_covers.py` | 正常结束，不影响 `python app.py` 启动 |

---

## 8. 附录

### 8.1 种子图书分类

`SEED_BOOKS` 中出现的分类：

`文学`、`社科`、`少儿`、`生活`、`经管`、`成长`、`历史`、`科技`、`小说`

### 8.2 种子图书数量

42 本。

### 8.3 文件清单

```
bookstore_app/
├── app.py                 # 主应用（路由、SQL、模板渲染）
├── download_covers.py     # 可选：下载真实封面
├── requirements.txt       # Flask、pytest
├── bookstore.db           # 运行期自动创建
├── README.md
├── API_DOC.md             # 接口文档
├── REQUIREMENTS.md        # 本文档
├── cover-download-results.jsonl   # 运行期生成
├── cover-01.svg                   # 根目录封面（兜底）
├── static/
│   ├── css/style.css
│   ├── js/app.js
│   └── covers/             # 静态封面（含 real/ 子目录）
└── templates/
    ├── base.html
    ├── index.html
    ├── book_detail.html
    ├── login.html
    ├── register.html
    ├── cart.html
    ├── checkout.html
    ├── orders.html
    ├── order_detail.html
    └── 404.html
```

### 8.4 变更记录

| 版本 | 日期 | 变更说明 |
| --- | --- | --- |
| v1.0 | 2026-09-21 | 初版，基于 `app.py` 当前实现整理 |