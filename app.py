# -*- coding: utf-8 -*-
from flask import Flask, request, jsonify, send_from_directory, Response, stream_with_context
from flask_cors import CORS
import json
import os
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
from crawler import LuoguCrawler, AtCoderCrawler
from analyzer import Analyzer
from config import DEEPSEEK_API_KEY, LUOGU_COOKIE

app = Flask(__name__, static_folder='static')
CORS(app)


@app.route('/')
def index():
    return send_from_directory('static', 'index.html')


@app.route('/analyze', methods=['POST'])
def analyze():
    try:
        data = request.get_json()
        luogu_uid = data.get('luogu_uid', '').strip()
        atcoder_user = data.get('atcoder_user', '').strip()
        user_api_key = data.get('api_key', '').strip()

        if not luogu_uid:
            return jsonify({'error': '请输入洛谷 UID'}), 400

        # ---------- 1. 主爬虫 ----------
        main_crawler = LuoguCrawler(cookie=LUOGU_COOKIE)

        # ---------- 2. 等级分历史 ----------
        elo_info = main_crawler.get_user_elo(luogu_uid)
        if not elo_info or not elo_info.get('history'):
            return jsonify({'error': '未获取到等级分历史，可能该用户没有 rated 比赛记录'}), 400

        history = sorted(elo_info['history'], key=lambda x: x.get('time') or 0)

        elo_history = []
        for record in history:
            elo_history.append({
                'time': record.get('time'),
                'rating': record.get('rating'),
                'contest_name': record.get('contest', {}).get('name', '')
            })

        # ---------- 3. 并行处理每场比赛 ----------
        rated_contests = []
        contest_name_cache = {}
        lock = threading.Lock()

        def get_contest_name(cid):
            with lock:
                if cid not in contest_name_cache:
                    info = main_crawler.get_contest_info(cid)
                    contest_name_cache[cid] = info.get('name', f'比赛 {cid}')
                return contest_name_cache[cid]

        def process_contest(record, idx):
            contest_id = record.get('contest', {}).get('id')
            if not contest_id:
                return None
            rating = record.get('rating')
            if rating is None:
                return None
            prev_rating = history[idx-1].get('rating') if idx > 0 else None
            change = (rating - prev_rating) if prev_rating is not None else 0

            contest_id_str = str(contest_id)
            contest_name = get_contest_name(contest_id_str)

            crawler = LuoguCrawler()

            try:
                submissions = crawler.get_contest_submissions(luogu_uid, contest_id_str)
            except Exception as e:
                print(f"  跳过比赛 {contest_id_str}: {e}")
                submissions = []

            contest_problems_info = crawler.get_contest_problems(contest_id_str)
            total_problems = contest_problems_info.get('total', 0)
            problem_list = contest_problems_info.get('problems', [])

            if not submissions:
                problems = []
                accepted_count = 0
            else:
                tags_map = {}
                difficulty_map = {}

                if problem_list:
                    def fetch_tags_and_diff(p):
                        pid = p.get('pid')
                        if not pid:
                            return None, None
                        tags = crawler.get_problem_tags(pid, contest_id_str)
                        return pid, {'tags': tags, 'difficulty': p.get('difficulty', '暂无评定')}

                    with ThreadPoolExecutor(max_workers=3) as tag_executor:
                        futures = {tag_executor.submit(fetch_tags_and_diff, p): p for p in problem_list}
                        for future in as_completed(futures):
                            result = future.result()
                            if result:
                                pid, result_data = result
                                tags_map[pid] = result_data['tags']
                                difficulty_map[pid] = result_data['difficulty']

                best_scores = {}
                for sub in submissions:
                    pid = sub['pid']
                    score = sub.get('score') or 0
                    if pid not in best_scores or score > best_scores[pid]['score']:
                        best_scores[pid] = sub
                        best_scores[pid]['score'] = score
                        best_scores[pid]['tags'] = tags_map.get(pid, [])
                        best_scores[pid]['difficulty'] = difficulty_map.get(pid, '暂无评定')

                problems = list(best_scores.values())
                accepted_count = sum(1 for p in problems if p['status'] == 'AC')

            return {
                'contest_id': contest_id_str,
                'contest_name': contest_name,
                'elo_before': prev_rating,
                'elo_after': rating,
                'elo_change': change,
                'time': record.get('time'),
                'problems': problems,
                'accepted_count': accepted_count,
                'total_problems': total_problems,
            }

        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(process_contest, record, i) for i, record in enumerate(history)]
            for future in as_completed(futures):
                result = future.result()
                if result:
                    rated_contests.append(result)

        rated_contests.sort(key=lambda x: x.get('time') or 0)

        # ---------- 生成错题本 ----------
        wrong_problems = []
        for contest in rated_contests:
            contest_name = contest.get('contest_name', '')
            for problem in contest.get('problems', []):
                if problem.get('status') != 'AC':
                    wrong_problems.append({
                        'pid': problem.get('pid'),
                        'status': problem.get('status'),
                        'contest_name': contest_name,
                        'difficulty': problem.get('difficulty', '未知'),
                        'tags': problem.get('tags', [])
                    })

        # ---------- 4. 奖项 & 通过统计 ----------
        luogu_awards = main_crawler.get_user_awards(luogu_uid)
        passed_stats = main_crawler.get_user_passed_problems(luogu_uid)

        # ---------- 5. AtCoder ----------
        atcoder_crawler = AtCoderCrawler()
        atcoder_rating = atcoder_crawler.get_user_rating_info(atcoder_user)
        atcoder_data = atcoder_crawler.get_user_contests(atcoder_user, max_workers=2)

        atcoder_elo_history = []
        for item in atcoder_data:
            if item.get('rating') is not None:
                end_time = item.get('end_time')
                if end_time and isinstance(end_time, str):
                    try:
                        from datetime import datetime
                        end_time = int(datetime.fromisoformat(end_time.replace('Z', '+00:00')).timestamp())
                    except:
                        end_time = None
                atcoder_elo_history.append({
                    'time': end_time,
                    'rating': item.get('rating'),
                    'contest_name': item.get('contest_name', '')
                })
        atcoder_elo_history.sort(key=lambda x: x.get('time') or 0)

        # ---------- 6. DeepSeek 分析 ----------
        # 检查是否提供 API Key（用户输入或配置文件）
        api_key = user_api_key if user_api_key else DEEPSEEK_API_KEY
        if api_key:
            try:
                analyzer = Analyzer(api_key=api_key)
                analysis_result = analyzer.analyze(
                    rated_contests,
                    atcoder_data,
                    luogu_awards,
                    atcoder_rating
                )
            except Exception as e:
                # 如果 AI 分析失败，返回错误信息但不影响其他数据
                analysis_result = {
                    "error": f"AI 分析失败: {str(e)}",
                    "overall_rating": "AI 分析出错",
                    "strengths": [],
                    "weaknesses": [],
                    "match_reviews": ["AI 分析过程中出现错误，请检查 API Key 或网络"],
                    "suggestions": "请稍后重试或检查 API Key",
                    "daily_mission": []
                }
        else:
            # 没有 API Key，返回空分析
            analysis_result = {
                "error": "未提供 DeepSeek API Key，AI 分析已跳过",
                "overall_rating": "未分析（请提供 API Key）",
                "strengths": [],
                "weaknesses": [],
                "match_reviews": ["请提供 DeepSeek API Key 以获取 AI 分析"],
                "suggestions": "请配置 API Key 后重新分析",
                "daily_mission": []
            }

        # ---------- 7. 组装结果 ----------
        final_result = {
            'luogu_uid': luogu_uid,
            'atcoder_user': atcoder_user,
            'luogu_awards': luogu_awards,
            'atcoder_rating': atcoder_rating,
            'luogu_contests': rated_contests,
            'atcoder_contests': atcoder_data,
            'analysis': analysis_result,
            'passed_stats': passed_stats,
            'wrong_problems': wrong_problems,
            'elo_history': elo_history,
            'atcoder_elo_history': atcoder_elo_history
        }

        os.makedirs('data', exist_ok=True)
        with open('data/result.json', 'w', encoding='utf-8') as f:
            json.dump(final_result, f, ensure_ascii=False, indent=2)

        return jsonify(final_result)

    except Exception as e:
        print('❌ 服务器错误:', traceback.format_exc())
        return jsonify({'error': f'服务器内部错误: {str(e)}'}), 500


@app.route('/chat', methods=['POST'])
def chat():
    try:
        data = request.get_json()
        user_message = data.get('message', '').strip()
        user_api_key = data.get('api_key', '').strip()
        if not user_message:
            return jsonify({'error': '请输入问题'}), 400

        result_path = 'data/result.json'
        if not os.path.exists(result_path):
            return jsonify({'error': '请先运行一次分析（点击"开始分析"）'}), 400

        with open(result_path, 'r', encoding='utf-8') as f:
            result_data = json.load(f)

        context_summary = _build_chat_context(result_data)

        api_key = user_api_key if user_api_key else DEEPSEEK_API_KEY
        if not api_key:
            return jsonify({'error': '请提供 DeepSeek API Key，或在 config.py 中配置'}), 400

        from analyzer import Analyzer
        analyzer = Analyzer(api_key=api_key)
        reply = analyzer.chat_with_context(context_summary, user_message)
        return jsonify({'reply': reply})

    except Exception as e:
        print('❌ 聊天错误:', traceback.format_exc())
        return jsonify({'error': f'聊天失败: {str(e)}'}), 500


@app.route('/chat/stream', methods=['POST'])
def chat_stream():
    try:
        data = request.get_json()
        messages = data.get('messages', [])
        user_api_key = data.get('api_key', '').strip()
        if not messages:
            return jsonify({'error': '请输入问题'}), 400

        result_path = 'data/result.json'
        if not os.path.exists(result_path):
            return jsonify({'error': '请先运行分析'}), 400

        with open(result_path, 'r', encoding='utf-8') as f:
            result_data = json.load(f)

        context = _build_chat_context(result_data)

        api_key = user_api_key if user_api_key else DEEPSEEK_API_KEY
        if not api_key:
            return jsonify({'error': '请提供 DeepSeek API Key，或在 config.py 中配置'}), 400

        from analyzer import Analyzer
        analyzer = Analyzer(api_key=api_key)
        return analyzer.stream_chat_with_history(context, messages)

    except Exception as e:
        print('❌ 聊天流错误:', traceback.format_exc())
        return jsonify({'error': str(e)}), 500


def _build_chat_context(data):
    context_parts = []

    awards = data.get('luogu_awards', [])
    if awards:
        context_parts.append(f"洛谷奖项：{', '.join(awards)}")

    rating = data.get('atcoder_rating', {})
    if rating.get('rank') and rating.get('rating'):
        context_parts.append(f"AtCoder 段位：{rating['rank']} ({rating['rating']})")

    analysis = data.get('analysis', {})
    if analysis.get('overall_rating'):
        context_parts.append(f"综合评级：{analysis['overall_rating']}")

    if analysis.get('strengths'):
        context_parts.append(f"优势领域：{', '.join(analysis['strengths'])}")
    if analysis.get('weaknesses'):
        context_parts.append(f"薄弱领域：{', '.join(analysis['weaknesses'])}")

    if analysis.get('suggestions'):
        context_parts.append(f"训练建议：{analysis['suggestions'][:200]}...")

    wrong = data.get('wrong_problems', [])
    if wrong:
        tag_count = {}
        for p in wrong:
            for tag in p.get('tags', ['无标签']):
                tag_count[tag] = tag_count.get(tag, 0) + 1
        top_wrong = sorted(tag_count.items(), key=lambda x: -x[1])[:5]
        if top_wrong:
            context_parts.append(f"常见错题标签：{', '.join([f'{tag}({count}次)' for tag, count in top_wrong])}")

    contests = data.get('luogu_contests', [])
    if contests:
        total_ac = sum(c.get('accepted_count', 0) for c in contests)
        total_problems = sum(c.get('total_problems', 0) for c in contests)
        if total_problems > 0:
            rate = total_ac / total_problems * 100
            context_parts.append(f"总比赛题数：{total_ac}/{total_problems}，通过率 {rate:.1f}%")

    if not context_parts:
        return "暂无你的个人数据，请先点击'开始分析'。"

    return "你是用户的数据分析助手。以下是用户已有的数据摘要：\n" + "\n".join(context_parts)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)