# workbuddy-auto-signin

WorkBuddy 桌面应用（腾讯云 CodeBuddy AI 助手）**自动签到工具**，通过图像识别 + 坐标点击实现每日积分领取。

> ⚠️ **仅支持 Windows** — 依赖 Win32 API (`ctypes`)、`pyautogui`、`PIL`、`OpenCV`。

## 🎯 主要能力

- **自适应坐标**：使用百分比定位，自动适配不同窗口大小和屏幕分辨率
- **OpenCV 按钮检测**：自动识别"立即领取"按钮位置，无需手动配置坐标
- **窗口管理**：自动处理最小化窗口、多显示器、窗口激活
- **双点击触发**：正确使用双击（单击无法触发签到）
- **调试模式**：`--debug` 保存每步截图，方便排查问题

## 🚀 快速开始

### 1. 安装依赖

```bash
pip install pyautogui pillow numpy opencv-python-headless
```

### 2. 安装 Skill

将本 Skill 复制到 WorkBuddy skills 目录：

```bash
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

**直接运行脚本**：
```bash
# 静默模式
python scripts/auto_signin.py

# 调试模式（保存截图）
python scripts/auto_signin.py --debug

# 查看当前配置
python scripts/auto_signin.py --save-config
```

## 📝 工作原理

由于 WorkBuddy 是 **Electron 应用**，其内部 DOM 元素无法通过标准无障碍 API 访问（`pywinauto` UIA 只能看到 `Chrome Legacy Window`）。本 Skill 采用 **视觉方案**：

1. **窗口管理**：通过 Win32 `EnumWindows` 查找 WorkBuddy 窗口，若最小化则恢复，并移动到主显示器固定位置 `(340,50)→(1540,950)`
2. **打开面板**：点击左下角用户头像，弹出签到面板
3. **按钮检测**：使用 **OpenCV 灰度阈值（<120）** 在绿色卡片区域内检测深色"立即领取"按钮；若检测失败则回退到配置坐标
4. **执行签到**：**双击**按钮（单击只会选中但不会执行！）
5. **结果验证**：捕获结果截图；成功会显示"✅ 领取成功！获得 150 Credits"提示条

## ⚙️ 配置说明

配置文件：`config/signin_config.json`

```json
{
  "avatar_click": {
    "x_percent": 0.0317,
    "y_from_bottom_percent": 0.0533
  },
  "signin_button": {
    "x_percent": 0.0858,
    "y_percent": 0.5167,
    "click_method": "double"
  }
}
```

### 坐标系统（自适应）

| 元素 | 位置 | 说明 |
|------|--------|------|
| 用户头像 | 左侧 3.17%，底部往上 5.33% | 点击打开签到面板 |
| 签到按钮 | 左侧 8.58%，顶部往下 51.67% | "立即领取"按钮 |

**自适应说明**：坐标为百分比格式，自动根据窗口大小计算绝对坐标，适配不同屏幕分辨率。

## 🔧 故障排除

| 现象 | 原因 | 解决方法 |
|------|------|----------|
| `WorkBuddy window not found` | 应用未运行 | 先启动 WorkBuddy |
| 点击到错误位置 | 窗口大小改变 | 运行 `--debug`，检查截图 |
| 按钮找到但无响应 | 未使用双击 | 配置中已设置 `click_method: "double"` |
| OpenCV 检测失败 | UI 布局改变 | 更新配置文件中的百分比坐标 |

## 📂 文件结构

| 文件 | 作用 |
|------|------|
| `SKILL.md` | AI 模型阅读的指令文档（触发词、工作流程） |
| `README.md` | 人类阅读的项目说明 |
| `scripts/auto_signin.py` | 核心签到脚本（自适应坐标版本） |
| `config/signin_config.json` | 坐标配置文件（百分比格式） |
| `references/technical_notes.md` | 技术文档（调试历史、像素映射记录） |
| `templates/` | 调试截图保存目录（`.gitignore` 已忽略） |

## 📌 重要技术要点

- **为什么必须双击？** 单击只会选中按钮，不会触发签到动作
- **为什么用百分比坐标？** 适配不同窗口大小和屏幕分辨率
- **为什么用 OpenCV？** Electron 应用不向外暴露 UI 元素，只能通过图像识别

## 📄 许可证

MIT License

---

_声明：本工具并非 WorkBuddy 官方出品。_
