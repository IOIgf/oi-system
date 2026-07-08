# 🧠 OI 训练系统

> 基于 AI 的 OI 竞赛训练分析系统，支持洛谷 + AtCoder 双平台数据，自动读取 Cookie，一键生成个性化训练建议。

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-2.3+-green.svg)](https://flask.palletsprojects.com/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## ✨ 功能特性

- 📊 **智能数据分析**：自动爬取洛谷和 AtCoder 比赛记录，生成详细分析报告
- 🤖 **AI 教练**：基于 DeepSeek 的对话式问答，针对你的数据给出个性化建议
- 📕 **错题本**：自动汇总所有错题，按知识点分组，方便针对性训练
- 📈 **等级分趋势**：可视化展示洛谷和 AtCoder 等级分变化
- 🏆 **荣誉墙**：展示获奖记录和段位
- 🎯 **每日推荐**：AI 根据薄弱点推荐题目，支持 Markdown 流式输出

---

## 🚀 快速开始

### 1. 环境要求

- Python 3.8+
- Chrome 浏览器（用于自动读取 Cookie）

### 2. 安装

```bash
git clone https://github.com/your-username/oi-training-system.git
cd oi-training-system
pip install -r requirements.txt
```

### 3. 配置

1. 复制 `config.example.py` 为 `config.py`：

```bash
cp config.example.py config.py
```

2. 在 `config.py` 中填写 **DeepSeek API Key**：

```python
DEEPSEEK_API_KEY = "sk-你的密钥"
```

3. **Cookie 无需手动填写**！程序会自动从 Chrome 读取：
   - 先在 Chrome 中登录 [洛谷](https://www.luogu.com.cn) 和 [AtCoder](https://atcoder.jp)
   - 运行后程序会自动读取登录状态

> 如果自动读取失败，可以在 `config.py` 的 `LUOGU_COOKIE` 中手动填写 Cookie 字符串。

### 4. 运行

```bash
python app.py
```

然后浏览器打开 `http://localhost:5000` 即可开始使用。

---

## 📁 项目结构

```
oi-system/
├── app.py                 # Flask 后端主程序
├── crawler.py             # 爬虫模块（洛谷 + AtCoder）
├── analyzer.py            # DeepSeek 分析模块
├── config.example.py      # 配置文件模板
├── requirements.txt       # Python 依赖
├── static/                # 前端页面
│   ├── index.html         # 主分析面板
│   ├── chat.html          # AI 教练（流式对话）
│   ├── wrong.html         # 错题本
│   └── contests.html      # 比赛详情
└── data/                  # 运行时生成的数据（不提交）
    └── result.json
```

---

## 🛠️ 技术栈

| 层次 | 技术 |
|:---|:---|
| **后端** | Python 3.8+、Flask |
| **前端** | 原生 HTML/CSS/JS、ECharts |
| **AI** | DeepSeek API |
| **爬虫** | Requests、BeautifulSoup、Selenium |
| **打包** | PyInstaller（可选） |

---

## 📸 功能预览

### 主分析面板
- 输入洛谷 UID 和 AtCoder 用户名
- 一键生成综合评级、优势/薄弱领域、训练建议、每日推荐任务
- 双平台等级分趋势图

### AI 教练
- 独立聊天页面，支持 Markdown 渲染
- 流式输出，实时显示回复
- 基于你的历史数据给出针对性建议

### 错题本
- 自动汇总所有非 AC 题目
- 按知识点标签分组，方便集中训练
- 点击题号直达洛谷题目页面

### 比赛详情
- 按比赛列出每道题的提交状态、得分、难度和知识点标签
- 显示等级分变化和 AC 题数统计

---

## 📝 注意事项

- 首次运行时会自动下载 ChromeDriver（需网络）
- 数据保存在 `data/result.json`，刷新页面不丢失
- 如使用打包后的 `.exe` 文件，同样需要 Chrome 浏览器

---

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

---

## 📄 许可证

MIT License © 2025

---

## 🙏 致谢

- [洛谷](https://www.luogu.com.cn/) – 国内最大的 OI 学习平台
- [AtCoder](https://atcoder.jp/) – 日本顶级算法竞赛平台
- [DeepSeek](https://deepseek.com/) – 提供强大的 AI 分析能力
- [ECharts](https://echarts.apache.org/) – 数据可视化库