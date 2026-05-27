# TikTokAutoSparkWeb Linux 服务器适配版

> 本项目基于开源项目 [DkoBot/TikTokAutoSparkWeb](https://github.com/DkoBot/TikTokAutoSparkWeb) 进行二次修改与部署适配。  
> 原项目主要面向本地 / Windows 环境，本 README 记录将其改造成适合 **Ubuntu Linux VPS + Nginx + PM2 + Selenium Chromium + Xpra** 的服务器版本时遇到的全部关键问题、错误现象与修复方法。

## 1. 项目说明

这是一个用于管理抖音好友火花续连的 Web 工具。前端提供后台管理页面，后端通过 Selenium 控制浏览器登录抖音并执行消息发送 / 定时任务。

本 Linux 适配版的核心目标是：

- 支持在 Ubuntu VPS 上部署；
- 后端只监听 `127.0.0.1`，由 Nginx 反向代理；
- 使用 PM2 托管 Python FastAPI 后端；
- 使用 Linux Chromium / ChromeDriver 代替 Windows EdgeDriver；
- 使用 Xpra 显示服务器端 Chromium 窗口，用于扫码登录、二次验证和排错；
- 使用固定 Chrome Profile 保存抖音登录态；
- 记录部署过程中遇到的全部典型错误和修复方法。

> ⚠️ 注意：本项目仅建议作为个人学习、研究和私人自用工具。涉及第三方平台登录态和自动化操作，请自行遵守相关平台规则，不要用于骚扰、批量营销或其他不当用途。

---

## 2. 上游项目与本版本差异

### 2.1 上游项目

- 上游仓库：`https://github.com/DkoBot/TikTokAutoSparkWeb`
- 技术栈大致包括：
  - 前端：Vue / Vite / Element Plus；
  - 后端：Python / FastAPI / Selenium；
  - 浏览器自动化：原项目中存在 Windows 环境相关写法。

### 2.2 本版本主要修改方向

本版本面向 Linux 服务器部署，重点修改：

1. 将 Windows EdgeDriver 路径改为 Linux Chromium / ChromeDriver。
2. 后端改为非交互式启动，适配 PM2。
3. 后端固定监听 `127.0.0.1:9844`，避免直接暴露公网。
4. 增加 `.env` 配置项，统一管理端口、浏览器路径、headless 模式、Chrome Profile 等。
5. 增加 `/health` 健康检查接口。
6. 增加 Xpra 可视化调试方案，用于处理抖音扫码登录和二次验证。
7. 记录并修复 Linux VPS 部署中的常见错误。
8. 增强安全建议：不要打印密码、token、Cookie、二维码 base64。

---

## 3. 推荐部署架构

```text
用户浏览器
   ↓
https://spark.example.com
   ↓
Nginx HTTPS
   ├─ /            → Vue/Vite dist 静态文件
   └─ /api/ 或后端接口 → 127.0.0.1:9844
                         ↓
                  FastAPI + Selenium
                         ↓
                  服务器 Chromium 登录抖音
                         ↓
                  读取好友 / 发送消息 / 执行定时任务
```

推荐信息：

```text
项目目录：/www/wwwroot/spark.example.com
后端监听：127.0.0.1:9844
PM2 服务名：spark-backend
Xpra 显示器：:100
Xpra Web 端口：127.0.0.1:14500
Chrome Profile：/www/wwwroot/spark.example.com/chrome-profile
```

---

## 4. 环境要求

服务器推荐：

```text
Ubuntu 22.04 / 24.04
Python 3.10+
Node.js 18+
Nginx
PM2
Chromium + ChromeDriver
Xpra
```

安装基础依赖：

```bash
apt update
apt install -y git curl unzip nginx python3 python3-venv python3-pip
apt install -y chromium-browser chromium-chromedriver
apt install -y xpra openbox xterm
```

检查浏览器与驱动：

```bash
which chromium-browser || which chromium
which chromedriver
chromedriver --version
```

正常应能看到：

```text
/usr/bin/chromium-browser
/usr/bin/chromedriver
ChromeDriver xxx
```

如果出现类似：

```text
libpxbackend-1.0.so: cannot open shared object file
Failed to load module: ... libgiolibproxy.so
```

但最后能输出 `ChromeDriver xxx`，一般不是致命问题。

---

## 5. 拉取项目

```bash
cd /www/wwwroot
git clone https://github.com/<your-name>/<your-repo>.git spark.example.com
cd /www/wwwroot/spark.example.com
```

如果出现：

```text
Repository not found
```

可能原因：

1. 仓库是私有仓库；
2. 仓库地址写错；
3. 服务器没有 GitHub 访问权限；
4. HTTPS clone 需要 token。

解决方法：

- 将仓库设置为 Public；
- 或使用 GitHub Personal Access Token；
- 或配置 SSH Key 后用 SSH clone。

---

## 6. 后端配置

### 6.1 创建虚拟环境

```bash
cd /www/wwwroot/spark.example.com
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
```

如果有 `requirements.txt`：

```bash
pip install -r requirements.txt
```

如果没有，临时安装：

```bash
pip install fastapi uvicorn selenium schedule requests python-dotenv
```

### 6.2 `.env` 推荐配置

在项目根目录创建 `.env`：

```env
HOST=127.0.0.1
PORT=9844
CHROME_BIN=/usr/bin/chromium-browser
CHROMEDRIVER_PATH=/usr/bin/chromedriver
CHROME_USER_DATA_DIR=/www/wwwroot/spark.example.com/chrome-profile
HEADLESS=false
ADMIN_USERNAME=your-admin-name
ADMIN_PASSWORD=your-strong-password
ALLOW_PUBLIC_BIND=false
CORS_ORIGINS=https://spark.example.com,http://localhost:5173,http://127.0.0.1:5173
```

创建浏览器资料目录：

```bash
mkdir -p /www/wwwroot/spark.example.com/chrome-profile
chmod 700 /www/wwwroot/spark.example.com/chrome-profile
```

### 6.3 重要配置说明

#### `CHROME_BIN`

应写为：

```env
CHROME_BIN=/usr/bin/chromium-browser
```

常见错误：

```env
CHROME_BIN=/usr/bin/chromium-blowser
```

`blowser` 是拼写错误，应改成 `browser`。

#### `HEADLESS`

Python 中不能这样判断：

```python
bool(os.getenv("HEADLESS"))
```

因为：

```python
bool("false") == True
```

正确做法应显式解析：

```python
def parse_bool(value: str, default: bool = False) -> bool:
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}
```

只有 `HEADLESS=true` 时才添加：

```text
--headless=new
--ozone-platform=headless
```

当 `HEADLESS=false` 时，绝不能添加这些参数，否则 Xpra 看不到浏览器窗口。

#### `CHROME_USER_DATA_DIR`

必须给 Chrome 添加固定资料目录：

```text
--user-data-dir=/www/wwwroot/spark.example.com/chrome-profile
```

如果没有这个参数，Chrome 可能使用临时目录：

```text
/tmp/org.chromium.Chromium.scoped_dir.xxxxxx
```

这会导致重启后抖音登录态丢失。

---

## 7. PM2 启动后端

语法检查：

```bash
cd /www/wwwroot/spark.example.com
source venv/bin/activate
python3 -m py_compile 抖音自动续火花-后端.py
```

启动：

```bash
pm2 start ./venv/bin/python --name spark-backend -- "抖音自动续火花-后端.py"
pm2 save
```

查看状态：

```bash
pm2 list
pm2 logs spark-backend --lines 100
```

健康检查：

```bash
curl http://127.0.0.1:9844/health
```

正常返回示例：

```json
{"status":"ok","service":"tiktok-auto-spark-backend"}
```

---

## 8. 前端构建

```bash
cd /www/wwwroot/spark.example.com
npm install
npm run build
ls -lah dist
```

需要看到：

```text
dist/index.html
```

---

## 9. Nginx 配置

创建配置：

```bash
nano /etc/nginx/conf.d/spark.example.com.conf
```

示例：

```nginx
server {
    listen 80;
    server_name spark.example.com;

    root /www/wwwroot/spark.example.com/dist;
    index index.html;

    client_max_body_size 20m;

    location / {
        try_files $uri $uri/ /index.html;
    }

    location /api/ {
        proxy_pass http://127.0.0.1:9844/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 300;
        proxy_connect_timeout 300;
        proxy_send_timeout 300;
    }
}
```

检查：

```bash
nginx -t
systemctl reload nginx
```

---

## 10. HTTPS 证书

```bash
apt install -y certbot python3-certbot-nginx
certbot --nginx -d spark.example.com
```

验证：

```bash
curl -I https://spark.example.com
curl https://spark.example.com/api/health
```

---

## 11. Xpra：服务器可视化浏览器

### 11.1 为什么需要 Xpra

抖音登录经常出现：

- 扫码登录；
- 手机确认；
- 二次验证；
- 滑块验证；
- 安全环境提示。

如果后端运行在 `headless` 模式，你看不到这些页面，后端可能误判“已登录”，但实际上无法获取用户名、好友列表或发送消息。

### 11.2 启动 Xpra

```bash
xpra start :100 \
  --bind-tcp=127.0.0.1:14500 \
  --html=on \
  --start-child=openbox \
  --daemon=yes
```

检查：

```bash
xpra list
ss -lntp | grep 14500
```

### 11.3 Windows 本地打开隧道

在 Windows PowerShell 新开窗口：

```powershell
ssh -L 14500:127.0.0.1:14500 root@<server-ip>
```

浏览器打开：

```text
http://127.0.0.1:14500
```

### 11.4 用 Xpra 显示器重启后端

```bash
cd /www/wwwroot/spark.example.com
pm2 stop spark-backend
pkill -f chromedriver || true
pkill -f chromium || true
pkill -f chrome || true

DISPLAY=:100 \
HEADLESS=false \
CHROME_BIN=/usr/bin/chromium-browser \
CHROMEDRIVER_PATH=/usr/bin/chromedriver \
CHROME_USER_DATA_DIR=/www/wwwroot/spark.example.com/chrome-profile \
pm2 restart spark-backend --update-env
```

如果不生效，重建 PM2 服务：

```bash
pm2 delete spark-backend
DISPLAY=:100 pm2 start ./venv/bin/python --name spark-backend -- "抖音自动续火花-后端.py"
pm2 save
```

检查 Chromium 参数：

```bash
ps aux | grep -E "chromium|chrome|chromedriver" | grep -v grep
```

目标：

```text
不能出现 --headless=new
不能出现 --ozone-platform=headless
应出现 --user-data-dir=/www/wwwroot/spark.example.com/chrome-profile
```

---

## 12. 首次登录流程

1. 打开 Xpra 页面：`http://127.0.0.1:14500`。
2. 打开项目后台：`https://spark.example.com`。
3. 在后台触发扫码登录或刷新好友。
4. 观察 Xpra 中的服务器 Chromium。
5. 如果出现抖音扫码 / 二次验证 / 手机确认，在 Xpra 中手动完成。
6. 完成后刷新好友列表。

成功标志：

```text
好友列表能显示
/Api/GetUsername 能返回用户名
/Api/GetFriendsList 不再返回“暂无好友或页面未加载”
```

---

## 13. 后台鉴权：token 不是 Cookie

登录接口返回的是 token：

```json
{"code":200,"data":"<token>"}
```

后续 curl 必须带：

```http
Authorization: Bearer <token>
```

获取 token：

```bash
read -p "Username: " SPARK_USER
read -s -p "Password: " SPARK_PASS
echo

curl -sS -G "http://127.0.0.1:9844/Api/Login/Admin" \
  --data-urlencode "username=$SPARK_USER" \
  --data-urlencode "password=$SPARK_PASS" \
  -o /tmp/spark_login_body.json

TOKEN=$(python3 - <<'PY'
import json
with open('/tmp/spark_login_body.json', 'r', encoding='utf-8') as f:
    print(json.load(f)['data'])
PY
)

echo ${#TOKEN}
```

测试接口：

```bash
curl -H "Authorization: Bearer $TOKEN" http://127.0.0.1:9844/Api/GetLogin
echo
curl -H "Authorization: Bearer $TOKEN" http://127.0.0.1:9844/Api/GetUsername
echo
curl -H "Authorization: Bearer $TOKEN" http://127.0.0.1:9844/Api/GetFriendsList
echo
curl -H "Authorization: Bearer $TOKEN" http://127.0.0.1:9844/Time/getlist
echo
```

如果返回：

```json
{"code":401,"data":"未授权"}
```

通常说明：

1. `$TOKEN` 为空；
2. token 已过期；
3. 后端重启后旧 token 失效；
4. 终端里的 token 与浏览器后台 token 不是同一个。

解决：重新登录获取 token。

---

## 14. 错误与修复方法汇总

### 14.1 SSH `Permission denied`

现象：

```text
Permission denied (password)
```

原因：

- root 密码错误；
- 使用了宝塔密码而不是 VPS root 密码；
- root 密码登录被禁用；
- root 密码已被重置。

修复：

1. 进入 VPS 控制面板 Console / VNC。
2. 重置 root 密码。
3. 再用 SSH 登录。

```bash
passwd root
```

### 14.2 PM2 报 `venv/bin/python not found`

现象：

```text
Script not found: /www/wwwroot/spark.example.com/venv/bin/python
```

原因：未创建虚拟环境。

修复：

```bash
cd /www/wwwroot/spark.example.com
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 14.3 `CHROME_BIN` 拼写错误

错误配置：

```env
CHROME_BIN=/usr/bin/chromium-blowser
```

正确配置：

```env
CHROME_BIN=/usr/bin/chromium-browser
```

### 14.4 `HEADLESS=false` 仍然 headless

现象：

```text
ps aux 中仍然出现 --headless=new
```

原因：代码中用 `bool("false")` 判断，结果为 `True`；或写死了 headless 参数。

修复：显式解析布尔值，只在 `HEADLESS=true` 时添加 headless 参数。

### 14.5 Xpra 看不到浏览器

原因：

- Chrome 仍是 headless；
- PM2 没吃到 `DISPLAY=:100`；
- 后端代码没读取 `.env`；
- 没有触发 Selenium 打开浏览器。

排查：

```bash
pm2 env <id> | grep -E "DISPLAY|HEADLESS|CHROME_USER_DATA_DIR"
ps aux | grep -E "chromium|chrome|chromedriver" | grep -v grep
```

### 14.6 好友列表为空 / 页面未加载

现象：

```json
{"code":400,"data":"已登录,但未获取到用户名"}
{"code":404,"data":"暂无好友或页面未加载"}
```

原因：

- 抖音登录没有真正完成；
- 服务器 Chromium 弹出了二次验证但无人处理；
- headless 模式导致看不到验证；
- 页面选择器过旧。

修复：使用 Xpra 打开服务器 Chromium，手动完成验证。

### 14.7 curl 接口返回 `401 未授权`

原因：终端 `$TOKEN` 为空或过期。

修复：重新登录后台拿 token，并带 `Authorization: Bearer $TOKEN`。

### 14.8 修改任务时间失败

错误链路：

```text
edit_time
→ AiqingGongyu_text()
→ requests.get('https://v2.xxapi.cn/api/aiqinggongyu')
→ RemoteDisconnected / ConnectionError
```

原因：服务器访问第三方随机文案 API 不稳定，甚至 TLS 握手失败。

服务器上可能出现：

```text
curl: (35) SSL routines::unexpected eof while reading
```

修复建议：

1. `requests.get` 增加 `timeout=5`。
2. 增加 `User-Agent` 和 `Accept` 请求头。
3. 第三方接口失败时使用本地 fallback 文案。
4. `edit_time` 中也要兜底，不允许文案接口失败影响修改时间主流程。

fallback 示例：

```text
今天也要记得续火花呀
本火花已续上
记得保持联系，火花别断
```

### 14.9 手动发送失败

可能原因：

1. Xpra / Chromium 会话被关闭；
2. 抖音登录态失效；
3. 后台显示的是旧好友缓存；
4. Selenium 当前页面不在正常聊天状态；
5. 输入框 / 发送按钮选择器失效。

排查：

```bash
pm2 logs spark-backend --lines 100
ps aux | grep -E "chromium|chrome|chromedriver" | grep -v grep
```

使用者经验中验证：如果关闭 Xpra / Chromium 导致抖音退出登录，发送会失败；恢复 Xpra 并重新登录后，手动发送和自动发送可以恢复。

### 14.10 `/Api/Send` HTTP 200 但前端仍提示失败

说明请求到达后端，但业务逻辑可能失败。需要查看接口 JSON 返回和 Xpra 浏览器实际动作。

curl 测试：

```bash
curl -sS -H "Authorization: Bearer $TOKEN" \
  --get "http://127.0.0.1:9844/Api/Send" \
  --data-urlencode "name=065642" \
  --data-urlencode "text=hi"
echo
```

如果返回 `401`，先重新获取 token。

---

## 15. 使用者经验

本节记录部署和排错过程中由实际使用者发现的关键经验。

### 15.1 我发现：二次验证必须在服务器浏览器里完成

本地电脑浏览器登录抖音并不能让服务器 Selenium 获得登录态。真正执行自动化的是服务器里的 Chromium，所以扫码、二次验证、滑块验证都必须在服务器浏览器环境中完成。

解决方法：使用 Xpra 显示服务器 Chromium，然后在 Xpra 里完成验证。

### 15.2 我发现：关闭 Xpra / Chromium 后可能导致发送失败

如果关闭了 Xpra 会话、服务器 Chromium、ChromeDriver，或重启 PM2 后端，抖音登录态可能丢失。此时后台页面可能仍能显示缓存好友，但实际发送消息会失败。

解决方法：

1. 保持 `xpra :100` 运行；
2. 保持 `spark-backend` 在线；
3. 不随意 `pkill chrome/chromium/chromedriver`；
4. 如果已关闭，重新启动 Xpra，重新完成抖音登录；
5. 确认好友刷新正常后再测试发送。

### 15.3 我发现：第三方文案接口本地能打开，不代表服务器能访问

浏览器打开 `https://v2.xxapi.cn/api/aiqinggongyu` 可能正常，但 RackNerd 服务器上 `curl` 会出现 TLS EOF：

```text
curl: (35) SSL routines::unexpected eof while reading
```

所以不能把修改任务时间功能强依赖这个接口。

解决方法：为随机文案接口增加 timeout、headers 和 fallback。

### 15.4 我发现：curl 测试不能直接复用浏览器登录态

后台登录返回 token，不是 Cookie。浏览器登录成功不代表 SSH 终端里的 curl 有权限。

如果 curl 返回：

```json
{"code":401,"data":"未授权"}
```

需要重新在终端登录接口拿 token。

### 15.5 我发现：Xpra 是比普通 VNC 更适合本项目的方案

VNC 可以用，但 Xpra 更适合只显示服务器端应用窗口，部署更轻量，适合临时处理抖音登录和二次验证。

### 15.6 我发现：自动续火花功能是否可用，必须以“到点真实发送成功”为最终标准

只看到任务列表添加成功不代表自动续火花一定成功。最终验收必须添加一个 3～5 分钟后的测试任务，看手机端聊天记录是否真的收到消息。

本次最终测试结果：

```text
抖音登录：成功
好友列表：成功
手动发送：成功
添加定时任务：成功
到点自动发送：成功
```

---

## 16. 最终验收流程

1. 打开后台：

```text
https://spark.example.com
```

2. 刷新好友列表。
3. 选择一个好友，手动发送测试消息。
4. 添加一个当前时间后 3～5 分钟的任务。
5. 消息内容填写：

```text
测试内容：本火花已续
```

6. 到点后检查：

- 服务器 Chromium 是否执行发送；
- 手机端抖音聊天是否收到；
- PM2 日志是否出现执行记录。

查看日志：

```bash
pm2 logs spark-backend --lines 100
```

---

## 17. 日常使用建议

正常使用时保持：

```text
Xpra :100 运行
PM2 spark-backend 在线
chrome-profile 不删除
```

不要随便执行：

```bash
xpra stop :100
pkill -f chrome
pkill -f chromium
pkill -f chromedriver
pm2 restart spark-backend
```

除非你准备重新登录抖音。

如果出现发送失败，优先检查：

```bash
xpra list
pm2 list
ps aux | grep -E "chromium|chrome|chromedriver" | grep -v grep
pm2 logs spark-backend --lines 100
```

---

## 18. 安全建议

### 18.1 不要提交敏感文件

`.gitignore` 应至少包含：

```gitignore
.env
logs/
chrome-profile/
*.log
__pycache__/
venv/
```

### 18.2 不要把密码放在 URL 日志里

如果后端登录仍使用：

```text
GET /Api/Login/Admin?username=...&password=...
```

那么 Uvicorn / PM2 access log 可能记录明文密码。

建议修改为 POST 登录：

```text
POST /Api/Login/Admin
Content-Type: application/json
```

请求体传：

```json
{"username":"...","password":"..."}
```

或至少过滤 access log，不记录 password 参数。

### 18.3 给后台加 Nginx Basic Auth

```bash
apt install -y apache2-utils
htpasswd -c /etc/nginx/.spark_htpasswd aprivity
```

Nginx server 块加入：

```nginx
auth_basic "Private Spark Panel";
auth_basic_user_file /etc/nginx/.spark_htpasswd;
```

重载：

```bash
nginx -t
systemctl reload nginx
```

---

## 19. 常用命令

查看服务：

```bash
pm2 list
pm2 logs spark-backend --lines 100
pm2 restart spark-backend
pm2 save
```

检查 Nginx：

```bash
nginx -t
systemctl reload nginx
systemctl status nginx --no-pager
```

检查后端：

```bash
curl http://127.0.0.1:9844/health
curl https://spark.example.com/api/health
```

查看 Xpra：

```bash
xpra list
ss -lntp | grep 14500
```

查看 Chromium：

```bash
ps aux | grep -E "chromium|chrome|chromedriver" | grep -v grep
```

清理日志和历史：

```bash
pm2 flush spark-backend
history -c
history -w
```

---

## 20. 当前测试结论

截至本文档记录，Linux 服务器适配版已经完成以下验证：

```text
网站访问：通过
HTTPS：通过
后端健康检查：通过
后台 token 鉴权：通过
服务器 Chromium 登录抖音：通过
Xpra 可视化验证：通过
好友列表：通过
手动发送：通过
添加定时任务：通过
到点自动发送：通过
```

仍建议继续优化：

```text
修改时间接口增加第三方文案 fallback
登录接口改 POST，避免密码进入 access log
/Api/Send 增加 debug_send.png 和 debug_send.html
日志中隐藏 token、password、cookie
进一步增强好友匹配和输入框选择器
```

---

## 21. 致谢

本项目基于 [DkoBot/TikTokAutoSparkWeb](https://github.com/DkoBot/TikTokAutoSparkWeb) 进行 Linux 服务器部署适配。感谢原作者提供基础实现。

本 README 记录的是将项目部署到 Ubuntu VPS、接入 Nginx HTTPS、PM2 托管、Xpra 可视化浏览器、持久化 Chrome Profile、修复常见错误后的实践经验。

