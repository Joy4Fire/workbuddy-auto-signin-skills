# workbuddy-auto-signin

**WorkBuddy 桌面应用**（腾讯云 CodeBuddy AI 助手）**自动签到技能** — v10 Vision-Driven Edition。

由 WorkBuddy 自己的多模态 Agent 通过截图视觉分析完成 UI 元素定位，Python 脚本只负责窗口管理、截图、点击等纯机械动作。

> ⚠️ **仅支持 Windows** — 依赖 Win32 API (`ctypes`)、`pyautogui`、`PIL`、`numpy`。

---

## 🎯 核心特性

- **🤖 视觉模型驱动** — 全部 UI 元素定位由 Agent 多模态视觉完成，**无 OpenCV、无硬编码坐标、无阈值调参**
- **🪟 自适应窗口** — 百分比坐标 + 窗口自动定位，适配不同屏幕分辨率和窗口大小
- **⏰ 凌晨友好** — 内置显示器唤醒 + 输入可达检测，应对 4AM 自动化的环境挑战
- **🛡️ 多重安全守卫** — 锁屏检查、输入隔离检测、像素变化验证，避免静默失败
- **🔧 薄 helper 架构** — Python 脚本是一个 350 行的 CLI 工具，所有"智能"在 Agent 侧
- **🧪 调试友好** — 每步可独立调用（`find-window` / `screenshot` / `click`），便于排错

## 🆕 v10 vs v9 主要变化

| 维度 | v9 (OpenCV) | v10 (Vision-Driven) |
|------|------------|---------------------|
| 按钮定位 | OpenCV 灰度阈值（<120）+ 轮廓 | Agent 直接读截图识别 |
| 坐标格式 | 固定百分比 + OpenCV 像素映射 | Agent 在截图坐标上直接定位 |
| 泛化能力 | 阈值一变就失效，需重新调参 | AI 理解任意 UI 布局 |
| 异常处理 | 硬编码规则（IDM 弹窗、面板异常） | Agent 自然理解 |
| 依赖 | opencv-python-headless (~50MB) | 无 OpenCV（仅 pyautogui + PIL + numpy） |
| 升级影响 | 改 UI 必须改阈值 | 改 UI 不用改代码 |

## 🚀 快速开始

### 1. 安装依赖

```bash
pip install pyautogui pillow numpy
```

**注意**：v10 不再需要 opencv-python-headless！如果从 v9 升级可以卸载。

### 2. 安装 Skill

将本仓库复制到 WorkBuddy skills 目录：

```bash
# Windows (PowerShell)
Copy-Item -Recurse workbuddy-auto-signin "$env:USERPROFILE\.workbuddy\skills\"

# Linux / WSL / macOS (仅供参考，本 skill 仅支持 Windows)
cp -r workbuddy-auto-signin ~/.workbuddy/skills/
```

### 3. 运行签到

**通过 WorkBuddy 对话**（推荐）：
```
签到
每日签到
WorkBuddy签到
自动领取积分
```

Agent 会自动按 SKILL.md 工作流完成所有步骤。

**直接调用 helper 脚本**（高级用法 / 调试）：
```bash
python scripts/auto_signin.py <command> [args]
```

可用命令：
| Command | 用途 |
|---------|------|
| `find-window` | 查找 WorkBuddy HWND 与 rect |
| `activate <HWND>` | 激活并定位窗口到主屏 |
| `screenshot --output <path> [--region x1,y1,x2,y2]` | 截屏 |
| `click <X> <Y> [single\|double]` | 单击/双击指定坐标 |
| `press-key <KEY>` | 按下键盘按键 |
| `check-lock` | 检查是否锁屏 |
| `wake-screen` | 唤醒显示器 + 验证输入可达 |

## 🧠 工作原理

```
Agent (multimodal LLM)         Python Helper (auto_signin.py)
       │                                    │
       │  ┌──── find-window ───────────────▶│
       │  │                                  │
       │  ◀── { hwnd, rect } ───────────────┤
       │  │                                  │
       │  ┌──── activate ──────────────────▶│
       │  │                                  │
       │  ┌──── wake-screen ───────────────▶│  (Shift key + 头像点击,
       │  │                                  │   验证输入可达)
       │  ◀── { status: "ok" } ─────────────┤
       │  │                                  │
       │  ┌──── screenshot ────────────────▶│
       │  │                                  │
       │  ◀── image bytes ─────────────────┤
       │  │                                  │
       │  [Agent 用 vision 分析: 找到头像]   │
       │  │                                  │
       │  ┌──── click 562 1158 ────────────▶│
       │  │                                  │
       │  [WorkBuddy 打开用户菜单]            │
       │  │                                  │
       │  ┌──── screenshot ────────────────▶│
       │  ◀── image bytes ─────────────────┤
       │  │                                  │
       │  [Agent 用 vision 分析: 找到签到按钮]│
       │  │                                  │
       │  ┌──── click 723 612 double ──────▶│
       │  │                                  │
       │  ┌──── press-key escape ──────────▶│
```

**关键设计原则**：
- **零检测逻辑在 Python** — UI 元素识别由 Agent 视觉完成，脚本只做机械操作
- **每步可独立验证** — 通过 `screenshot` 截图 + Agent Read + 视觉判断
- **失败立刻 abort** — 不重试、不静默、不掩盖错误

## 📋 SKILL.md 工作流

Agent 按以下步骤执行（详见 `SKILL.md`）：

1. **Step 0: check-lock** — 检查屏幕是否锁定
2. **Step 0.5: wake-screen** — 唤醒显示器 + 验证输入可达
3. **Step 1: find-window** — 找到 WorkBuddy IDE 窗口
4. **Step 1.5: activate** — 激活窗口并定位到主屏
5. **Step 2: screenshot + 视觉分析** — 截取基线，定位用户头像坐标
6. **Step 3: click avatar** — 点击头像打开用户菜单
7. **Step 3b: 视觉验证面板** — 截图确认菜单已打开
8. **Step 4: 视觉定位签到按钮** — 找到"立即领取"按钮
9. **Step 5: double-click** — 双击按钮（单击无效！）
10. **Step 6: press-key escape** — 关闭面板

## ⚙️ 配置说明

配置文件：`config/signin_config.json`

```json
{
  "window_position": {
    "width_percent": 0.6,
    "height_percent": 0.7,
    "x_percent": 0.2,
    "y_percent": 0.15
  }
}
```

只保留窗口定位参数——v10 不需要按钮坐标，所有元素都由 Agent 视觉定位。

## 🐛 故障排除

| 现象 | 原因 | 解决方法 |
|------|------|----------|
| `WorkBuddy window not found` | 应用未运行 | 启动 WorkBuddy 后重试 |
| `wake-screen` 返回 `input_blocked` | 会话隔离或输入事件被拦截 | 白天手动运行；或检查 PC 是否处于 UAC / 锁屏中间态 |
| 头像点击后面板未打开 | WorkBuddy 处于非主界面视图 | 在 WorkBuddy 内手动切回主界面再触发 skill |
| 双击按钮无响应 | 用了单击 | 必须用 `double`（脚本默认） |
| 凌晨 4 点失败 | 见 `references/technical_notes.md` | 调整触发时间 + 显示器不休眠 |

## 📂 文件结构

| 文件 | 作用 |
|------|------|
| `SKILL.md` | Agent 指令文档（触发词、工作流、状态机） |
| `README.md` | 本文件，人类阅读的项目说明 |
| `scripts/auto_signin.py` | 薄 helper CLI 工具（350 行） |
| `config/signin_config.json` | 窗口定位配置 |
| `debug_enum.py` | 诊断工具：枚举所有 WorkBuddy 窗口与 PID |
| `references/technical_notes.md` | 技术笔记：架构演进、踩过的坑、4AM 失败的根因分析 |
| `templates/` | 调试截图目录（gitignore 忽略） |

## 📜 许可证

Apache License 2.0

## 🙋 贡献

欢迎提交 Issue / PR 报告问题或改进。常见改进方向：
- 适配其他平台的 WorkBuddy 客户端（macOS / Linux）
- 优化 agent prompt 减少 token 消耗
- 添加更多错误状态的可恢复分支

---

_本工具并非 WorkBuddy 官方出品。_
