# -*- coding: utf-8 -*-
import re
import json
import time
import urllib.parse
import requests
from bs4 import BeautifulSoup
from typing import List, Dict, Any
from config import REQUEST_INTERVAL
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import sys
import os
import tempfile
from datetime import datetime

# ==================== Selenium Cookie 读取（全局缓存） ====================
_SELENIUM_COOKIE_CACHE = {}

def get_cookie_from_chrome(domain: str) -> str:
    if domain in _SELENIUM_COOKIE_CACHE:
        return _SELENIUM_COOKIE_CACHE[domain]

    if len(_SELENIUM_COOKIE_CACHE) >= 2:
        return _SELENIUM_COOKIE_CACHE.get(domain)

    domains = ['www.luogu.com.cn', 'atcoder.jp']
    print("🚀 正在启动 Selenium 读取 Cookie...")
    import os
    import tempfile
    from selenium.common.exceptions import WebDriverException
    from webdriver_manager.chrome import ChromeDriverManager

    os.environ['WDM_LOG_LEVEL'] = '0'
    os.environ['WDM_PRINT_FIRST_LINE'] = 'False'

    user_data_dir = os.path.expanduser('~') + '/AppData/Local/Google/Chrome/User Data'
    if not os.path.exists(user_data_dir):
        user_data_dir = tempfile.mkdtemp()

    options = Options()
    options.add_argument('--headless')
    options.add_argument('--disable-gpu')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-logging')
    options.add_argument('--log-level=3')
    options.add_argument('--silent')
    options.add_argument('--remote-debugging-port=0')
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_experimental_option('excludeSwitches', ['enable-logging'])
    options.add_argument(f'--user-data-dir={user_data_dir}')
    options.add_argument('--profile-directory=Default')

    try:
        if getattr(sys, 'frozen', False):
            base_dir = os.path.dirname(sys.executable)
            local_driver = os.path.join(base_dir, 'chromedriver.exe')
            if os.path.exists(local_driver):
                service = Service(local_driver)
            else:
                service = Service(ChromeDriverManager().install())
        else:
            service = Service(ChromeDriverManager().install())

        service.creation_flags = 0x08000000
        driver = webdriver.Chrome(service=service, options=options)

        for d in domains:
            driver.get(f'https://{d}')
            time.sleep(1.5)
            cookies = driver.get_cookies()
            if cookies:
                cookie_str = "; ".join([f"{c['name']}={c['value']}" for c in cookies])
                _SELENIUM_COOKIE_CACHE[d] = cookie_str
        driver.quit()
        print("✅ Selenium 读取 Cookie 完成")
        return _SELENIUM_COOKIE_CACHE.get(domain)

    except Exception as e:
        print(f"⚠️ Selenium 读取 Cookie 失败: {e}")
        return None


# ==================== 洛谷爬虫 ====================
class LuoguCrawler:
    _cached_cookie = None
    _cookie_printed = False
    _cookie_read_attempted = False
    _problem_cache = {}
    _tag_map_cache = None
    _algorithm_tag_ids = None
    _problem_title_cache = {}  # 新增：题目名称缓存

    def __init__(self, cookie: str = None):
        self.session = requests.Session()
        self.session.proxies = {}
        self.session.trust_env = False
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Referer": "https://www.luogu.com.cn/",
        })

        if cookie:
            self._set_cookie_from_string(cookie)
            return

        if LuoguCrawler._cached_cookie:
            self._set_cookie_from_string(LuoguCrawler._cached_cookie)
            return

        if LuoguCrawler._cookie_read_attempted:
            return

        LuoguCrawler._cookie_read_attempted = True

        cookie_str = get_cookie_from_chrome('www.luogu.com.cn')
        if cookie_str:
            LuoguCrawler._cached_cookie = cookie_str
            self._set_cookie_from_string(cookie_str)
            if not LuoguCrawler._cookie_printed:
                print("✅ 已通过 Selenium 读取洛谷 Cookie")
                LuoguCrawler._cookie_printed = True
            return

        print("⚠️ 未获取到洛谷 Cookie，请确保 Chrome 已登录洛谷")
        print("   或手动在 config.py 中配置 LUOGU_COOKIE")

    def _set_cookie_from_string(self, cookie_str: str):
        cookie_dict = {}
        for item in cookie_str.split(';'):
            item = item.strip()
            if not item or '=' not in item:
                continue
            key, value = item.split('=', 1)
            cookie_dict[key] = value
        self.session.cookies.update(cookie_dict)

    # ==================== 难度映射 ====================
    @staticmethod
    def _get_difficulty_name(code: int) -> str:
        map_ = {
            0: "暂无评定", 1: "入门", 2: "普及-", 3: "普及",
            4: "普及+/提高-", 5: "提高", 6: "提高+/省选-",
            7: "省选/NOI-", 8: "NOI/NOI+/CTS"
        }
        return map_.get(code, f"未知({code})")

    # ==================== 等级分 ====================
    def get_user_elo(self, uid: str) -> Dict[str, Any]:
        url = f"https://www.luogu.com.cn/user/{uid}/practice"
        try:
            resp = self.session.get(url, timeout=10)
            if resp.status_code != 200:
                return {}
            soup = BeautifulSoup(resp.text, "html.parser")
            script_tag = soup.find("script", id="lentille-context")
            if not script_tag:
                return {}
            data = json.loads(script_tag.string)
            elo_data = data.get("data", {}).get("elo", [])
            if not elo_data:
                return {}
            return {"history": elo_data, "latest": elo_data[-1] if elo_data else None}
        except Exception as e:
            print(f"获取等级分异常: {e}")
            return {}

    # ==================== 比赛信息 ====================
    def get_contest_info(self, contest_id: str) -> Dict[str, Any]:
        url = f"https://www.luogu.com.cn/contest/{contest_id}"
        headers = {"x-lentille-request": "content-only", "Referer": "https://www.luogu.com.cn/"}
        try:
            resp = self.session.get(url, headers=headers, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("status") == 200:
                    contest = data.get("data", {}).get("contest", {})
                    return {
                        "id": contest_id,
                        "name": contest.get("name", ""),
                        "startTime": contest.get("startTime"),
                        "endTime": contest.get("endTime"),
                    }
        except Exception as e:
            print(f"获取比赛 {contest_id} 信息失败: {e}")
        return {"id": contest_id, "name": f"比赛 {contest_id}"}

    # ==================== 比赛提交记录（优先 JSON，失败时回退 HTML） ====================
    def get_contest_submissions(self, uid: str, contest_id: str) -> List[Dict[str, Any]]:
        all_submissions = []
        page = 1
        max_pages = 5

        while page <= max_pages:
            url = f"https://www.luogu.com.cn/record/list?user={uid}&contestId={contest_id}&page={page}"
            try:
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
                    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                    "Referer": "https://www.luogu.com.cn/",
                    "Connection": "keep-alive",
                    "Upgrade-Insecure-Requests": "1",
                }
                resp = self.session.get(url, headers=headers, timeout=10)
                if resp.status_code != 200:
                    break

                soup = BeautifulSoup(resp.text, "html.parser")

                script_tag = None
                for script in soup.find_all("script"):
                    if script.string and "window._feInjection" in script.string:
                        script_tag = script
                        break

                data = None
                if script_tag:
                    script_content = script_tag.string
                    patterns = [
                        r'decodeURIComponent\("(.*?)"\)',
                        r"decodeURIComponent\(%22(.*?)%22\)",
                        r"window\._feInjection\s*=\s*(\{.*?\});"
                    ]
                    for pattern in patterns:
                        match = re.search(pattern, script_content, re.DOTALL)
                        if match:
                            try:
                                json_str = urllib.parse.unquote(match.group(1))
                                data = json.loads(json_str)
                                break
                            except:
                                continue
                    if not data:
                        match = re.search(r'JSON\.parse\(decodeURIComponent\(%22(.*?)%22\)\)', script_content)
                        if match:
                            try:
                                json_str = urllib.parse.unquote(match.group(1))
                                data = json.loads(json_str)
                            except:
                                pass

                if data:
                    records_data = data.get("currentData", {}).get("records", {}).get("result", [])
                    if records_data:
                        status_map = {
                            12: "AC", 13: "WA", 14: "WA", 15: "TLE", 16: "MLE",
                            17: "RE", 18: "CE", 19: "UKE", 20: "OLE", 21: "PC", 11: "AC"
                        }
                        for item in records_data:
                            pid = item.get("problem", {}).get("pid")
                            if not pid:
                                continue
                            status_code = item.get("status")
                            status_text = status_map.get(status_code, str(status_code))
                            score = item.get("score") or 0
                            submit_time = item.get("submitTime")
                            full_score = item.get("problem", {}).get("fullScore") or 0
                            all_submissions.append({
                                "pid": pid,
                                "status": status_text,
                                "score": score,
                                "submitTime": submit_time,
                                "fullScore": full_score,
                            })

                        per_page = data.get("currentData", {}).get("records", {}).get("perPage")
                        total_count = data.get("currentData", {}).get("records", {}).get("count")
                        if per_page is None:
                            per_page = 20
                        if total_count is None:
                            if len(records_data) < per_page:
                                break
                            page += 1
                            continue
                        if page * per_page >= total_count:
                            break
                        page += 1
                        time.sleep(0.1)
                        continue

                table = soup.find("table", class_=re.compile(r"table"))
                if not table:
                    break
                tbody = table.find("tbody")
                if not tbody:
                    break
                rows = tbody.find_all("tr")
                if not rows:
                    break

                status_map_html = {
                    "Accepted": "AC", "AC": "AC",
                    "Wrong Answer": "WA", "WA": "WA",
                    "Time Limit Exceeded": "TLE", "TLE": "TLE",
                    "Memory Limit Exceeded": "MLE", "MLE": "MLE",
                    "Runtime Error": "RE", "RE": "RE",
                    "Compile Error": "CE", "CE": "CE",
                    "Unkown Error": "UKE", "UKE": "UKE",
                    "Output Limit Exceeded": "OLE", "OLE": "OLE",
                    "Pending": "Pending",
                    "Judging": "Judging",
                }

                for tr in rows:
                    tds = tr.find_all("td")
                    if len(tds) < 7:
                        continue
                    problem_td = tds[1] if len(tds) > 1 else None
                    if not problem_td:
                        continue
                    link = problem_td.find("a")
                    pid = link.text.strip() if link else problem_td.text.strip()

                    status_td = tds[2] if len(tds) > 2 else None
                    if status_td:
                        status_link = status_td.find("a")
                        status_text = status_link.text.strip() if status_link else status_td.text.strip()
                        status = status_map_html.get(status_text, status_text)
                    else:
                        status = "Unknown"

                    score = 0
                    if status == "AC":
                        score = 100
                    elif status_td:
                        match = re.search(r"(\d+)", status_td.text.strip())
                        if match:
                            score = int(match.group(1))

                    time_td = tds[6] if len(tds) > 6 else None
                    submit_time = time_td.text.strip() if time_td else ""

                    all_submissions.append({
                        "pid": pid,
                        "status": status,
                        "score": score,
                        "submitTime": submit_time,
                        "fullScore": 100,
                    })

                next_link = soup.find("a", class_="next")
                if not next_link:
                    break
                page += 1
                time.sleep(0.1)

            except Exception as e:
                print(f"获取比赛 {contest_id} 第 {page} 页异常: {e}")
                break

        return all_submissions

    # ==================== 比赛题目列表 ====================
    def get_contest_problems(self, contest_id: str) -> Dict[str, Any]:
        url = f"https://www.luogu.com.cn/contest/{contest_id}"
        headers = {"x-lentille-request": "content-only", "Referer": "https://www.luogu.com.cn/"}
        try:
            resp = self.session.get(url, headers=headers, timeout=10)
            if resp.status_code != 200:
                return {"total": 0, "problems": []}
            data = resp.json()
            if data.get("status") != 200:
                return {"total": 0, "problems": []}

            contest_data = data.get("data", {})
            total = contest_data.get("contest", {}).get("problemCount", 0)
            problems_data = contest_data.get("contestProblems", [])

            problems = []
            for p in problems_data:
                problem = p.get("problem", {})
                problems.append({
                    "pid": problem.get("pid"),
                    "fullScore": p.get("score", 0),
                    "title": problem.get("name", ""),
                    "difficulty": self._get_difficulty_name(problem.get("difficulty", 0)),
                })
            return {"total": total, "problems": problems}
        except Exception as e:
            print(f"获取比赛 {contest_id} 题目列表异常: {e}")
            return {"total": 0, "problems": []}

    # ==================== 奖项 ====================
    def get_user_awards(self, uid: str) -> List[str]:
        url = f"https://www.luogu.com.cn/user/{uid}"
        headers = {"x-lentille-request": "content-only", "Referer": "https://www.luogu.com.cn/"}
        try:
            resp = self.session.get(url, headers=headers, timeout=10)
            if resp.status_code != 200:
                return []
            data = resp.json()
            if data.get("status") != 200:
                return []

            prizes_data = data.get("data", {}).get("prizes", [])
            awards = []
            for p in prizes_data:
                if isinstance(p, dict):
                    prize_info = p.get("prize")
                    if isinstance(prize_info, dict):
                        name = prize_info.get("prize")
                        if name:
                            year = prize_info.get("year")
                            contest = prize_info.get("contest")
                            if year and contest:
                                awards.append(f"{year} {contest} {name}")
                            else:
                                awards.append(name)
            return awards
        except Exception as e:
            print(f"获取洛谷奖项异常: {e}")
            return []

    # ==================== 标签映射 ====================
    def _ensure_tag_map(self):
        if LuoguCrawler._tag_map_cache is not None:
            return
        url = "https://www.luogu.com.cn/_lfe/tags/zh-CN"
        try:
            resp = self.session.get(url, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                tags_list = data.get("tags", [])
                tag_map = {}
                algorithm_ids = set()
                for item in tags_list:
                    if isinstance(item, dict):
                        tag_id = item.get("id")
                        name = item.get("name")
                        tag_type = item.get("type")
                        if tag_id is not None and name:
                            tag_map[int(tag_id)] = name
                            if tag_type == 2:
                                algorithm_ids.add(int(tag_id))
                LuoguCrawler._tag_map_cache = tag_map
                LuoguCrawler._algorithm_tag_ids = algorithm_ids
        except Exception as e:
            print(f"获取标签映射失败: {e}")

    # ==================== 题目标签 ====================
    def get_problem_tags(self, pid: str, contest_id: str = None) -> List[str]:
        cache_key = f"{pid}_{contest_id}" if contest_id else pid

        if cache_key in LuoguCrawler._problem_cache:
            return LuoguCrawler._problem_cache[cache_key]

        url = f"https://www.luogu.com.cn/problem/{pid}"
        if contest_id:
            url += f"?contestId={contest_id}"

        headers = {"x-lentille-request": "content-only", "Referer": "https://www.luogu.com.cn/"}
        try:
            resp = self.session.get(url, headers=headers, timeout=10)
            if resp.status_code != 200:
                return []

            data = resp.json()
            if data.get("status") != 200:
                return []

            tags = data.get("data", {}).get("problem", {}).get("tags", [])
            if not tags:
                LuoguCrawler._problem_cache[cache_key] = []
                return []

            self._ensure_tag_map()
            algorithm_ids = LuoguCrawler._algorithm_tag_ids or set()
            tag_map = LuoguCrawler._tag_map_cache or {}

            tag_names = []
            for tag_id in tags:
                if isinstance(tag_id, int):
                    if tag_id in algorithm_ids:
                        name = tag_map.get(tag_id)
                        if name:
                            tag_names.append(name)
                elif isinstance(tag_id, str) and tag_id.isdigit():
                    tid = int(tag_id)
                    if tid in algorithm_ids:
                        name = tag_map.get(tid)
                        if name:
                            tag_names.append(name)
                elif isinstance(tag_id, str):
                    tag_names.append(tag_id)

            LuoguCrawler._problem_cache[cache_key] = tag_names
            return tag_names
        except Exception as e:
            print(f"获取题目 {pid} 标签异常: {e}")
            return []

    # ==================== 通过题目统计 ====================
    def get_user_passed_problems(self, uid: str) -> Dict[str, Any]:
        url = f"https://www.luogu.com.cn/user/{uid}/practice"
        try:
            resp = self.session.get(url, timeout=10)
            if resp.status_code != 200:
                return {"total": 0, "by_difficulty": {}, "problems": []}

            soup = BeautifulSoup(resp.text, "html.parser")
            script_tag = soup.find("script", id="lentille-context")
            if not script_tag:
                return {"total": 0, "by_difficulty": {}, "problems": []}

            data = json.loads(script_tag.string)
            data_obj = data.get("data", {})

            passed_data = None
            candidates = ["passed", "passedProblems", "accepted", "problems"]
            for key in candidates:
                if key in data_obj and isinstance(data_obj[key], list) and len(data_obj[key]) > 0:
                    passed_data = data_obj[key]
                    break

            if not passed_data:
                for k, v in data_obj.items():
                    if isinstance(v, dict):
                        for sub_k, sub_v in v.items():
                            if isinstance(sub_v, list) and len(sub_v) > 0 and "pid" in sub_v[0]:
                                passed_data = sub_v
                                break
                    if passed_data:
                        break

            if not passed_data:
                return {"total": 0, "by_difficulty": {}, "problems": []}

            by_difficulty = {}
            problems = []
            for item in passed_data:
                if "problem" in item and isinstance(item["problem"], dict):
                    prob = item["problem"]
                    diff_code = prob.get("difficulty", 0)
                    pid = prob.get("pid")
                else:
                    diff_code = item.get("difficulty", 0)
                    pid = item.get("pid")
                if not pid:
                    continue
                diff_name = self._get_difficulty_name(diff_code)
                problems.append({"pid": pid, "difficulty": diff_name})
                by_difficulty[diff_name] = by_difficulty.get(diff_name, 0) + 1

            order = ["入门", "普及-", "普及", "普及+/提高-", "提高", "提高+/省选-", "省选/NOI-", "NOI/NOI+/CTS", "暂无评定"]
            sorted_by_difficulty = {k: by_difficulty[k] for k in order if k in by_difficulty}
            for k, v in by_difficulty.items():
                if k not in sorted_by_difficulty:
                    sorted_by_difficulty[k] = v

            return {
                "total": len(problems),
                "by_difficulty": sorted_by_difficulty,
                "problems": problems
            }
        except Exception as e:
            print(f"获取通过题目统计异常: {e}")
            return {"total": 0, "by_difficulty": {}, "problems": []}

    # ==================== 新增：获取题目真实名称 ====================
    def get_problem_title(self, pid: str) -> str:
        """
        根据题号获取题目名称（带缓存）
        """
        if pid in LuoguCrawler._problem_title_cache:
            return LuoguCrawler._problem_title_cache[pid]

        url = f"https://www.luogu.com.cn/problem/{pid}"
        headers = {"x-lentille-request": "content-only", "Referer": "https://www.luogu.com.cn/"}
        try:
            resp = self.session.get(url, headers=headers, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("status") == 200:
                    title = data.get("data", {}).get("problem", {}).get("name", "")
                    if title:
                        LuoguCrawler._problem_title_cache[pid] = title
                        return title
        except Exception as e:
            print(f"获取题目 {pid} 名称失败: {e}")
        # 如果获取失败，返回题号本身
        LuoguCrawler._problem_title_cache[pid] = pid
        return pid
    def get_upcoming_contests(self) -> List[Dict[str, Any]]:
        url = "https://www.luogu.com.cn/contest/list"
        headers = {"x-lentille-request": "content-only", "Referer": "https://www.luogu.com.cn/"}
        try:
            resp = self.session.get(url, headers=headers, timeout=10)
            if resp.status_code != 200:
                return []
            data = resp.json()
            if data.get("status") != 200:
                return []
            contests = data.get("data", {}).get("contests", {}).get("result", [])
            result = []
            now = time.time()
            for c in contests:
                start_time = c.get("startTime")
                if start_time and start_time > now:
                    result.append({
                        "id": c.get("id"),
                        "name": c.get("name"),
                        "startTime": start_time,
                        "endTime": c.get("endTime"),
                        "platform": "洛谷",
                        "url": f"https://www.luogu.com.cn/contest/{c.get('id')}",
                        "problemCount": c.get("problemCount", 0)
                    })
            # 按开始时间升序（最近的在最前）
            result.sort(key=lambda x: x["startTime"])
            return result[:20]
        except Exception as e:
            print(f"获取洛谷比赛列表失败: {e}")
            return []

# ==================== AtCoder 爬虫 ====================
class AtCoderCrawler:
    _cached_cookie = None
    _cookie_printed = False
    _cookie_read_attempted = False

    def __init__(self, cookie: str = None):
        self.session = requests.Session()
        self.session.proxies = {}
        self.session.trust_env = False
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Referer": "https://atcoder.jp/",
        })

        if cookie:
            self._set_cookie_from_string(cookie)
            return

        if AtCoderCrawler._cached_cookie:
            self._set_cookie_from_string(AtCoderCrawler._cached_cookie)
            return

        if AtCoderCrawler._cookie_read_attempted:
            return

        AtCoderCrawler._cookie_read_attempted = True

        cookie_str = get_cookie_from_chrome('atcoder.jp')
        if cookie_str:
            AtCoderCrawler._cached_cookie = cookie_str
            self._set_cookie_from_string(cookie_str)
            if not AtCoderCrawler._cookie_printed:
                print("✅ 已通过 Selenium 读取 AtCoder Cookie")
                AtCoderCrawler._cookie_printed = True
            return

        print("⚠️ 未获取到 AtCoder Cookie，请确保 Chrome 已登录 AtCoder")
        print("   或手动在 config.py 中配置 LUOGU_COOKIE")

    def _set_cookie_from_string(self, cookie_str: str):
        cookie_dict = {}
        for item in cookie_str.split(';'):
            item = item.strip()
            if not item or '=' not in item:
                continue
            key, value = item.split('=', 1)
            cookie_dict[key] = value
        self.session.cookies.update(cookie_dict)

    def _get_rank_by_rating(self, rating: int) -> str:
        if rating >= 2800:
            return "Red"
        elif rating >= 2400:
            return "Orange"
        elif rating >= 2000:
            return "Gold"
        elif rating >= 1600:
            return "Blue"
        elif rating >= 1200:
            return "Cyan"
        elif rating >= 800:
            return "Green"
        elif rating >= 400:
            return "Brown"
        else:
            return "Grey"

    def get_user_rating_info(self, username: str) -> Dict[str, str]:
        history_url = f"https://atcoder.jp/users/{username}/history/json"
        try:
            resp = self.session.get(history_url, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                if data:
                    latest = data[-1]
                    rating = latest.get("rating")
                    if rating is not None:
                        return {"rating": str(rating), "rank": self._get_rank_by_rating(rating)}
                    if "NewRating" in latest:
                        rating = latest["NewRating"]
                        if rating is not None:
                            return {"rating": str(rating), "rank": self._get_rank_by_rating(rating)}
        except Exception as e:
            print(f"从 history API 获取评级失败: {e}")

        url = f"https://atcoder.jp/users/{username}"
        try:
            resp = self.session.get(url, timeout=10)
            if resp.status_code != 200:
                return {"rating": "N/A", "rank": "N/A"}
            soup = BeautifulSoup(resp.text, "html.parser")
            rating_elem = soup.find("span", class_="rating")
            if not rating_elem:
                rating_elem = soup.find("span", class_=re.compile(r"rating"))
            if rating_elem:
                rating_text = rating_elem.text.strip()
                match = re.search(r"(\d+)", rating_text)
                if match:
                    rating = int(match.group(1))
                    return {"rating": str(rating), "rank": self._get_rank_by_rating(rating)}
            for td in soup.find_all("td"):
                if "Rating:" in td.text:
                    next_td = td.find_next("td")
                    if next_td:
                        rating_str = next_td.text.strip()
                        match = re.search(r"(\d+)", rating_str)
                        if match:
                            rating = int(match.group(1))
                            return {"rating": str(rating), "rank": self._get_rank_by_rating(rating)}
            return {"rating": "N/A", "rank": "N/A"}
        except Exception as e:
            print(f"获取 AtCoder 评级失败: {e}")
            return {"rating": "N/A", "rank": "N/A"}

    def get_contest_tasks(self, contest_id: str) -> List[Dict[str, str]]:
        url = f"https://atcoder.jp/contests/{contest_id}/tasks"
        try:
            resp = self.session.get(url, timeout=10)
            if resp.status_code != 200:
                return []
            soup = BeautifulSoup(resp.text, "html.parser")
            table = soup.select_one("#main-container table")
            if not table:
                return []
            tasks = []
            for row in table.find_all("tr")[1:]:
                cols = row.find_all("td")
                if len(cols) >= 2:
                    link = cols[0].find("a")
                    if link:
                        pid = link.get("href", "").split("/")[-1]
                        tasks.append({
                            "pid": pid,
                            "title": link.text.strip(),
                        })
            return tasks
        except Exception as e:
            print(f"获取 AtCoder 比赛 {contest_id} 题目列表失败: {e}")
            return []

    def _get_contest_standings(self, contest_id: str, retries: int = 3) -> Dict[str, Any]:
        url = f"https://atcoder.jp/contests/{contest_id}/standings/json"
        for attempt in range(retries):
            try:
                resp = self.session.get(url, timeout=10)
                if resp.status_code == 429:
                    wait = (attempt + 1) * 2
                    print(f"  [限流] 比赛 {contest_id} 被限流，等待 {wait} 秒后重试 ({attempt+1}/{retries})")
                    time.sleep(wait)
                    continue
                if resp.status_code != 200:
                    return {}
                try:
                    return resp.json()
                except ValueError:
                    return {}
            except Exception as e:
                if attempt == retries - 1:
                    print(f"  [错误] 比赛 {contest_id} 请求失败: {e}")
                time.sleep(1)
        return {}

    def get_user_contests(self, username: str, max_workers: int = 1) -> List[Dict[str, Any]]:
        url = f"https://atcoder.jp/users/{username}/history/json"
        try:
            resp = self.session.get(url, timeout=10)
            if resp.status_code != 200:
                return []
            history = resp.json()
        except Exception as e:
            print(f"获取 AtCoder 比赛历史失败: {e}")
            return []

        def process_contest(item):
            contest_name = item.get("ContestName") or item.get("contest_name") or item.get("ContestNameEn") or ""
            contest_id_raw = item.get("ContestScreenName")
            if contest_id_raw:
                contest_id = contest_id_raw.split(".")[0] if ".contest.atcoder.jp" in contest_id_raw else contest_id_raw
            else:
                contest_id = None

            rank = item.get("Place") or item.get("rank")
            rating = item.get("NewRating") or item.get("rating") or item.get("Performance")
            if rank is None and "Place" in item:
                rank = item["Place"]
            if rating is None and "OldRating" in item:
                rating = item["OldRating"]

            problems = {}
            total_problems = 0
            if contest_id:
                tasks = self.get_contest_tasks(contest_id)
                total_problems = len(tasks)

                standings = self._get_contest_standings(contest_id)
                if standings and "StandingsData" in standings:
                    target_username_lower = username.lower()
                    for entry in standings["StandingsData"]:
                        if entry.get("UserScreenName", "").lower() == target_username_lower:
                            task_results = entry.get("TaskResults", {})
                            if not task_results:
                                return None
                            for task_key, task_val in task_results.items():
                                status_code = task_val.get("Status")
                                score = task_val.get("Score", 0) // 100
                                if status_code == 1:
                                    status = "AC"
                                elif status_code == 2:
                                    status = "WA"
                                elif status_code == 0:
                                    status = "未提交"
                                else:
                                    if score > 0:
                                        status = "AC"
                                    else:
                                        status = "WA"
                                problems[task_key] = {"status": status, "score": score}
                            break
                    else:
                        return None
                else:
                    return None
            else:
                return None

            return {
                "contest_name": contest_name,
                "contest_id": contest_id,
                "rank": rank,
                "rating": rating,
                "problems": problems,
                "total_problems": total_problems,
                "end_time": item.get("EndTime"),
            }

        from concurrent.futures import ThreadPoolExecutor, as_completed
        results = []
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(process_contest, item) for item in history]
            for future in as_completed(futures):
                try:
                    result = future.result()
                    if result:
                        results.append(result)
                except Exception as e:
                    print(f"处理 AtCoder 比赛时出错: {e}")

        result_map = {r["contest_id"]: r for r in results if r["contest_id"]}
        ordered_results = []
        for item in history:
            cid_raw = item.get("ContestScreenName")
            if cid_raw:
                cid = cid_raw.split(".")[0] if ".contest.atcoder.jp" in cid_raw else cid_raw
            else:
                cid = None
            if cid in result_map:
                ordered_results.append(result_map[cid])
        return ordered_results
    def get_upcoming_contests(self) -> List[Dict[str, Any]]:
        """获取 AtCoder 即将开始的比赛（增加详细调试）"""
        url = "https://atcoder.jp/contests"
        try:
            resp = self.session.get(url, timeout=10)
            print(f"[AT] 状态码: {resp.status_code}")
            print(f"[AT] 响应长度: {len(resp.text)}")
            if resp.status_code != 200:
                return []
            
            soup = BeautifulSoup(resp.text, "html.parser")
            
            # 定位 upcoming 表格（多种方式）
            table = None
            # 方式1: 通过 id
            table = soup.find("div", id="contest-table-upcoming")
            if not table:
                # 方式2: 通过 class
                table = soup.find("div", class_="contest-table-upcoming")
            if not table:
                # 方式3: 查找包含 "Upcoming Contests" 的 panel
                for panel in soup.find_all("div", class_="panel"):
                    if panel.find("h3") and "Upcoming Contests" in panel.find("h3").text:
                        table = panel
                        break
            if not table:
                print("[AT] 未找到 upcoming 表格")
                return []
            
            print("[AT] 找到 upcoming 表格")
            tbody = table.find("tbody")
            if not tbody:
                print("[AT] 未找到 tbody")
                return []
            
            rows = tbody.find_all("tr")
            print(f"[AT] 找到 {len(rows)} 行")
            
            result = []
            now = time.time()
            
            for row in rows:
                cols = row.find_all("td")
                if len(cols) < 3:
                    continue
                
                # 时间列
                time_text = cols[0].text.strip()
                # 名称列
                name_link = cols[1].find("a")
                if not name_link:
                    continue
                name = name_link.text.strip()
                href = name_link.get("href")
                contest_id = href.split("/")[-1] if href else ""
                
                # 解析开始时间
                try:
                    # 处理时区
                    if "+" in time_text:
                        time_text_clean = time_text.split("+")[0]
                    else:
                        time_text_clean = time_text[:19]
                    start_time = int(datetime.strptime(time_text_clean, "%Y-%m-%d %H:%M:%S").timestamp())
                except Exception as e:
                    print(f"[AT] 时间解析失败: '{time_text}', 错误: {e}")
                    continue
                
                if start_time <= now:
                    continue
                
                # 获取题目数（可选）
                problem_count = 0
                try:
                    tasks = self.get_contest_tasks(contest_id)
                    problem_count = len(tasks)
                except Exception as e:
                    print(f"[AT] 获取题目数失败 {contest_id}: {e}")
                
                result.append({
                    "id": contest_id,
                    "name": name,
                    "startTime": start_time,
                    "endTime": None,
                    "platform": "AtCoder",
                    "url": f"https://atcoder.jp{href}",
                    "problemCount": problem_count
                })
            
            result.sort(key=lambda x: x["startTime"])
            print(f"[AT] 获取到 {len(result)} 场即将开始的比赛")
            return result[:20]
        
        except Exception as e:
            print(f"[AT] 异常: {e}")
            import traceback
            traceback.print_exc()
            return []