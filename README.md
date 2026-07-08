# workbuddy-auto-signin

WorkBuddy 桌面应用（腾讯云 CodeBuddy AI 助手）**自动签到工具**，通过图像识别 + 坐标点击实现每日积分领取。

> ⚠️ **仅支持 Windows** — 依赖 Win32 API (`ctypes`)、`pyautogui`、`PIL`、`OpenCV`。

## 🎯 主要能力

- **自适应坐标**：使用百分比定位，自动适配不同窗口大小和屏幕分辨率
- **OpenCV 按钮检测**：自动识别"立即领取"按钮位置，无需手动配置坐标
- **窗口管理**：自动处理最小化窗口、多显示器、窗口激活（v9 起**单次**激活，避免轰炸 Electron 主线程）
- **双点击触发**：正确使用双击（单击无法触发签到）
- **v9.2 安全机制**：锁屏守卫、面板打开像素校验+重试、按钮检测 sanity-check、真实错误状态、签后清理面板——彻底解决旧版导致 WorkBuddy 卡死的问题
- **调试模式**：`--debug` 保存每步截图，`--check-lock` 仅检测锁屏

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

# 仅检测当前是否锁屏（不点击）
python scripts/auto_signin.py --check-lock
```

## 📝 工作原理（v9.2）

由于 WorkBuddy 是 **Electron 应用**，其内部 DOM 元素无法通过标准无障碍 API 访问（`pywinauto` UIA 只能看到 `Chrome Legacy Window`）。本 Skill 采用 **视觉方案**，并在 v9.2 加入多重安全守卫以避免旧版的"卡死"问题：

0. **锁屏守卫**：交互前通过 `OpenInputDesktop` 检查当前桌面，若处于锁屏（Winlogon 安全桌面）则立即中止，不向虚空发送点击
1. **窗口管理**：Win32 `EnumWindows` 查找窗口，最小化则恢复，移动到主显示器（v9 起单次 `SetWindowPos`，不再反复激活）
2. **打开面板 + 校验**：点击左下角头像弹出签到面板，随后**对比截图像素验证面板是否真的打开**（真实打开变化 ≥3%）。未打开则按 `Escape` 再重试一次；仍失败则中止（可能处于非主界面视图，如 NRC 面板）
3. **按钮检测**：**OpenCV 灰度阈值（<120）** 在绿色卡片区域检测深色"立即领取"按钮，并做 sanity-check（够暗、尺寸合理）；失败则回退配置坐标
4. **执行签到**：**双击**按钮（单击只会选中但不会执行！）
5. **结果 + 清理**：捕获结果截图，再按 `Escape` **关闭面板**，避免 WorkBuddy 残留半开界面看起来像卡死

### 状态与可靠性

脚本返回 JSON 字典，**`status` 为 `success` 或 `error`，不再有静默假成功**：

- `"success"`：面板已打开且双击序列已执行（确认 UI 交互完成，但不 OCR 校验"领取成功"提示条）
- `"error"` 含 `reason` 字段，安全中止且不点错目标：
  - `"screen_locked"`：处于锁屏，登录后运行
  - `"panel_not_opened"`：头像点击未打开面板（多为非主界面视图），切回主界面重试
  - `"window_not_found"`：WorkBuddy 未运行

## ⚙️ 配置说明

配置文件：`config/signin_config.json`

```json
{
  "avatar_click": {
    "x_percent": 0.0317,
    "y_from_bottom_percent": 0.0533
  },
  "signin_button": {
    "x_percent": 0.06,
    "y_percent": 0.569,
    "click_method": "double"
  }
}
```

### 坐标系统（自适应）

| 元素 | 位置 | 说明 |
|------|--------|------|
| 用户头像 | 左侧 3.17%，底部往上 5.33% | 点击打开签到面板 |
| 签到按钮 | 左侧 6.00%，顶部往下 56.90% | "立即领取"按钮 |

**自适应说明**：坐标为百分比格式，自动根据窗口大小计算绝对坐标，适配不同屏幕分辨率。

## 🔧 故障排除

| 现象 | 原因 | 解决方法 |
|------|------|----------|
| `WorkBuddy window not found` | 应用未运行 | 先启动 WorkBuddy |
| `reason: screen_locked` | 处于锁屏状态 | 登录 / 解锁后运行 |
| `reason: panel_not_opened` | 处于非主界面视图（如 NRC 面板） | 切回主界面，重新运行 |
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
| `references/technical_notes.md` | 技术文档（调试历史、像素映射、卡死修复分析） |
| `debug_enum.py` | 诊断工具：枚举 WorkBuddy 窗口与 PID |
| `templates/` | 调试截图保存目录（`.gitignore` 已忽略） |

## 📌 重要技术要点

- **为什么必须双击？** 单击只会选中按钮，不会触发签到动作
- **为什么用百分比坐标？** 适配不同窗口大小和屏幕分辨率
- **为什么用 OpenCV？** Electron 应用不向外暴露 UI 元素，只能通过图像识别
- **为什么加锁屏守卫？** 凌晨 4 点自动化运行时 PC 可能锁屏，不加守卫点击落空、`ImageGrab` 会截到安全桌面
- **为什么做像素校验？** 旧版面板没打开仍盲目双击，点到错误 UI 并让 WorkBuddy 卡死；v9.2 改为未打开即中止
- **为什么签后清理面板？** 残留半开的签到浮层会让 WorkBuddy 看起来像卡死，`Escape` 可干净关闭

## 📄 许可证

MIT License

---

_声明：本工具并非 WorkBuddy 官方出品。_
