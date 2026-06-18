# Unicom-IPTV-M3U-Generator

用 Python 模拟机顶盒登录鉴权，获取 IPTV 频道列表和节目单。

本仓库模拟了联通 IPTV 机顶盒的登录流程，可以自动获取频道的组播播放列表、单播回看地址和节目单。

> **本项目基于 [Unicom-IPTV-Mock](https://github.com/VergilGao/Unicom-IPTV-Mock) 二次开发，新增 Windows 桌面版 GUI 工具，无需敲命令，小白也能轻松上手。**

## 功能

- 🖥️ **Windows 桌面版 GUI 工具**（新增！一键获取列表）
- 🌐 Web 管理界面（响应式，兼容手机）
- 自动完成 EDS/EPG 服务器登录鉴权
- 获取频道列表（组播地址 + 回看地址）
- 频道筛选、重命名、重编号
- 生成 `iptv.m3u` 播放列表
- 抓取 ESAAS 节目单 → `epg.xml`
- SQLite 缓存节目单，增量更新
- 定时自动运行（APScheduler）
- 在线查看运行日志（SSE 实时推送）

## 快速开始（Windows 桌面版）⭐ 推荐

### 方式一：直接下载 exe（无需安装 Python）

1. 从 [Releases](https://github.com/xisohi/Unicom-IPTV-M3U-Generator/releases) 下载 `IPTV列表获取工具.exe`
2. 双击运行
3. 填写认证信息（EDS服务器、UserID、STBID、MAC地址）
4. 点击「获取列表」
5. 用 PotPlayer/VLC 打开生成的 `iptv.m3u`
6. windows打包命令：
```bash
pyinstaller "IPTV列表获取工具.spec"
```

### 方式二：从源码运行

```bash
# 安装依赖
pip install -r requirements.txt

# 运行桌面版
python gui_launcher.py

# 或运行 Web 版
DATA_DIR=./data python src/web.py

## 协议流程

```
Phase 1 服务器发现
GET /EDS/jsp/AuthenticationURL → 302 重定向到 EPG 服务器

Phase 2 获取 EncryptToken
POST /EPG/jsp/authLoginHWCU.jsp → 返回 HTML 内含 EncryptToken

Phase 3 认证
POST /EPG/jsp/ValidAuthenticationHWCU.jsp
→ 提交 Authenticator（DES ECB 加密）、STBType、STBID、MAC 等
→ 成功返回 UserToken

Phase 4 频道列表
POST /EPG/jsp/getchannellistHWCU.jsp → 返回频道列表的 JS 数据

Phase 5 EPG 节目单
POST /esaas/v2/live/channel → 获取 ESAAS 频道映射
POST /esaas/v1/live/program → 获取节目数据
```

## 使用方法

### 环境要求

- Python 3.13+
- 网络路由能访问 IPTV 内网服务器（EDS/EPG/ESAAS）

### 本地运行

```bash
# 安装依赖
pip install -r requirements.txt

# 运行（数据目录默认为 ./data）
mkdir -p ./data
DATA_DIR=./data python src/web.py

# 或使用 VSCode 调试（按 F5，需 .vscode/launch.json）
```

访问 `http://localhost:5000`，通过 Web 界面完成全部配置。

### Podman / Docker

确保容器网络能路由到 IPTV 内网服务器（需自行配置 `--network host` 或自定义网络）。

```bash
# 构建
docker build -t ghcr.io/vergilgao/unicom-iptv-mock:latest .

# 创建数据目录
mkdir -p /path/data

# HTTP 运行
docker run -d --name unicom-iptv-mock \
  -v /path/data:/data:Z \
  -p 5000:5000 \
  --restart unless-stopped \
  ghcr.io/vergilgao/unicom-iptv-mock:latest

# HTTPS 运行（PEM 证书文件）
docker run -d --name unicom-iptv-mock \
  -v /path/data:/data:Z \
  -v /path/cert.pem:/ssl/cert.pem:Z \
  -e SSL_CERT_KEY=/ssl/cert.pem \
  -e WEB_PORT=8443 \
  -p 8443:8443 \
  --restart unless-stopped \
  ghcr.io/vergilgao/unicom-iptv-mock:latest

# 从 GHCR 拉取
docker pull ghcr.io/vergilgao/unicom-iptv-mock:latest
```

首次启动后访问 Web 界面，在"配置"页面填入参数，在"频道"页面勾选需要的频道，点击"立即运行"或等待定时任务自动执行。

### 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `DATA_DIR` | `/data` | 数据持久化目录（配置、日志、输出文件） |
| `WEB_PORT` | `5000` | Web 端口 |
| `SSL_CERT_KEY` | 无 | 合并 PEM 证书文件路径（启用 HTTPS） |

## Web 界面

| 页面 | 路径 | 功能 |
|------|------|------|
| 首页 | `/` | 运行状态、手动触发、下载 iptv.m3u / epg.xml |
| 配置 | `/config` | 编辑登录参数（server、userId、STBID、MAC 等）和 EPG 设置 |
| 频道 | `/channels` | 搜索、勾选频道，自定义显示名称和频道号 |
| 定时 | `/schedule` | Cron 表达式配置自动运行 |
| 日志 | `/logs` | 查看最近 7 次运行日志，运行时 SSE 实时输出 |

### 频道配置示例

在 Web 界面的"频道"页勾选需要的频道，设置显示名和频道号。配置保存在 `channels` 字段中：

```yaml
channels:
  - original: "CCTV-1高清"
    name: "CCTV-1综合"
    chno: 1
  - original: "CCTV-2高清现网"
    name: "CCTV-2财经"
    chno: 2
```

`channels.txt` 会输出全部 255 个频道的原始名称，供配置时复制。

## 输出文件

所有输出文件生成在 `DATA_DIR` 目录中：

| 文件 | 说明 |
|------|------|
| `iptv.m3u` | 播放列表（Web 界面可直接下载） |
| `epg.xml` | XMLTV 格式电子节目单 |
| `epg.db` | SQLite 节目单缓存 |
| `channels.txt` | 全部频道原始名称参考列表 |
| `logs/` | 运行日志目录（每次运行独立文件） |

## 认证算法说明

Authenticator 使用 DES ECB 模式加密，密钥为 `12345678`，payload 格式：

```
{8位随机数}${EncryptToken}${UserID}${STBID}${IP}${MAC}$$CTC
```

## 项目结构

```
Unicom-IPTV-M3U-Generator/
├── src/
│   ├── web.py              # Flask 总入口（Web UI + 调度器）
│   ├── scraper.py           # 抓包流程（登录、频道列表、EPG）
│   ├── storage.py           # SQLite 缓存（节目单）
│   ├── scheduler.py         # APScheduler 定时任务
│   ├── templates/           # Jinja2 模板
│   └── static/              # CSS
├── gui_launcher.py          # 🆕 Windows 桌面版 GUI
├── dist/                    # 🆕 打包后的 exe 文件
├── docs/                    # 文档
├── Dockerfile
├── config.yaml              # 用户配置文件
├── requirements.txt
├── README.md
├── LICENSE
└── .github/workflows/       # GitHub Actions（Release 时构建 Docker 镜像到 GHCR）
```

## 使用前必读

本仓库代码旨在提供一种家庭自动化的思路，仅供个人测试使用，并不保证在其他用户的使用环境下的功能完善。请勿用于任何商业用途。

## 申明

当你查阅、下载了本项目源代码或二进制程序，即代表你接受了以下条款：

- 本项目和项目成果仅供技术、学术交流和 Python3 性能测试使用
- 用户在使用本项目和项目成果前，请用户了解并遵守当地法律法规
- 如本项目及项目成果使用过程中存在违反当地法律法规的行为，请勿使用该项目及项目成果
- 法律后果及使用后果由使用者承担
- 若用户不同意上述条款任意一条，请勿使用本项目和项目成果

## License

GPL-3.0

