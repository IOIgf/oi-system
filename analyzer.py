# -*- coding: utf-8 -*-
import json
import requests
from typing import Dict, List, Optional, Any
from config import DEEPSEEK_API_KEY, DEEPSEEK_API_URL
from flask import Response, stream_with_context

class Analyzer:
    def __init__(self, api_key: str = DEEPSEEK_API_KEY):
        self.api_key = api_key
        self.api_url = DEEPSEEK_API_URL
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

    def analyze(self,
                luogu_data: List[Dict],
                atcoder_data: List[Dict],
                luogu_awards: Optional[List[str]] = None,
                atcoder_rating: Optional[Dict] = None) -> Dict:
        prompt = self._build_prompt(luogu_data, atcoder_data, luogu_awards, atcoder_rating)
        payload = {
            "model": "deepseek-chat",
            "messages": [
                {"role": "system", "content": "你是一位资深OI教练，擅长数据分析。请根据选手的比赛记录，给出详细、具体、可操作的分析和建议。输出必须严格符合JSON格式。特别注意：suggestions 和 match_reviews 字段内容请使用 Markdown 格式（标题、列表、加粗等）组织，以便前端美化展示。"},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.9,   # 提高温度增加多样性
            "max_tokens": 5000,
            "response_format": {"type": "json_object"},
            "search_enable": True  # 🔑 开启联网搜索，获取最新题目
        }
        try:
            resp = requests.post(self.api_url, headers=self.headers, json=payload, timeout=120)  # 增加超时以允许搜索
            resp.raise_for_status()
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            return json.loads(content)
        except Exception as e:
            return {"error": str(e)}

    def _build_prompt(self, luogu_data, atcoder_data, luogu_awards, atcoder_rating):
        luogu_summary, luogu_stats = self._format_luogu(luogu_data)
        atcoder_summary, atcoder_stats = self._format_atcoder(atcoder_data)
        awards_str = ", ".join(luogu_awards) if luogu_awards else "无"
        atcoder_rank_str = f"{atcoder_rating.get('rank', 'N/A')} ({atcoder_rating.get('rating', 'N/A')})" if atcoder_rating else "无"

        total_contests = len(luogu_data)
        rated_count = sum(1 for c in luogu_data if c.get("elo_change") is not None)

        # 提取用户已做的题号列表
        done_pids = set()
        for contest in luogu_data:
            for problem in contest.get('problems', []):
                pid = problem.get('pid')
                if pid:
                    done_pids.add(pid)
        done_pids_str = ", ".join(sorted(done_pids)[:100]) if done_pids else "无"

        # 构建搜索关键词模板
        search_keywords = {
            "dp": "洛谷 动态规划 题目 推荐 2025 2026",
            "graph": "洛谷 图论 题目 推荐 2025 2026",
            "search": "洛谷 搜索 题目 推荐 2025 2026",
            "greedy": "洛谷 贪心 题目 推荐 2025 2026",
            "math": "洛谷 数论 组合数学 题目 推荐 2025 2026",
            "string": "洛谷 字符串 题目 推荐 2025 2026",
        }

        prompt = f"""
假设你是一位资深的信息学奥赛教练，请分析以下选手的比赛数据，给出深度评估。

【选手荣誉背景】
- 洛谷奖项：{awards_str}
- AtCoder 段位：{atcoder_rank_str}

【洛谷比赛数据】（共 {total_contests} 场，其中 {rated_count} 场有等级分变化）
全局统计：
- 总比赛数：{luogu_stats.get('total_contests', 0)}
- 总提交题数：{luogu_stats.get('total_problems', 0)}
- 总 AC 题数：{luogu_stats.get('total_ac', 0)}
- 总通过率：{luogu_stats.get('ac_rate', 0):.1%}
- 各难度通过率：
{self._format_diff_stats(luogu_stats.get('diff_stats', {}))}

详细比赛记录：
{luogu_summary}

【AtCoder比赛记录】（共 {atcoder_stats.get('total_contests', 0)} 场，含每道题状态和得分）
全局统计：
- 总比赛数：{atcoder_stats.get('total_contests', 0)}
- 总 AC 题数：{atcoder_stats.get('total_ac', 0)}
- 总通过率：{atcoder_stats.get('ac_rate', 0):.1%}

详细记录：
{atcoder_summary}

【任务要求】
请生成严格的 JSON 输出，结构如下：
{{
  "overall_rating": "综合评级（一句较短的句子，分析选手的综合实力）",
  "strengths": ["优势知识点1", "优势知识点2", "..."],
  "weaknesses": ["薄弱知识点1", "薄弱知识点2", "..."],
  "match_reviews": [
    "## 1. 总体表现\\n结合等级分趋势，说明整体水平变化，哪些比赛表现好，哪些糟糕。",
    "## 2. 知识点分析\\n具体哪些算法/数据结构掌握得好，哪些经常失分。",
    "## 3. 难度适应\\n分析在不同难度（入门、普及-、普及等）的通过率，指出哪一难度段最薄弱。",
    "## 4. 比赛策略\\n分析时间分配等与比赛策略有关的内容。",
    "## 5. AtCoder 表现\\n单独分析 AtCoder 比赛的特点和掌握情况。"
  ],
  "suggestions": "**训练建议**\\n\\n使用 Markdown 格式分点列出，至少 5 条。每条建议包括具体专题、推荐题目和理由。",
  "daily_mission": [
    {{ "pid": "用户未做过的洛谷题号（如 P1048）", "title": "题目的完整中文名称（如'采药'）", "reason": "为什么推荐这道题，与用户哪项薄弱相关" }}
  ]
}}

【重要规则 — 必须严格遵守！】
1. suggestions 要具体，包含可操作的训练计划，不要泛泛而谈。
2. match_reviews 中的每条内容请使用 Markdown 格式（标题 `##`、列表 `-`、加粗 `**` 等）。
3. suggestions 也请使用 Markdown 格式，包含标题、列表、加粗等。
4. daily_mission 的推荐规则（这是最关键的部分）：
   - 根据用户的薄弱知识点（从 weaknesses 中提取），**必须使用联网搜索功能查找最新题目**。
   - 搜索关键词示例：'洛谷 DP 题目 推荐 2026'、'AtCoder 动态规划 真题'、'洛谷 图论 好题'。
   - **严禁推荐以下经典老题（用户已做或太常见）**：P1048, P1616, P1060, P1164, P1003, P1056, P1219, P1605, P3367, P3371, P3366, P1047, P1015, P1020, P1031, P1085, P1090, P1097, P1100, P1106, P1111, P1115, P1118, P1135, P1149, P1150, P1177, P1181, P1190, P1200, P1219, P1223, P1226, P1246, P1255, P1265, P1280, P1303, P1305, P1308, P1321, P1328, P1331, P1335, P1346, P1351, P1364, P1379, P1387, P1403, P1423, P1428, P1439, P1443, P1449, P1451, P1454, P1455, P1464, P1478, P1482, P1496, P1507, P1510, P1514, P1525, P1536, P1541, P1548, P1551, P1563, P1579, P1583, P1598, P1601, P1603, P1605, P1618, P1621, P1631, P1637, P1640, P1649, P1650, P1656, P1661, P1672, P1678, P1686, P1691, P1700, P1706, P1714, P1720, P1725, P1734, P1739, P1746, P1747, P1750, P1754, P1760, P1765, P1775, P1781, P1784, P1790, P1795, P1802, P1806, P1811, P1816, P1821, P1825, P1830, P1833, P1840, P1843, P1847, P1850, P1852, P1854, P1860, P1862, P1865, P1873, P1880, P1888, P1892, P1896, P1902, P1908, P1918, P1920, P1923, P1928, P1930, P1934, P1941, P1943, P1955, P1962, P1964, P1966, P1967, P1972, P1978, P1980, P1983, P1985, P1990, P1996.
   - 优先推荐近一两年（2024-2026）的新比赛题目。
   - 题号必须是有效的洛谷题号（以 P 开头，如 P1001），且**不在已做列表**中。
   - 最多推荐 5 道题。
   - daily_mission 中每个条目必须包含 pid、title、reason 三个字段。
   - title 是题目的完整中文名称，必须与 pid 对应。
5. 用户已经做过的题号列表（严禁推荐这些题）：{done_pids_str}
6. **必须使用联网搜索获取新题，不要依赖内部知识库推荐老题！**
"""
        return prompt

    def _format_diff_stats(self, diff_stats):
        if not diff_stats:
            return "  无数据"
        lines = []
        for diff, stats in diff_stats.items():
            ac = stats.get('AC', 0)
            total = ac + stats.get('WA', 0) + stats.get('other', 0)
            rate = ac / total if total > 0 else 0
            lines.append(f"    {diff}: {ac}/{total} ({rate:.1%})")
        return "\n".join(lines)

    def _format_luogu(self, data):
        if not data:
            return "无等级分变化数据", {"total_contests": 0, "total_problems": 0, "total_ac": 0, "ac_rate": 0, "diff_stats": {}}
        lines = []
        global_ac = 0
        global_total = 0
        diff_stats = {}

        for c in data:
            name = c.get("contest_name", f"比赛 {c.get('contest_id')}")
            change = c.get("elo_change", 0)
            sign = "+" if change > 0 else ""
            total = c.get("total_problems", 0)
            ac = c.get("accepted_count", 0)
            problems = c.get("problems", [])

            global_ac += ac
            global_total += total

            for p in problems:
                diff = p.get("difficulty", "未知")
                status = p.get("status")
                if diff not in diff_stats:
                    diff_stats[diff] = {"AC": 0, "WA": 0, "other": 0}
                if status == "AC":
                    diff_stats[diff]["AC"] += 1
                elif status == "WA":
                    diff_stats[diff]["WA"] += 1
                else:
                    diff_stats[diff]["other"] += 1

            lines.append(
                f"{name}: 等级分 {c.get('elo_before')} → {c.get('elo_after')} ({sign}{change})，"
                f"AC {ac}/{total} 题"
            )

        ac_rate = global_ac / global_total if global_total > 0 else 0

        stats = {
            "total_contests": len(data),
            "total_problems": global_total,
            "total_ac": global_ac,
            "ac_rate": ac_rate,
            "diff_stats": diff_stats
        }

        return "\n".join(lines), stats

    def _format_atcoder(self, data):
        if not data:
            return "无比赛记录", {"total_contests": 0, "total_ac": 0, "ac_rate": 0}
        lines = []
        total_ac = 0
        total_problems = 0
        for item in data:
            name = item.get("contest_name", "")
            rank = item.get("rank")
            rating = item.get("rating")
            problems = item.get("problems", {})
            prob_keys = list(problems.keys())
            ac_count = sum(1 for p in problems.values() if p.get("status") == "AC")
            total_ac += ac_count
            total_problems += len(prob_keys)
            if problems:
                prob_details = []
                for pid, info in problems.items():
                    status = info.get("status", "未知")
                    score = info.get("score", 0)
                    prob_details.append(f"{pid}: {status}({score}分)")
                prob_summary = ", ".join(prob_details)
            else:
                prob_summary = "无提交"
            lines.append(f"{name}: 排名{rank}, 表现分{rating} -> {prob_summary}")
        ac_rate = total_ac / total_problems if total_problems > 0 else 0
        stats = {
            "total_contests": len(data),
            "total_ac": total_ac,
            "ac_rate": ac_rate
        }
        return "\n".join(lines), stats

    def chat_with_context(self, context: str, user_message: str) -> str:
        payload = {
            "model": "deepseek-chat",
            "messages": [
                {"role": "system", "content": f"你是一位OI竞赛教练，善于根据数据给予具体建议。回答时请基于用户提供的数据，语言亲切、具体，避免泛泛而谈。请使用 Markdown 格式（标题、列表、加粗、代码块等）组织你的回答，让内容更清晰、有条理。\n\n{context}"},
                {"role": "user", "content": user_message}
            ],
            "temperature": 0.7,
            "max_tokens": 2000
        }
        try:
            resp = requests.post(self.api_url, headers=self.headers, json=payload, timeout=60)
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]
        except Exception as e:
            return f"AI 暂时无法回答，请稍后再试。错误：{str(e)}"

    def stream_chat_with_history(self, context: str, messages: List[Dict[str, str]]) -> Response:
        full_messages = [
            {"role": "system", "content": f"你是一位OI竞赛教练，善于根据数据给予具体建议。回答时请基于用户提供的数据，语言亲切、具体，避免泛泛而谈。请使用 Markdown 格式（标题、列表、加粗、代码块等）组织你的回答，让内容更清晰、有条理。\n\n{context}"}
        ] + messages

        payload = {
            "model": "deepseek-chat",
            "messages": full_messages,
            "temperature": 0.7,
            "max_tokens": 2000,
            "stream": True
        }

        def generate():
            try:
                resp = requests.post(self.api_url, headers=self.headers, json=payload, stream=True, timeout=60)
                resp.raise_for_status()
                for line in resp.iter_lines():
                    if line:
                        decoded = line.decode('utf-8')
                        if decoded.startswith('data: '):
                            data_str = decoded[6:]
                            if data_str == '[DONE]':
                                break
                            try:
                                data_json = json.loads(data_str)
                                delta = data_json.get('choices', [{}])[0].get('delta', {})
                                content = delta.get('content', '')
                                if content:
                                    yield f"data: {json.dumps({'content': content})}\n\n"
                            except json.JSONDecodeError:
                                continue
            except Exception as e:
                yield f"data: {json.dumps({'error': str(e)})}\n\n"
            yield "data: [DONE]\n\n"

        return Response(stream_with_context(generate()), mimetype='text/event-stream')