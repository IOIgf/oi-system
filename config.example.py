# config.example.py - 复制为 config.py 后填写
import os
from dotenv import load_dotenv

load_dotenv()

# ===== DeepSeek API =====
# 请到 https://platform.deepseek.com/ 获取
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "your-api-key-here")
DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"

# ===== 洛谷 Cookie =====
# 留空即可，程序会自动从 Chrome 读取（需先在 Chrome 中登录洛谷）
# 如果自动读取失败，可以手动填写，格式: "_uid=xxx; __client_id=xxx"
LUOGU_COOKIE = os.getenv("LUOGU_COOKIE", "")

# ===== 请求间隔 =====
REQUEST_INTERVAL = 1.5