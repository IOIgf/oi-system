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
                {"role": "system", "content": "你是一位资深OI教练，擅长数据分析。请根据选手的比赛记录，给出详细、具体、可操作的分析和建议。输出必须严格符合JSON格式。"},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.7,
            "max_tokens": 5000,  # 增加 token 以允许更长的分析
            "response_format": {"type": "json_object"}
        }
        try:
            resp = requests.post(self.api_url, headers=self.headers, json=payload, timeout=60)
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

        prompt = f"""
请分析以下选手的比赛数据，给出深度评估。你的分析需要具体、详细，并基于数据事实。

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

请生成严格的 JSON 输出，结构如下：
{{
  "overall_rating": "综合评级（例如：CSP-J 一等奖水平，AtCoder Brown，建议主攻提高组）",
  "strengths": ["优势知识点1", "优势知识点2", "..."],
  "weaknesses": ["薄弱知识点1", "薄弱知识点2", "..."],
  "match_reviews": [
    "1. 总体表现：结合等级分趋势，说明整体水平变化，哪些比赛表现好，哪些糟糕。",
    "2. 知识点分析：具体哪些算法/数据结构掌握得好，哪些经常失分。例如：动态规划中背包问题 AC 率高，但树形 DP 经常 WA。",
    "3. 难度适应：分析在不同难度（入门、普及-、普及等）的通过率，指出哪一难度段最薄弱。",
    "4. 比赛策略：分析时间分配、多提交尝试是否有效，是否存在因粗心导致的 WA。",
    "5. AtCoder 表现：单独分析 AtCoder 比赛的特点（如思维题、构造题等）的掌握情况。"
  ],
  "suggestions": "详细的训练建议，分点列出，至少 5 点。每条建议包括具体专题、推荐题目和理由。例如：1. 动态规划：推荐 P1048（01背包）、P1616（完全背包），巩固基础。2. 图论：练习 P3371（单源最短路），掌握 Dijkstra。...",
  "daily_mission": [
    {{ "pid": "P1048", "reason": "经典01背包，巩固DP基础" }},
    ...
  ]
}}
注意：suggestions 要具体，包含可操作的训练计划，不要泛泛而谈。
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

            # 更新全局统计
            global_ac += ac
            global_total += total

            # 按难度统计
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

            # 生成该场比赛的难度总结
            diff_summary = []
            for diff, stats in diff_stats.items():
                # 只显示本场比赛涉及的难度（此处在循环中会重复计算，优化：在循环外统计）
                pass
            # 我们可以在循环外重新统计每场比赛的难度，但为了简洁，我们在全局统计中统一处理。

            # 简化每场比赛的描述：只显示AC/总数和等级分变化
            lines.append(
                f"{name}: 等级分 {c.get('elo_before')} → {c.get('elo_after')} ({sign}{change})，"
                f"AC {ac}/{total} 题"
            )

        # 重新计算每场比赛的难度分布？由于在循环中已经累加 diff_stats，我们直接用全局的
        # 但全局 diff_stats 已经是所有比赛的汇总，不需要再按比赛拆分。

        # 我们还需要为每场比赛单独显示难度吗？如果比赛很多，会很长，所以只显示全局统计。
        # 但上面 lines 只显示了每场比赛的基本信息，难度统计已在全局。
        # 为了更详细，可以在每场比赛后面添加该场比赛的难度摘要，但那样会很长。
        # 我们选择在全局统计中展示难度分布。

        # 计算全局通过率
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
        """基于上下文和用户消息进行对话"""
        payload = {
            "model": "deepseek-chat",
            "messages": [
                {"role": "system", "content": f"你是一位OI竞赛教练，善于根据数据给予具体建议。回答时请基于用户提供的数据，语言亲切、具体，避免泛泛而谈。\n\n{context}"},
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
    def stream_chat(self, context: str, user_message: str):
        payload = {
            "model": "deepseek-chat",
            "messages": [
                {"role": "system", "content": f"你是一位OI竞赛教练，善于根据数据给予具体建议。回答时请基于用户提供的数据，语言亲切、具体，避免泛泛而谈。\n\n{context}"},
                {"role": "user", "content": user_message}
            ],
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