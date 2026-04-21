# ipoipo.cn 网站数据结构与爬虫参考文档

> 基于代码库逆向分析得出，非官方文档。最后更新：2026-04-22

---

## 1. 网站概览

**ipoipo.cn** 是一个 IPO 行业报告聚合网站，使用 Z-Blog（或类似 CMS）构建。报告以 ZIP 压缩包形式提供下载，ZIP 内包含 PDF/Word/PPT/Excel 等文档。

---

## 2. URL 模式

### 2.1 分类页（Tags 页）

| 类型 | URL 模式 | 示例 |
|------|----------|------|
| 分类首页（第1页） | `https://ipoipo.cn/tags-{id}.html` | `https://ipoipo.cn/tags-85.html` |
| 分类分页（第N页） | `https://ipoipo.cn/tags-{id}_{N}.html` | `https://ipoipo.cn/tags-85_2.html` |

- **注意**：第1页用 `tags-{id}.html`，第2页起用 `tags-{id}_{N}.html`（下划线分隔）
- 页面为纯 HTML，无 API 接口

### 2.2 文章详情页

| 类型 | URL 模式 | 示例 |
|------|----------|------|
| 文章页 | `https://ipoipo.cn/post/{post_id}.html` | `https://ipoipo.cn/post/26028.html` |

### 2.3 下载页（关键！）

| 类型 | URL 模式 | 示例 |
|------|----------|------|
| 下载页 | `https://ipoipo.cn/download/{post_id}.html` | `https://ipoipo.cn/download/26028.html` |

- 从文章页 URL 到下载页 URL 的转换：将 `/post/` 替换为 `/download/`
- 下载页包含 ZIP 文件的实际下载链接

### 2.4 ZIP 文件下载

| 类型 | URL 模式 | 示例 |
|------|----------|------|
| ZIP 直链 | `https://ipo.ai-tag.cn/{year}/{month}/{filename}.zip` | `https://ipo.ai-tag.cn/2025/12/202512021157134086066.zip` |

- **关键**：ZIP 文件托管在 `ipo.ai-tag.cn` 域名（阿里云 OSS/CDN），而非 `ipoipo.cn`
- URL 中包含时间戳：`YYYYMMDDHHmmss{随机数}.zip`
- 直链 **不能直接访问**，必须设置正确的 Referer（见下方防盗链部分）

---

## 3. 分类体系

### 3.1 完整分类列表（39个）

| ID | 分类名称 | 标签页 URL |
|----|---------|-----------|
| 70 | TMT行业 | `tags-70.html` |
| 53 | 医药医疗器械行业 | `tags-53.html` |
| 59 | 金融行业 | `tags-59.html` |
| 69 | 新能源及电力行业 | `tags-69.html` |
| 14 | 电子行业 | `tags-14.html` |
| 10 | 智能制造行业 | `tags-10.html` |
| 79 | 汽车行业 | `tags-79.html` |
| 67 | 地产及旅游行业 | `tags-67.html` |
| 34 | 经济报告 | `tags-34.html` |
| 24 | 新材料及矿产报告 | `tags-24.html` |
| 61 | 电商及销售报告 | `tags-61.html` |
| 62 | 消费者及人群研究报告 | `tags-62.html` |
| 33 | 食品饮料酒水行业 | `tags-33.html` |
| 11 | 大消费报告 | `tags-11.html` |
| **85** | **人工智能AI行业** | `tags-85.html` |
| 60 | 化工行业 | `tags-60.html` |
| 63 | 物流行业 | `tags-63.html` |
| **7** | **教育行业** | `tags-7.html` |
| 23 | 云计算行业 | `tags-23.html` |
| 56 | 节能环保行业 | `tags-56.html` |
| 64 | 农林牧渔行业 | `tags-64.html` |
| 73 | 餐饮业报告 | `tags-73.html` |
| 74 | 化妆品行业 | `tags-74.html` |
| 25 | 体育及用品行业 | `tags-25.html` |
| 68 | 军工行业 | `tags-68.html` |
| 76 | 光电行业 | `tags-76.html` |
| 39 | 纺织服装行业 | `tags-39.html` |
| 86 | 航天通讯行业 | `tags-86.html` |
| 77 | 安全监控行业 | `tags-77.html` |
| 66 | 服务业报告 | `tags-66.html` |
| 84 | 宠物行业 | `tags-84.html` |
| 75 | 奢侈品及珠宝报告 | `tags-75.html` |
| 72 | 经验干货 | `tags-72.html` |
| 83 | 母婴行业 | `tags-83.html` |
| 80 | 检测行业报告 | `tags-80.html` |
| 82 | 共享经济报告 | `tags-82.html` |
| 88 | 新基建报告 | `tags-88.html` |
| 54 | 博彩行业报告 | `tags-54.html` |

> **代码中仅启用 85（人工智能AI）和 7（教育行业）**，其余分类在 `settings.py` 中被注释掉。

### 3.2 分类 ID 规律

- ID 为数字字符串，无固定范围（7~88）
- ID 与分类名称的映射关系固定，但网站可能新增分类

---

## 4. 页面 HTML 结构

### 4.1 分类列表页 — 报告卡片

每个报告以 `<div class="wapost card">` 卡片形式呈现：

```html
<div class="wapost card">
    <h2 class="multi-ellipsis">
        <a href="https://ipoipo.cn/post/26028.html" title="报告标题">报告标题</a>
    </h2>
    <p class="img">
        <a href="..." target="_blank">
            <img class="img-cover br" src="缩略图URL" title="...">
        </a>
    </p>
    <p class="text">报告简介文本...</p>
    <div class="count">
        <span class="view-num"><i class="fa fa-eye"></i>44</span>
        <span class="edit"><i class="fa fa-clock-o"></i>2025-12-22</span>
    </div>
</div>
```

**可提取字段**：
- `post_id`：从 `<a href>` 中用正则 `/post/(\d+)\.html` 提取
- `title`：`<a>` 标签的 `title` 属性
- `detail_url`：`<a>` 标签的 `href` 属性
- `thumbnail_url`：`<img class="img-cover">` 的 `src` 属性
- `description`：`<p class="text">` 的文本
- `view_count`：`<span class="view-num">` 中的数字
- `publish_date`：`<span class="edit">` 中的日期文本

### 4.2 下载页 — ZIP 链接

下载页包含一个指向 ZIP 文件的 `<a>` 标签，典型形式：

```html
<a style="font-size: 12px; color: rgb(0, 102, 204);"
   href="https://ipo.ai-tag.cn/2025/12/202512021157134086066.zip"
   data-darkreader-inline-color="">
   2025中国地方公共数据开放利用报告.zip
</a>
```

ZIP 链接提取策略（按优先级）：
1. 查找 `href` 以 `.zip` 结尾的 `<a>` 标签
2. 查找带有 `font-size` + `color` 样式的 `<a>` 标签
3. 查找文本包含 `.zip` 的 `<a>` 标签
4. 用正则匹配 HTML 中所有 `http...zip` URL

---

## 5. 数据库结构（SQLite）

### 5.1 表：`categories`

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER PK | 自增主键 |
| category_id | TEXT UNIQUE | 分类ID（如 "85"） |
| category_name | TEXT | 分类名称 |
| url | TEXT | 分类页URL |
| created_at | TIMESTAMP | 创建时间 |

### 5.2 表：`reports`

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER PK | 自增主键 |
| category_id | TEXT FK | 关联分类ID |
| post_id | TEXT UNIQUE | 文章ID |
| title | TEXT | 报告标题 |
| detail_url | TEXT | 文章详情页URL |
| download_url | TEXT | ZIP下载链接 |
| thumbnail_url | TEXT | 缩略图URL |
| view_count | INTEGER | 浏览量 |
| publish_date | TEXT | 发布日期 |
| status | TEXT | 状态：`pending`/`ready`/`downloaded`/`failed`/`no_download_url` |
| local_path | TEXT | 本地文件路径 |
| created_at | TIMESTAMP | 创建时间 |
| updated_at | TIMESTAMP | 更新时间 |

### 5.3 表：`downloads`

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER PK | 自增主键 |
| post_id | TEXT FK | 关联文章ID |
| zip_url | TEXT | ZIP文件URL |
| file_name | TEXT | 文件名 |
| file_path | TEXT | 本地保存路径 |
| file_size | INTEGER | 文件大小（字节） |
| status | TEXT | 下载状态 |
| download_attempts | INTEGER | 尝试次数 |
| error_message | TEXT | 错误信息 |
| started_at / completed_at / created_at | TIMESTAMP | 时间戳 |

### 5.4 表：`extractions`

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER PK | 自增主键 |
| download_id | INTEGER FK | 关联下载记录 |
| extract_path | TEXT | 解压路径 |
| files_count | INTEGER | 文件数 |
| status | TEXT | 解压状态 |
| extracted_at / created_at | TIMESTAMP | 时间戳 |

### 5.5 状态流转

```
pending → ready（获取到download_url）→ downloaded / failed / no_download_url
failed → ready（通过 --retry 重置）
```

---

## 6. 爬虫 Gotchas

### 6.1 Tengine CDN 防盗链（最重要！）

**现象**：直接请求 ZIP URL 返回 `403 Forbidden`，响应头含 `X-Tengine-Error`。

**根因**：阿里云 Tengine CDN 使用 Referer ACL 白名单，仅允许来自 `ipoipo.cn` 域名的请求。

**解决方案**（三步缺一不可）：
1. 使用 `requests.Session()` 保持 cookies
2. 先访问下载页 `https://ipoipo.cn/download/{post_id}.html` 建立会话
3. 下载 ZIP 时设置 `Referer: https://ipoipo.cn/download/{post_id}.html`

**关键细节**：
- Referer 必须是 `ipoipo.cn` 域名，**不能是 `ipo.ai-tag.cn`**（ZIP 所在域名）
- 空 Referer 也会返回 403
- 错误的 Referer（如 `example.com`）也会返回 403
- 验证：访问下载页后等待 ~1s 再请求 ZIP，模拟人类行为

### 6.2 代理要求

- 网站需要翻墙访问，必须配置代理
- 使用 Clash 本地代理（默认端口 7890，从 `clash_config.yaml` 的 `mixed-port` 读取）
- 所有请求通过 `http://127.0.0.1:{port}` 转发
- 代理节点类型：SS（Shadowsocks），支持 `aes-128-gcm` 加密
- 节点地区：香港、日本、台湾、美国、韩国、新加坡

### 6.3 代理自动切换

- 遇到 403 错误 → 立即切换代理节点
- 连续失败 2 次 → 自动切换代理节点
- 切换流程：标记当前节点失败 → 随机选择新节点 → 更新 `session.proxies` → 清除 cookies
- 清除 cookies 的原因：新节点可能需要重新建立会话

### 6.4 请求频率限制

- 分类列表页爬取：无显式延迟（但建议控制）
- 下载页访问（Stage 3）：每次间隔 **2 秒**
- ZIP 文件下载（Stage 4）：每次间隔 **2 秒**
- 访问下载页后等待 **1 秒** 再请求 ZIP（模拟人类行为）
- **并发下载警告**：`--concurrent` 启用多线程（最多 3 worker），但可能触发更多防护

### 6.5 浏览器请求头

必须模拟完整 Chrome 浏览器请求头，关键字段：
- `User-Agent`：Chrome 120 macOS
- `Accept`：包含 `text/html`, `application/xhtml+xml`, `image/webp` 等
- `Accept-Language`：`zh-CN,zh;q=0.9,en;q=0.8`
- `sec-ch-ua` / `sec-ch-ua-mobile` / `sec-ch-ua-platform`：Chrome 指纹
- `Sec-Fetch-Dest` / `Sec-Fetch-Mode` / `Sec-Fetch-Site`：Fetch 元数据
- `Sec-Fetch-Site` 下载时设为 `cross-site`（因为 ZIP 域名不同）

### 6.6 文件名处理

- ZIP 文件名包含时间戳：`YYYYMMDDHHmmss{随机数}.zip`
- 解压后的文档重命名格式：`{YYYYMMDD}{报告标题}.{ext}`
- 文件名需清理中文标点（`【】（）《》""''：；，。！？`）
- 文件夹名比文件名更严格（只保留字母、数字、中文、下划线）
- 最大文件名长度 200 字符

### 6.7 分页终止条件

- 分类列表页没有"总页数"信息
- 终止条件：某页返回空报告列表 → 停止爬取
- 或达到 `--max-pages` 限制

### 6.8 其他注意事项

- `detail_scraper.py` 和 `utils/helpers.py` 为空文件（未使用）
- `codePrompt.md` 是原始需求文档，包含所有 39 个分类的完整列表
- `FIX.md` 是防盗链修复的详细说明文档
- `test_anti_hotlink.py` 是独立的防盗链测试脚本（可直接运行验证）
- 日志使用 loguru，输出到 `logs/` 目录，10MB 轮转，30 天保留
- 数据库和下载目录均被 `.gitignore` 排除

---

## 7. 爬虫管线（5 阶段）

```
Stage 1: 分类爬取
  → 遍历 CATEGORY_NAMES，构造 tags-{id}.html URL，存入 categories 表

Stage 2: 报告列表爬取
  → 对每个分类，爬取 tags-{id}.html 和 tags-{id}_{N}.html
  → 解析 .wapost.card 卡片，提取 post_id/title/detail_url 等
  → 存入 reports 表，status=pending

Stage 3: 下载链接获取
  → 遍历 status=pending 的报告
  → 访问 download/{post_id}.html 页面
  → 从 HTML 中提取 ZIP URL
  → 更新 reports.download_url，status=ready

Stage 4: ZIP 下载
  → 遍历 status=ready 的报告
  → 先访问下载页（建立 session）
  → 使用 Referer 下载 ZIP 到 data/downloads/{分类名}/
  → 自动解压 ZIP，重命名文档
  → 删除 ZIP（默认），status=downloaded

Stage 5: 解压（可独立运行）
  → 遍历 status=downloaded 的报告
  → 解压 ZIP，重命名文档为 {YYYYMMDD}{标题}.{ext}
```

---

## 8. 快速参考

### 关键 URL 模板

```python
CATEGORY_PAGE       = "https://ipoipo.cn/tags-{}.html"         # 第1页
CATEGORY_PAGE_N     = "https://ipoipo.cn/tags-{}_{}.html"      # 第N页
POST_URL            = "https://ipoipo.cn/post/{}.html"          # 文章页
DOWNLOAD_URL        = "https://ipoipo.cn/download/{}.html"      # 下载页（Referer）
ZIP_HOST            = "https://ipo.ai-tag.cn"                   # ZIP 文件域名
```

### CSS 选择器速查

```
报告卡片      → div.wapost.card
报告标题链接   → h2.multi-ellipsis > a
缩略图        → img.img-cover
简介          → p.text
浏览量        → span.view-num
发布日期      → span.edit
ZIP 下载链接   → a[href$=".zip"] 或 正则 http...\.zip
```

### 数据库路径

```
DB:     data/downloads.db
下载:   data/downloads/
日志:   logs/
代理:   config/clash_config.yaml
```
