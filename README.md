# 自动续火花

一个用于抖音好友火花续期管理的 Web 控制台项目。前端基于 Vue 3 + Element Plus，后端基于 FastAPI + Selenium，通过 Chrome/Chromium 自动化抖音 Web 页面，实现好友列表查看、消息发送和每日定时任务管理。

> 本项目仅供个人学习与研究使用。请遵守相关平台规则、法律法规和账号安全要求，不要用于骚扰、滥发、绕过平台限制或其他违规用途。

## 功能

- 后台管理员登录
- 抖音扫码登录、手机号验证码登录、Base64 Cookie 登录
- 抖音登录状态检测
- 好友列表展示与搜索
- 单个好友发送消息
- 单个或批量创建每日定时发送任务
- 定时任务查看、修改、删除
- Cookie 导出、页面截图、强制退出登录
- Ubuntu VPS 后端部署适配
- PM2 托管 FastAPI 后端
- Nginx `/api/` 反向代理支持

## 技术栈

前端：

- Vue 3
- Vite
- Element Plus
- Pinia
- Vue Router
- Axios

后端：

- Python
- FastAPI
- Uvicorn
- Selenium
- schedule
- Chrome/Chromium + ChromeDriver

## 项目结构

```text
.
├── public/                         # 前端静态资源
├── src/                            # Vue 前端源码
│   ├── api/douyin.js               # 前端 API 封装
│   ├── router/index.js             # 前端路由
│   ├── stores/                     # Pinia/共享状态
│   └── views/                      # 页面组件
├── 抖音自动续火花-后端.py              # FastAPI + Selenium 后端
├── requirements.txt                # Python 后端依赖
├── ecosystem.config.cjs            # PM2 后端托管配置
├── .env.example                    # 后端环境变量示例
├── README_DEPLOY_BACKEND.md        # Ubuntu 后端部署说明
├── package.json                    # 前端依赖与脚本
└── vite.config.js                  # Vite 配置和 /api 代理
```

## 本地前端开发

```bash
npm install
npm run dev
```

默认访问：

```text
http://localhost:5173
```

Vite 会把 `/api` 请求代理到：

```text
http://localhost:9844
```

## 后端运行

创建虚拟环境并安装依赖：

```bash
python3 -m venv venv
venv/bin/pip install --upgrade pip
venv/bin/pip install -r requirements.txt
```

复制环境变量模板：

```bash
cp .env.example .env
```

必须修改 `.env` 中的管理员密码：

```text
ADMIN_PASSWORD=your-strong-password
```

不要使用 `123456`、`change-me-now`、`admin`、`password` 等默认或弱密码，后端会拒绝启动。

启动后端：

```bash
venv/bin/python 抖音自动续火花-后端.py
```

健康检查：

```bash
curl http://127.0.0.1:9844/health
```

预期返回：

```json
{"status":"ok","service":"tiktok-auto-spark-backend"}
```

## Ubuntu VPS 部署

完整后端部署步骤见：

[README_DEPLOY_BACKEND.md](README_DEPLOY_BACKEND.md)

典型部署方式：

- 后端监听 `127.0.0.1:9844`
- PM2 托管 Python 后端进程
- Nginx 将 `/api/` 反向代理到 `http://127.0.0.1:9844/`
- 浏览器自动化使用 `chromium` + `chromedriver`

## 环境变量

```env
HOST=127.0.0.1
PORT=9844
CHROME_BIN=/usr/bin/chromium
CHROMEDRIVER_PATH=/usr/bin/chromedriver
HEADLESS=true
ADMIN_USERNAME=admin
ADMIN_PASSWORD=change-me-now
ALLOW_PUBLIC_BIND=false
CORS_ORIGINS=https://spark.aprivity.xyz,http://localhost:5173,http://127.0.0.1:5173
```

生产环境请至少修改：

- `ADMIN_USERNAME`
- `ADMIN_PASSWORD`
- `CORS_ORIGINS`

## 安全说明

- 后端默认只监听 `127.0.0.1`，不建议直接暴露到公网。
- `.env`、Cookie、日志、缓存文件已加入 `.gitignore`。
- 服务不会在日志中输出 Cookie、token、Base64Cookie 或完整二维码内容。
- 不允许默认弱密码启动。
- 如需公网监听，必须显式设置 `ALLOW_PUBLIC_BIND=true`，但生产环境推荐通过 Nginx 反代访问。

## 许可证

MIT
