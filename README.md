# IPO报告自动下载器

一个完整的自动化报告下载系统，支持代理、断点续传、智能去重等功能。

## ✨ 功能特点

- 🌐 **代理支持**: 自动解析Clash配置，智能选择最快节点
- 🔄 **断点续传**: 支持中断后继续下载
- 🚫 **智能去重**: 自动跳过已下载的文件
- 📊 **状态管理**: SQLite数据库记录所有下载状态
- 🎭 **防封策略**: fake-headers + 随机延迟
- 📦 **自动解压**: 下载完成自动解压ZIP文件
- 🗂️ **层级目录**: 按分类和报告名称组织文件
- 📈 **进度显示**: 实时显示下载进度
- ⚡ **并发下载**: 可选的多线程并发下载

## 📁 项目结构

```
ipoipo_downloader/
├── config/
│   ├── settings.py          # 配置文件
│   └── clash_config.yaml    # Clash代理配置
├── core/
│   ├── proxy_manager.py     # 代理管理器
│   ├── http_client.py       # HTTP客户端
│   └── database.py          # 数据库管理
├── scrapers/
│   ├── category_scraper.py  # 分类爬虫
│   ├── list_scraper.py      # 列表爬虫
│   └── download_scraper.py  # 下载链接爬虫
├── download/
│   ├── downloader.py        # 下载管理器
│   └── file_manager.py      # 文件管理器
├── utils/
│   └── logger.py            # 日志配置
├── main.py                  # 主程序
└── requirements.txt
```

## 🚀 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置代理（可选）

将你的Clash配置文件放到 `config/clash_config.yaml`

如果不使用代理，运行时加上 `--no-proxy` 参数。

### 3. 运行程序

```bash
# 查看帮助
python main.py --help

# 运行完整流程（推荐先测试）
python main.py --full --max-pages 2 --max-reports 10

# 不使用代理运行
python main.py --full --no-proxy --max-pages 2 --max-reports 10
```

## 📝 使用示例

### 完整流程

```bash
# 每个分类爬2页，最多下载10个报告
python main.py --full --max-pages 2 --max-reports 10

# 使用并发下载加速
python main.py --full --max-pages 2 --max-reports 10 --concurrent
```

### 分阶段运行

```bash
# Stage 1: 爬取分类列表
python main.py --stage1

# Stage 2: 爬取报告列表（所有分类，每个5页）
python main.py --stage2 --max-pages 5

# Stage 3: 获取下载链接（前50个报告）
python main.py --stage3 --limit 50

# Stage 4: 下载报告（最多20个，使用并发）
python main.py --stage4 --max-reports 20 --concurrent
```

### 指定分类下载

```bash
# 只下载"经济报告"分类（ID=34）
python main.py --stage2 --categories 34 --max-pages 5
python main.py --stage3 --limit 100
python main.py --stage4 --category 34 --max-reports 10

# 下载多个分类
python main.py --stage2 --categories 34 69 85 --max-pages 3
```

### 查看统计

```bash
python main.py --stats
```

## 📂 文件组织

下载的文件按以下结构组织：

```
downloads/
├── 经济报告/
│   ├── 中国地方公共数据开放利用报告/
│   │   ├── 2025中国地方公共数据开放利用报告.zip
│   │   └── [解压后的文件]
│   └── 另一个报告/
├── 人工智能AI/
│   └── ...
└── 其他分类/
```

## ⚙️ 配置说明

### `config/settings.py` 主要配置项：

```python
# 代理配置
USE_PROXY = True              # 是否使用代理
PROXY_TEST_TIMEOUT = 5        # 代理测速超时（秒）

# 下载配置
DOWNLOAD_DIR = "downloads"    # 下载目录
MAX_CONCURRENT_DOWNLOADS = 3  # 最大并发数

# 爬虫配置
REQUEST_DELAY = (1, 3)        # 请求延迟范围（秒）
MAX_RETRIES = 5               # 最大重试次数
```

## 🗄️ 数据库

使用SQLite存储下载状态，位于 `data/downloads.db`

### 主要数据表：

- `categories`: 分类信息
- `reports`: 报告列表
- `downloads`: 下载记录
- `extractions`: 解压记录

### 报告状态：

- `pending`: 待获取下载链接
- `ready`: 准备下载
- `downloaded`: 已下载
- `failed`: 失败
- `no_download_url`: 没有下载链接

## 📋 日志

日志文件位于 `logs/` 目录：

- `app_YYYY-MM-DD.log`: 完整日志
- `error_YYYY-MM-DD.log`: 错误日志

## 🔧 高级功能

### 断点续传

程序会自动检测未完成的下载并继续：

```bash
# 正常下载（支持断点续传）
python main.py --stage4 --max-reports 100

# 强制重新下载
python main.py --stage4 --max-reports 100 --force
```

### 并发下载

```bash
# 使用3个线程并发下载（在settings.py中配置）
python main.py --stage4 --concurrent
```

### 只下载特定分类

```bash
# 查看所有分类ID（在settings.py中）
grep "CATEGORY_NAMES" config/settings.py

# 下载经济报告（ID=34）
python main.py --full --categories 34 --max-pages 10
```

## ⚠️ 注意事项

1. **首次运行**: 建议先用 `--max-pages 2 --max-reports 10` 测试
2. **代理配置**: 如果代理不稳定，可以用 `--no-proxy` 不使用代理
3. **磁盘空间**: 确保有足够的磁盘空间（每个报告通常几MB到几十MB）
4. **网络限制**: 建议设置合理的延迟，避免被封（在settings.py中配置）
5. **中断恢复**: 程序被中断后可以继续运行，会自动跳过已下载的文件

## 🐛 常见问题

### 1. 代理连接失败

```bash
# 检查代理配置文件是否正确
ls config/clash_config.yaml

# 或者不使用代理
python main.py --full --no-proxy
```

### 2. 下载速度慢

```bash
# 使用并发下载
python main.py --stage4 --concurrent

# 或者选择更快的代理节点（程序会自动测速选择）
```

### 3. 某些报告下载失败

```bash
# 查看错误日志
tail -f logs/error_*.log

# 重新尝试失败的报告
python main.py --stage4 --force
```

### 4. 数据库损坏

```bash
# 删除数据库重新开始
rm data/downloads.db
python main.py --full
```

## 📊 性能优化

1. **并发下载**: 使用 `--concurrent` 参数
2. **代理选择**: 程序会自动选择最快的代理节点
3. **断点续传**: 避免重复下载
4. **智能去重**: 自动跳过已下载的文件

## 🔐 安全性

- 使用fake-headers模拟真实浏览器
- 随机延迟避免被识别为机器人
- 支持代理隐藏真实IP
- 自动重试处理网络错误

## 📈 监控

```bash
# 查看实时日志
tail -f logs/app_*.log

# 查看错误日志
tail -f logs/error_*.log

# 查看数据库统计
python main.py --stats
```

## 🤝 贡献

欢迎提交Issue和Pull Request！

## 📄 许可证

MIT License