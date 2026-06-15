# 主题开发指南

MediaTree 前端主题是一个本地 JSON 文件。用户可以在 `设置 -> 界面偏好 -> 主题` 中上传、切换、删除和导出主题。

## 主题文件结构

```json
{
  "version": 1,
  "name": "my-theme",
  "label": "我的主题",
  "description": "自定义 MediaTree 主题示例",
  "author": "MediaTree user",
  "colorScheme": "dark",
  "tokens": {
    "--mt-color-bg-start": "#07120f",
    "--mt-color-bg-mid": "#101820",
    "--mt-color-bg-end": "#18151f",
    "--mt-color-bg-glow": "rgba(45, 212, 191, 0.18)",
    "--mt-color-text": "#f8fafc",
    "--mt-color-text-muted": "#a7b4c2",
    "--mt-color-surface": "rgba(255,255,255,0.08)",
    "--mt-color-surface-elevated": "rgba(255,255,255,0.13)",
    "--mt-color-border": "rgba(255,255,255,0.12)",
    "--mt-color-accent": "#2dd4bf",
    "--mt-color-accent-strong": "#fb7185",
    "--mt-radius-panel": "1.25rem",
    "--mt-shadow-glow": "0 18px 48px rgba(45, 212, 191, 0.18)"
  },
  "customCss": ".media-grid-card:hover { filter: saturate(1.08); }"
}
```

`name` 只能使用小写字母、数字、短横线和下划线，长度为 2-49 位。`colorScheme` 支持 `dark`、`light`、`auto`。主题至少要提供 `tokens` 或 `customCss`。

## 可用变量

核心页面变量：

| 变量 | 用途 |
| --- | --- |
| `--mt-color-bg-start` / `--mt-color-bg-mid` / `--mt-color-bg-end` | 页面背景渐变 |
| `--mt-color-bg-glow` | 页面背景高光 |
| `--mt-color-page-overlay` | 页面前景遮罩 |
| `--mt-color-noise-opacity` | 噪点透明度 |
| `--mt-color-text` | 主文字 |
| `--mt-color-text-muted` | 次级文字 |
| `--mt-color-text-faint` | 弱提示文字 |
| `--mt-color-surface` | 面板背景 |
| `--mt-color-surface-elevated` | 浮层/导航背景 |
| `--mt-color-surface-muted` | 卡片背景 |
| `--mt-color-surface-strong` | 深色日志/遮罩背景 |
| `--mt-color-control` | 普通按钮/控件背景 |
| `--mt-color-control-hover` | 控件 hover 背景 |
| `--mt-color-border` | 普通边框 |
| `--mt-color-border-strong` | 强边框 |
| `--mt-color-accent` | 主强调色 |
| `--mt-color-accent-strong` | 强强调色 |
| `--mt-color-accent-soft` | 弱强调底色 |
| `--mt-color-success` | 成功色 |
| `--mt-color-warning` | 警告色 |
| `--mt-color-danger` | 危险色 |
| `--mt-radius-panel` | 大面板圆角 |
| `--mt-radius-card` | 卡片/输入框圆角 |
| `--mt-radius-control` | 按钮/胶囊控件圆角 |
| `--mt-shadow-glass` | 玻璃面板阴影 |
| `--mt-shadow-card` | 卡片阴影 |
| `--mt-shadow-glow` | 强调光晕 |
| `--mt-backdrop-panel` | 面板 backdrop-filter |
| `--mt-backdrop-card` | 卡片 backdrop-filter |

播放器变量也可以覆盖，变量名以 `--player-ui-` 开头，例如：

```json
{
  "tokens": {
    "--player-ui-bottom-scrim": "linear-gradient(180deg, transparent 0%, rgba(0,0,0,0.72) 100%)",
    "--player-ui-warning-text": "#fde68a"
  }
}
```

## 自定义 CSS

`customCss` 用于补充变量无法覆盖的细节。上传时 MediaTree 会自动把普通选择器限制在当前主题根节点下，例如：

```css
.glass-panel { border-width: 1px; }
```

会被应用为：

```css
:root[data-mediatree-theme] .glass-panel { border-width: 1px; }
```

可以直接写带主题条件的选择器：

```css
:root[data-mediatree-theme="my-theme"] .media-grid-card {
  transform-origin: center;
}
```

## 安全边界

主题文件只在当前浏览器本地保存，不会上传到后端。为了避免主题造成外部请求或脚本注入，导入时会拒绝：

- `@import`
- `javascript:`
- `data:`
- 远程 `url(https://...)` 或 `url(//...)`
- `expression(...)`
- `</style>` 和 `<script>`

主题文件大小上限为 128KB，`customCss` 上限为 60KB。

## 主题包导入导出

单主题文件可以直接上传。导出的主题包结构如下：

```json
{
  "version": 1,
  "activeTheme": "my-theme",
  "themes": [
    {
      "name": "my-theme",
      "label": "我的主题",
      "tokens": {}
    }
  ]
}
```

导入主题包时，`themes` 内的所有主题会写入当前浏览器；如果 `activeTheme` 指向包内主题，会自动切换到该主题。
