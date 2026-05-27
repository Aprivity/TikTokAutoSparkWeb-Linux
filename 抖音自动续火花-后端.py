import re, os, gzip
import shutil
import logging
import atexit
from selenium import webdriver
from selenium.webdriver import Keys
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import NoSuchElementException
from selenium.common.exceptions import SessionNotCreatedException
from selenium.webdriver.common.by import By
import schedule, requests
import time, uvicorn
from datetime import datetime
import json, base64
from typing import List, Optional, Tuple
from fastapi import FastAPI, Header, Request, Query, Body
from fastapi.middleware.cors import CORSMiddleware
import threading, hashlib, secrets, random

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("tiktok-auto-spark-backend")

COMMON_CHROME_BINARIES = (
    "/usr/bin/google-chrome",
    "/usr/bin/chromium",
    "/usr/bin/chromium-browser",
)
COMMON_CHROMEDRIVERS = (
    "/usr/bin/chromedriver",
)


def env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in ("1", "true", "yes", "on")


def resolve_existing_path(env_name: str, candidates: Tuple[str, ...]) -> Optional[str]:
    env_path = os.getenv(env_name)
    if env_path and os.path.exists(env_path):
        return env_path
    for candidate in candidates:
        if os.path.exists(candidate):
            return candidate
    return None


def resolve_chrome_binary() -> Optional[str]:
    chrome_bin = resolve_existing_path("CHROME_BIN", COMMON_CHROME_BINARIES)
    if chrome_bin:
        return chrome_bin
    for command in ("google-chrome", "chromium", "chromium-browser"):
        found = shutil.which(command)
        if found:
            return found
    return None


def resolve_chromedriver_path() -> Optional[str]:
    chromedriver_path = resolve_existing_path("CHROMEDRIVER_PATH", COMMON_CHROMEDRIVERS)
    if chromedriver_path:
        return chromedriver_path
    return shutil.which("chromedriver")


def build_chrome_options():
    options = webdriver.ChromeOptions()
    chrome_bin = resolve_chrome_binary()
    if chrome_bin:
        options.binary_location = chrome_bin
    else:
        logger.warning("未找到 Chrome/Chromium 可执行文件，将尝试由 Selenium 自动解析")

    if env_bool("HEADLESS", True):
        options.add_argument("--headless=new")

    options.add_experimental_option('excludeSwitches', ['enable-logging'])
    options.add_argument('log-level=3')
    options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.5481.177 Safari/537.36")
    options.add_experimental_option('excludeSwitches', ['enable-automation', 'useAutomationExtension'])
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument('--disable-infobars')
    options.add_argument('--disable-notifications')
    options.add_argument('--disable-popup-blocking')
    options.add_argument('--disable-web-security')
    options.add_argument('--ignore-certificate-errors')
    options.add_argument('--window-size=1280,720')
    options.add_argument("--force-device-scale-factor=0.25")
    return options


def build_chrome_service():
    chromedriver_path = resolve_chromedriver_path()
    if chromedriver_path:
        return Service(executable_path=chromedriver_path)
    logger.warning("未找到 ChromeDriver，将尝试由 Selenium Manager 自动解析")
    return Service()


def get_bind_host() -> str:
    host = os.getenv("HOST", "127.0.0.1")
    allow_public_bind = env_bool("ALLOW_PUBLIC_BIND", False)
    if host not in ("127.0.0.1", "localhost", "::1") and not allow_public_bind:
        logger.warning("HOST=%s 被拒绝：如需公网监听请显式设置 ALLOW_PUBLIC_BIND=true，当前改为 127.0.0.1", host)
        return "127.0.0.1"
    return host


def get_bind_port() -> int:
    try:
        return int(os.getenv("PORT", "9844"))
    except ValueError:
        logger.warning("PORT 配置无效，当前使用默认端口 9844")
        return 9844


def get_allowed_origins() -> List[str]:
    origins = os.getenv(
        "CORS_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173,https://spark.aprivity.xyz"
    )
    parsed = [origin.strip() for origin in origins.split(",") if origin.strip()]
    if "*" in parsed:
        logger.warning("CORS_ORIGINS 包含 *，已拒绝任意跨域配置")
        parsed = [origin for origin in parsed if origin != "*"]
    return parsed


def load_admin_config() -> Tuple[str, str]:
    username = os.getenv("ADMIN_USERNAME")
    password = os.getenv("ADMIN_PASSWORD")
    unsafe_passwords = {"123456", "admin", "password", "change-me-now"}

    if not username:
        raise RuntimeError("ADMIN_USERNAME must be set in environment or .env")
    if not password or password in unsafe_passwords:
        raise RuntimeError("ADMIN_PASSWORD must be set to a non-default value")

    if username == "admin":
        logger.warning("ADMIN_USERNAME 仍为 admin，生产环境建议修改")
    return username, password


def unban_config():
    return build_chrome_options()


AIQINGGONGYU_FALLBACK_TEXTS = [
    "今天也要记得续火花呀",
    "别忘了今天的小火花",
    "火花不断，心意常在",
]


def AiqingGongyu_text():
    fallback_text = random.choice(AIQINGGONGYU_FALLBACK_TEXTS)
    try:
        req = requests.get('https://v2.xxapi.cn/api/aiqinggongyu', timeout=5)
        if req.status_code != 200:
            logger.warning("AiqingGongyu_text API returned status %s, using fallback text", req.status_code)
            return fallback_text

        json_data = req.json()
        text = json_data.get('data') if isinstance(json_data, dict) else None
        if text:
            return text

        logger.warning("AiqingGongyu_text API returned empty data, using fallback text")
        return fallback_text
    except (requests.RequestException, ValueError, TypeError) as exc:
        logger.warning("AiqingGongyu_text API failed with %s, using fallback text", exc.__class__.__name__)
        return fallback_text


def Get_Cooke():
    driver.get('https://www.douyin.com/')
    for_OFF = True
    logger.info('请登录抖音并保持浏览器为全屏')
    while for_OFF:
        try:
            # 尝试获取 login_type 元素
            login_type_element = driver.find_element(By.XPATH,
                                                     '/html/body/div[2]/div[1]/div[4]/div[1]/div[1]/header/div/div/div[2]/div/pace-island/div/div[5]/div/div[1]/button/span/p')
        except NoSuchElementException:
            driver.get_cookies()
            logger.info('Cookie 获取成功，已禁止在日志中输出 Cookie 内容')
            driver.close()
            exit()


def format_time(time_str: str) -> str:
    """
    将时间字符串格式化为 HH:MM 格式
    例如: "9:23" -> "09:23", "9:5" -> "09:05", "09:23" -> "09:23"
    """
    if not time_str:
        return '22:00'

    # 统一替换中文冒号
    time_str = time_str.replace('：', ':').strip()

    try:
        # 分割小时和分钟
        parts = time_str.split(':')
        if len(parts) != 2:
            logger.warning('时间格式错误，使用默认时间 22:00')
            return '22:00'

        hour = int(parts[0])
        minute = int(parts[1])

        # 验证范围
        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            logger.warning('时间范围错误，使用默认时间 22:00')
            return '22:00'

        # 格式化为两位数字
        return f"{hour:02d}:{minute:02d}"

    except ValueError:
        logger.warning('时间解析错误，使用默认时间 22:00')
        return '22:00'


class TrueString:
    def __init__(self, is_bool, string):
        self.is_bool = is_bool
        self.string = string


class UserFriendsInfo:
    def __init__(self, username, avatar, fire):
        self.username = username
        self.avatar = avatar
        self.fire = fire


class Douyin:
    friends_xpath_list = {}

    def __init__(self, driver):
        self.driver = driver  # 将 driver 作为实例属性

    def PrintfFrinder(self):
        logger.info('好友列表共获取 %s 位，已禁止在日志中输出好友昵称', len(self.friends_xpath_list))

    def Updara_FrinderList(self):
        friends_xpath = '//div[@class="conversationConversationListwrapper"]/div/div/div'
        msg_main_list = driver.find_elements(By.XPATH, friends_xpath)
        temp_list = []
        for msg_len in range(1, len(msg_main_list) + 1):
            new_xpath = f'//div[@class="conversationConversationListwrapper"]/div/div[{msg_len + 1}]/div[1]/div[2]/div[1]/div[1]'
            avatar_xpath = f'//div[@class="conversationConversationListwrapper"]/div/div[{msg_len + 1}]/div[1]/div[1]/div/span/img'
            avatar_xpath2 = f'//div[@class="conversationConversationListwrapper"]/div/div[{msg_len + 1}]/div/div/img'
            fire_xpath = f'//div[@class="conversationConversationListwrapper"]/div/div[{msg_len + 1}]/div[1]/div[2]/div[1]/div[2]/div[1]/div/div'
            friends_get = driver.find_element(By.XPATH, value=new_xpath)
            friends_text = friends_get.text
            try:
                avatar_get = driver.find_element(By.XPATH, value=avatar_xpath)
                avatar = avatar_get.get_attribute('src')
            except:
                avatar_get = driver.find_element(By.XPATH, value=avatar_xpath2)
                avatar = avatar_get.get_attribute('src')
            self.friends_xpath_list[friends_text] = new_xpath
            try:
                fire_count = driver.find_element(By.XPATH, value=fire_xpath).text.strip()
            except:
                fire_count = ''
            temp_list.append(UserFriendsInfo(friends_text, avatar, fire_count))
        return temp_list

    def Send_Frinder(self, name: str, text: str):
        count = self.Updara_FrinderList()
        if count == 0:
            logger.warning("更新好友列表失败")
        else:
            try:
                for index, value in self.friends_xpath_list.items():
                    if index == name:
                        friend_id = driver.find_element(By.XPATH, value=value)
                        friend_id.click()
                        time.sleep(1.5)
                        seng = driver.find_element(By.XPATH,
                                                   value='//div[@class="messageEditorimChatEditorContainer"]/div/div')
                        seng.send_keys(text)
                        seng.send_keys(Keys.ENTER)
                        return TrueString(True, None)
            except Exception as e:
                return TrueString(False, e)

    def Find_Friends(self, name: str):
        count = self.Updara_FrinderList()
        is_find = False
        if count == 0:
            return TrueString(False, '未初始化好友')
        try:
            for index, value in self.friends_xpath_list.items():
                if index == name:
                    is_find = True
            return TrueString(is_find, None)
        except Exception as e:
            return TrueString(False, e)

    def LoginInit(self):
        try:
            dle_user = driver.find_element(By.XPATH,
                                           value='//*[@id="douyin_login_comp_flat_panel"]/div/div[2]/div/div[4]/p')
            dle_user.click()
        except:
            pass


init = False
Login_is_bool = False
driver = None
douyin = None
app = FastAPI()

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_allowed_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 管理员认证配置。生产环境必须通过环境变量或 .env 设置非默认密码。
_admin_username, _password = load_admin_config()


def cleanup_browser():
    global driver, init, Login_is_bool
    if driver is not None:
        try:
            driver.quit()
            logger.info("浏览器进程已关闭")
        except Exception as exc:
            logger.warning("关闭浏览器进程失败: %s", exc)
        finally:
            driver = None
            init = False
            Login_is_bool = False


atexit.register(cleanup_browser)


def hash_pwd(pwd: str) -> str:
    return hashlib.sha256(pwd.encode()).hexdigest()


# Token存储
_valid_tokens = set()
_last_login_ip = '无'


def generate_token() -> str:
    token = secrets.token_hex(32)
    _valid_tokens.add(token)
    return token


def verify_token(token: str) -> bool:
    return token in _valid_tokens


def remove_token(token: str):
    _valid_tokens.discard(token)


def require_auth(authorization: str = Header(None)):
    if not authorization or not authorization.startswith('Bearer '):
        return {'code': 401, 'data': '未授权'}
    token = authorization[7:]
    if not verify_token(token):
        return {'code': 401, 'data': '未授权'}
    return None


# 定时任务存储
scheduled_tasks = {}  # 格式: {任务ID: job对象}


# 定时线程
def run_schedule():
    """后台线程运行定时任务"""
    while True:
        schedule.run_pending()
        time.sleep(1)


def start_scheduler():
    """启动定时任务调度线程"""
    scheduler_thread = threading.Thread(target=run_schedule, daemon=True)
    scheduler_thread.start()
    return scheduler_thread


start_time = datetime.now()


# 抖音操作
@app.get('/Home')
def Home(authorization: str = Header(None)):
    auth_err = require_auth(authorization)
    if auth_err:
        return auth_err
    return {'time': start_time}


@app.get('/health')
def health():
    return {
        "status": "ok",
        "service": "tiktok-auto-spark-backend"
    }


@app.get('/Api/Init')  # 初始化浏览器
def Init(authorization: str = Header(None)):
    auth_err = require_auth(authorization)
    if auth_err:
        return auth_err

    global init, driver, douyin

    if not init:
        try:
            options = unban_config()
            service = build_chrome_service()
            driver = webdriver.Chrome(service=service, options=options)
            driver.set_window_size(1280, 720)
            driver.get('https://www.douyin.com/chat?isPopup=1 ')
            douyin = Douyin(driver)
            init = True
            start_scheduler()  # 启动调度线程
            return {'code': 200, 'data': 'success'}
        except SessionNotCreatedException as e:
            if "only supports" in str(e):
                return {'code': 400, 'data': '需要更新 Chrome/Chromium 或 ChromeDriver 版本'}
            return {'code': 400, 'data': f'浏览器会话创建失败: {str(e)}'}
        except Exception as e:
            return {'code': 500, 'data': f'初始化失败: {str(e)}'}
    else:
        return {'code': 200, 'data': 'init Repeated!'}


@app.get('/Api/GetInit')  # 获取初始化状态
def GetInit(authorization: str = Header(None)):
    auth_err = require_auth(authorization)
    if auth_err:
        return auth_err
    return {'code': 200, 'data': 'Yes' if init else 'No'}


@app.post('/Api/login')  # 登录 传入cooke
def Login(cooke: str = Body(default=None), gzip_flag: bool = Body(default=False), authorization: str = Header(None)):
    auth_err = require_auth(authorization)
    if auth_err:
        return auth_err
    global Login_is_bool
    if cooke:
        try:
            decoded_bytes = base64.b64decode(cooke)
            if gzip_flag:
                try:
                    decoded_bytes = gzip.decompress(decoded_bytes)
                except Exception:
                    return {'code': '404',
                            'data': 'login-error-gzip decompress failed, check cookie format and gzip flag'}
            cookie_list = decoded_bytes.decode('utf-8')
            str = eval(base64.b64decode(cookie_list).decode('utf-8').replace('false', 'False').replace('true', 'True'))
            for cookie in str:
                driver.add_cookie(cookie)
        except Exception as e:
            return {'code': '404', 'data': f'login-error-cookie parse error: {str(e)}'}
        driver.refresh()
        try:
            login_type_element = driver.find_element(By.XPATH, '//*[@id="douyin_login_comp_flat_panel"]/picture')
            login_type = login_type_element.text
            return {'code': '404', 'data': 'login-error-cooker cant login'}
        except NoSuchElementException:
            Login_is_bool = True
            return {'code': '200', 'data': 'ok'}
    else:
        return {'code': '404', 'data': 'login-error-not cooker'}  # # @#z


@app.get('/Api/Pnglogin')  # 扫码登录
def PngLogin(authorization: str = Header(None)):
    auth_err = require_auth(authorization)
    if auth_err:
        return auth_err
    global Login_is_bool
    cooke = driver.get_cookies()
    if cooke:
        try:
            for cookie in cooke:
                driver.add_cookie(cookie)
        except Exception as e:
            return {'code': '404', 'data': f'login-error-cookie parse error: {str(e)}'}
        driver.refresh()
        try:
            login_type_element = driver.find_element(By.XPATH, '//*[@id="douyin_login_comp_flat_panel"]/picture')
            login_type = login_type_element.text
            driver.refresh()
            return {'code': '404', 'data': '系统繁忙,请稍后重新登录'}
        except NoSuchElementException:
            Login_is_bool = True
            return {'code': '200', 'data': 'ok'}
    else:
        return {'code': '404', 'data': 'login-error-not cooker'}  # # @#z


@app.get('/Api/GetLogin')  # 获取登录
def GetLogin(authorization: str = Header(None)):
    auth_err = require_auth(authorization)
    if auth_err:
        return auth_err
    return {'code': 200, 'data': 'Yes' if Login_is_bool else 'No'}


@app.get('/Api/login/Init/GetLoginPng')  # 获取登录扫码
def GetLoginPng(authorization: str = Header(None)):
    auth_err = require_auth(authorization)
    if auth_err:
        return auth_err
    try:
        Douyin.LoginInit(douyin)
        try:
            error = driver.find_element(By.XPATH, '//*[@id="animate_qrcode_container"]/div[2]/div/p[1]')
            img_element = driver.find_element(By.XPATH, '//*[@id="animate_qrcode_container"]/div[2]/img')
            img_element.click()
        except:
            pass
        img_element = driver.find_element(By.XPATH, '//*[@id="animate_qrcode_container"]/div[2]/img')
        login_src = img_element.get_attribute('src')
        try:
            is_rust = driver.find_element(By.XPATH, '//*[@id="animate_qrcode_container"]/div[2]/div')
            is_rust.click()
            time.sleep(5)
            img_element = driver.find_element(By.XPATH, '//*[@id="animate_qrcode_container"]/div[2]/img')
            login_src = img_element.get_attribute('src')
        except:
            pass
        if login_src:
            return {'code': 200, 'data': login_src}
        else:
            return {'code': 404, 'data': 'cant find LoginPng src attribute'}
    except NoSuchElementException:
        return {'code': 404, 'data': 'cant find img element'}


@app.get('/Api/login/Init/GetCooker')  # 获取cooke
def GetCooke(password: str = Query(None), authorization: str = Header(None)):
    auth_err = require_auth(authorization)
    if auth_err:
        return auth_err
    # 验证密码
    if not password or hash_pwd(password) != hash_pwd(_password):
        return {'code': 400, 'data': '密码错误'}
    if Login_is_bool:
        cooke = driver.get_cookies()
        cookie_json = json.dumps(cooke)
        cookie_base64 = base64.b64encode(cookie_json.encode('utf-8')).decode('utf-8')
        return {'code': 200, 'data': {'cooke': cookie_base64}}
    else:
        return {'code': 400, 'data': '未登录'}


@app.get('/Api/GetFriendsList')  # 获取好友列表
def GetFrindesList(authorization: str = Header(None)):
    auth_err = require_auth(authorization)
    if auth_err:
        return auth_err
    try:
        friends_list = douyin.Updara_FrinderList()
        if len(friends_list) == 0:
            return {'code': 404, 'data': '暂无好友或页面未加载'}
        dicts = {}
        for v in friends_list:
            dicts[v.username] = [v.avatar, v.fire]
        return {'code': 200, 'data': {'count': len(friends_list), 'list': dicts}}
    except Exception as e:
        return {'code': 404, 'data': str(e)}


@app.get('/Api/Send')  # 发送信息
def Send(name: str, text: str, authorization: str = Header(None)):
    auth_err = require_auth(authorization)
    if auth_err:
        return auth_err
    Douyin.Updara_FrinderList(douyin)
    out = Douyin.Send_Frinder(douyin, name, text)
    if out.is_bool:
        return {'code': 200, 'data': 'Send successfully'}
    else:
        return {'code': 404, 'data': out.string}


@app.get('/Api/GetUsername')  # 获取用户名
def GetUserInfo(authorization: str = Header(None)):
    auth_err = require_auth(authorization)
    if auth_err:
        return auth_err
    if Login_is_bool:
        match = re.search(r'\\"nickname\\":\\"([^\\"]+)\\"', driver.page_source)
        if match:
            text = match.group(0)
            clean = text.replace('\\"', '"')
            data = json.loads('{' + clean + '}')
            return {'code': 200, 'data': data['nickname']}
        else:
            return {'code': 400, 'data': '已登录,但未获取到用户名'}
    else:
        return {'code': 400, 'data': '未登录'}


@app.get('/Api/GetScrlk')  # 获取截图
def GetScrlk(authorization: str = Header(None)):
    auth_err = require_auth(authorization)
    if auth_err:
        return auth_err
    try:
        driver.save_screenshot("temp.png")
        with open("temp.png", "rb") as f:
            img_data = base64.b64encode(f.read()).decode('utf-8')
        os.remove("temp.png")
        return {'code': 200, 'data': img_data}
    except Exception as e:
        return {'code': 400, 'data': f'截图错误:{e}'}


@app.get('/Api/DieLogin')  # 取消登录
def DieLogin(authorization: str = Header(None)):
    auth_err = require_auth(authorization)
    if auth_err:
        return auth_err
    driver.delete_all_cookies()
    driver.refresh()
    return {'code': 200, 'data': '已清除Cooke'}


@app.get('/Api/LoginPhone')  # 验证码登录
def authorization(areacode: str, phone: str, authorization: str = Header(None)):
    auth_err = require_auth(authorization)
    if auth_err:
        return auth_err
    try:
        Douyin.LoginInit(douyin)
        areacode_value = driver.find_element(By.XPATH, '//*[@id="douyin_login_comp_normal_input_id"]/div[1]/div/input')
        areacode_value.clear()
        areacode_value.send_keys(areacode.strip())
        inp = driver.find_element(By.XPATH, '//*[@id="normal-input"]')
        inp.send_keys(phone)
        span = driver.find_element(By.XPATH, '//*[@id="douyin_login_comp_button_input_id"]/span')
        span.click()
        time.sleep(2)
        if span.text.strip() == '获取验证码':
            return {'code': 400, 'data': '验证码发送失败'}
        else:
            return {'code': 200, 'data': '验证码发送成功'}
    except Exception as e:
        return {'code': 400, 'data': e}


@app.get('/Api/LoginPhoneInput')  # 验证码登录 2 输入验证码
def authorizations(code: str, authorization: str = Header(None)):
    global Login_is_bool
    auth_err = require_auth(authorization)
    if auth_err:
        return auth_err
    try:
        inp = driver.find_element(By.XPATH, '//*[@id="button-input"]')
        inp.send_keys(code)
        button = driver.find_element(By.XPATH, '//*[@id="douyin_login_comp_btn_id"]')
        button.click()
        time.sleep(2)
        try:
            login_div = driver.find_element(By.XPATH, '//*[@id="douyin_login_comp_flat_panel"]/picture')
            return {'code': 400, 'data': '登录失败'}
        except:
            Login_is_bool = True
            return {'code': 200, 'data': '登录成功'}
    except Exception as e:
        return {'code': 400, 'data': e}


@app.get('/Api/LoginDebug')
def LoginDebug(authorization: str = Header(None)):
    global Login_is_bool
    auth_err = require_auth(authorization)
    if auth_err:
        return auth_err
    if Login_is_bool == False:
        Login_is_bool = True
        return {'code': 200, 'data': 'OK'}
    else:
        return {'code': 400, 'data': '已是登录状态,无需设定'}


# 定时任务操作
@app.get('/Time/add')
def add_time(time: str, name: str, text: str = None, authorization: str = Header(None)):
    auth_err = require_auth(authorization)
    if auth_err:
        return auth_err
    # 检查是否已存在该好友的定时任务
    for task_id, job in scheduled_tasks.items():
        if task_id.endswith(f"_{name}"):
            return {'code': 400, 'data': f'好友 {name} 已有定时任务，请先删除或修改'}

    temp = douyin.Find_Friends(name)
    if temp.is_bool:
        play_time = format_time(time)
        msg = AiqingGongyu_text() if text == None else text
        # 添加定时任务并保存job对象
        job = schedule.every().day.at(play_time).do(douyin.Send_Frinder, name, msg)
        # 生成唯一任务ID
        task_id = f"{play_time}_{name}"
        scheduled_tasks[task_id] = job
        return {'code': 200, 'data': f'已添加定时任务: {play_time}', 'task_id': task_id}
    else:
        return {'code': 404, 'data': temp.string}


@app.get('/Time/del')
def del_time(task_id: str, authorization: str = Header(None)):
    auth_err = require_auth(authorization)
    if auth_err:
        return auth_err
    """根据任务ID删除定时任务"""
    if task_id in scheduled_tasks:
        job = scheduled_tasks[task_id]
        schedule.cancel_job(job)
        del scheduled_tasks[task_id]
        return {'code': 200, 'data': f'已删除任务: {task_id}'}
    else:
        return {'code': 404, 'data': '任务ID不存在'}


@app.get('/Time/edit')
def edit_time(name: str, new_time: str, authorization: str = Header(None)):
    auth_err = require_auth(authorization)
    if auth_err:
        return auth_err
    """修改指定好友的定时任务时间"""
    # 查找该好友的现有任务
    old_task_id = None
    for task_id, job in scheduled_tasks.items():
        if task_id.endswith(f"_{name}"):
            old_task_id = task_id
            break

    if not old_task_id:
        return {'code': 404, 'data': f'好友 {name} 没有定时任务'}

    # 取消旧任务
    old_job = scheduled_tasks[old_task_id]
    schedule.cancel_job(old_job)

    # 解析旧任务信息
    parts = old_task_id.split('_', 1)
    old_time = parts[0] if len(parts) == 2 else ""

    # 创建新任务
    new_play_time = format_time(new_time)
    try:
        msg = AiqingGongyu_text()  # 获取新的名言
    except Exception as exc:
        logger.warning("edit_time ignored text API failure: %s", exc.__class__.__name__)
        msg = random.choice(AIQINGGONGYU_FALLBACK_TEXTS)
    new_job = schedule.every().day.at(new_play_time).do(douyin.Send_Frinder, name, msg)

    # 生成新任务ID并替换
    new_task_id = f"{new_play_time}_{name}"
    scheduled_tasks[new_task_id] = new_job
    del scheduled_tasks[old_task_id]

    return {
        'code': 200,
        'data': f'已将 {name} 的定时任务从 {old_time} 修改为 {new_play_time}',
        'old_time': old_time,
        'new_time': new_play_time,
        'task_id': new_task_id
    }


@app.get('/Time/getlist')
def get_time_list(authorization: str = Header(None)):
    auth_err = require_auth(authorization)
    if auth_err:
        return auth_err
    """获取当前所有定时任务列表"""
    tasks = []
    for task_id, job in scheduled_tasks.items():
        # 解析任务ID获取信息
        parts = task_id.split('_', 1)
        if len(parts) == 2:
            time_str, name = parts
            tasks.append({
                'task_id': task_id,
                'time': time_str,
                'name': name,
                'next_run': str(job.next_run) if job.next_run else None
            })
    return {'code': 200, 'data': {'count': len(tasks), 'tasks': tasks}}


# 后台登录
@app.get('/Api/Login/Admin')
def admin_login(username: str, password: str, request: Request = None):
    global _last_login_ip
    if username == _admin_username and hash_pwd(password) == hash_pwd(_password):
        _last_login_ip = request.client.host if request else '127.0.0.1'
        token = generate_token()
        return {'code': 200, 'data': token}
    else:
        return {'code': 400, 'data': '登录失败'}


@app.get('/Api/GetLastLoginIP')
def get_last_login_ip(authorization: str = Header(None)):
    auth_err = require_auth(authorization)
    if auth_err:
        return auth_err
    return {'code': 200, 'data': _last_login_ip}


# 退出登录
@app.get('/Api/logout')
def logout(authorization: str = Header(None)):
    auth_err = require_auth(authorization)
    if auth_err:
        return auth_err
    token = authorization[7:]
    remove_token(token)
    return {'code': 200, 'data': '已退出登录'}


# 密码修改
@app.get('/Api/ChangePassword')
def change_password(old_password: str, new_password: str, authorization: str = Header(None)):
    auth_err = require_auth(authorization)
    if auth_err:
        return auth_err
    global _password
    if hash_pwd(old_password) != hash_pwd(_password):
        return {'code': 400, 'data': '原密码错误'}
    _password = new_password
    return {'code': 200, 'data': '密码修改成功'}


if __name__ == "__main__":
    bind_host = get_bind_host()
    bind_port = get_bind_port()
    logger.info("启动 tiktok-auto-spark-backend，监听 %s:%s", bind_host, bind_port)
    uvicorn.run(
        app,
        host=bind_host,
        port=bind_port,
        reload=False
    )
