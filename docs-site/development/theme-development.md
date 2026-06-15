# 主题开发指南

MediaTree 主题是一个本地主题文件。用户可以在 `设置 -> 界面偏好 -> 外观主题` 中导入和切换主题。主题文件只保存在当前浏览器，不会上传到后端。

主题适合做大范围视觉改造，例如把默认玻璃质感改成更接近 MD3 / Material You 的实色容器、圆润控件、低阴影层级和浅色文字体系。主题不是插件：它不能执行 JavaScript，不能改页面结构，不能新增业务交互，也不能加载远程资源。

## 能改到哪些地方

主题文件可以覆盖：

- 页面背景、文字颜色、强调色、成功/警告/危险色。
- 面板、卡片、弹窗、按钮、输入框、标签、媒体卡片的背景、边框、圆角、阴影和模糊。
- 全局字体、内容最大宽度、页面间距、常用动效时长和界面密度。
- 播放器控制层的颜色、遮罩、警告提示和浮层样式。
- 使用稳定选择器补充 CSS，以实现类似 MD3 的组件外观重塑。

主题文件不能覆盖：

- 路由结构、页面内容顺序、数据来源和业务逻辑。
- React 组件渲染逻辑、按钮行为、播放器能力判断。
- 任意脚本、HTML 注入、远程图片/字体/CSS 加载。

## 主题文件结构

```json
{
  "schemaVersion": 2,
  "name": "my-advanced-skin",
  "label": "我的高级外观",
  "description": "把 MediaTree 调整为实色容器和圆润控件的主题。",
  "author": "MediaTree user",
  "version": "1.0.0",
  "capabilities": ["tokens", "custom-css", "stable-selectors", "layout", "density", "motion"],
  "colorScheme": "light",
  "tokens": {
    "--mt-font-family": "Inter, \"Noto Sans SC\", \"Microsoft YaHei\", sans-serif",
    "--mt-density-scale": "0.96",
    "--mt-layout-content-max": "92rem",
    "--mt-layout-gap": "1rem",
    "--mt-layout-page-padding-x": "1.25rem",
    "--mt-layout-page-padding-y": "1.25rem",
    "--mt-layout-page-padding-x-wide": "1.5rem",
    "--mt-layout-page-padding-y-wide": "1.5rem",
    "--mt-motion-fast": "140ms",
    "--mt-motion-normal": "240ms",
    "--mt-theme-style": "advanced-skin",
    "--mt-color-bg-start": "#f8fafc",
    "--mt-color-bg-mid": "#eef6f6",
    "--mt-color-bg-end": "#f7f1fb",
    "--mt-color-bg-glow": "rgba(20, 184, 166, 0.14)",
    "--mt-color-text": "#111827",
    "--mt-color-text-muted": "#4b5563",
    "--mt-color-text-faint": "#6b7280",
    "--mt-color-surface": "rgba(255,255,255,0.82)",
    "--mt-color-surface-elevated": "rgba(255,255,255,0.94)",
    "--mt-color-surface-muted": "rgba(15,23,42,0.055)",
    "--mt-color-surface-container": "#eef6f6",
    "--mt-color-surface-container-high": "#e7f0f3",
    "--mt-color-border": "rgba(15,23,42,0.12)",
    "--mt-color-border-strong": "rgba(15,23,42,0.2)",
    "--mt-color-accent": "#0f766e",
    "--mt-color-accent-strong": "#7c3aed",
    "--mt-color-accent-soft": "rgba(15,118,110,0.14)",
    "--mt-radius-panel": "24px",
    "--mt-radius-card": "18px",
    "--mt-radius-control": "999px",
    "--mt-shadow-glass": "0 16px 40px rgba(15, 23, 42, 0.12)",
    "--mt-shadow-card": "0 10px 28px rgba(15, 23, 42, 0.1)",
    "--mt-shadow-glow": "0 12px 32px rgba(15, 118, 110, 0.14)",
    "--mt-shadow-elevation-1": "0 1px 3px rgba(15, 23, 42, 0.08)",
    "--mt-shadow-elevation-2": "0 8px 22px rgba(15, 23, 42, 0.1)",
    "--mt-shadow-elevation-3": "0 18px 42px rgba(15, 23, 42, 0.12)",
    "--mt-backdrop-panel": "none",
    "--mt-backdrop-card": "none"
  },
  "customCss": ".mt-panel { border-width: 1px; }\n.mt-topbar .liquid-glass { background: var(--mt-color-surface-container-high); }\n.mt-media-card:hover { filter: saturate(1.08); transform: translateY(-3px); }"
}
```

`name` 只能使用小写字母、数字、短横线和下划线，长度为 2-49 位。`colorScheme` 支持 `dark`、`light`、`auto`。主题至少要提供 `tokens` 或 `customCss`。

`schemaVersion` 描述主题文件结构版本；旧主题不写也可以继续导入。`capabilities` 是给主题作者和维护者看的能力说明，当前支持 `tokens`、`custom-css`、`stable-selectors`、`layout`、`density`、`motion`。

## 常用变量

全局与布局变量：

| 变量 | 用途 |
| --- | --- |
| `--mt-font-family` | 全局字体 |
| `--mt-density-scale` | 主题密度描述，供主题和自定义 CSS 复用 |
| `--mt-layout-content-max` | 主内容最大宽度 |
| `--mt-layout-gap` | 主题通用间距 |
| `--mt-layout-page-padding-x` / `--mt-layout-page-padding-y` | 小屏页面内容区内边距 |
| `--mt-layout-page-padding-x-wide` / `--mt-layout-page-padding-y-wide` | 宽屏页面内容区内边距 |
| `--mt-motion-fast` / `--mt-motion-normal` | 常用过渡时长 |
| `--mt-theme-style` | 主题风格标记，便于自定义 CSS 判断 |

核心颜色变量：

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
| `--mt-color-surface-muted` | 低强调卡片背景 |
| `--mt-color-surface-container` | 容器背景，适合 MD3 实色卡片 |
| `--mt-color-surface-container-high` | 高层级容器背景 |
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

形状、阴影和模糊变量：

| 变量 | 用途 |
| --- | --- |
| `--mt-radius-panel` | 大面板/弹窗圆角 |
| `--mt-radius-card` | 卡片/输入框圆角 |
| `--mt-radius-control` | 按钮/胶囊控件圆角 |
| `--mt-shadow-glass` | 主面板阴影 |
| `--mt-shadow-card` | 卡片阴影 |
| `--mt-shadow-glow` | 强调按钮光晕 |
| `--mt-shadow-elevation-1` / `--mt-shadow-elevation-2` / `--mt-shadow-elevation-3` | 层级阴影 |
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

## 稳定选择器

高级主题应优先使用 `.mt-*` 选择器。这些选择器会尽量保持稳定，比直接覆盖 Tailwind 工具类更适合长期维护。

| 选择器 | 用途 |
| --- | --- |
| `.mt-app-shell` | 应用根容器 |
| `.mt-topbar` | 顶部导航区域 |
| `.mt-content` | 主内容区域 |
| `.mt-panel` | 页面面板 |
| `.mt-card` | 通用卡片 |
| `.mt-media-card` | 媒体封面卡片 |
| `.mt-button` | 普通按钮 |
| `.mt-button-primary` | 主按钮 |
| `.mt-input` | 输入框/选择框 |
| `.mt-chip` | 标签/胶囊信息 |
| `.mt-popover` | 弹出层 |
| `.mt-dialog` | 弹窗 |

旧的 `.glass-*` 和 `.media-grid-card` 仍然可用，但新主题建议使用 `.mt-*`。

## MD3 风格示例

以下片段展示了如何把玻璃质感改成更接近 MD3 的实色容器：

```json
{
  "schemaVersion": 2,
  "name": "material-like",
  "label": "Material 风格",
  "colorScheme": "light",
  "capabilities": ["tokens", "custom-css", "stable-selectors", "layout", "motion"],
  "tokens": {
    "--mt-font-family": "Roboto, \"Noto Sans SC\", \"Microsoft YaHei\", sans-serif",
    "--mt-color-bg-start": "#fffbfe",
    "--mt-color-bg-mid": "#f8f2fb",
    "--mt-color-bg-end": "#fdf8fd",
    "--mt-color-text": "#1d1b20",
    "--mt-color-text-muted": "#49454f",
    "--mt-color-surface": "#fffbfe",
    "--mt-color-surface-container": "#f3edf7",
    "--mt-color-surface-container-high": "#ece6f0",
    "--mt-color-accent": "#6750a4",
    "--mt-color-accent-strong": "#006a6a",
    "--mt-radius-panel": "28px",
    "--mt-radius-card": "16px",
    "--mt-radius-control": "999px",
    "--mt-shadow-glass": "0 1px 2px rgba(29, 27, 32, 0.08), 0 1px 3px rgba(29, 27, 32, 0.08)",
    "--mt-shadow-card": "0 1px 2px rgba(29, 27, 32, 0.08)",
    "--mt-shadow-glow": "none",
    "--mt-backdrop-panel": "none",
    "--mt-backdrop-card": "none"
  },
  "customCss": ".mt-topbar .liquid-glass { background: var(--mt-color-surface-container); }\n.mt-media-card { box-shadow: var(--mt-shadow-card); }\n.mt-button-primary { box-shadow: none; }"
}
```

上面的主题文件结构可作为高级主题模板，用于本地调试和二次调整。

## 自定义 CSS

`customCss` 用于补充变量无法覆盖的细节。导入时 MediaTree 会自动把普通选择器限制在当前主题根节点下，例如：

```css
.mt-panel { border-width: 1px; }
```

会被应用为：

```css
:root[data-mediatree-theme] .mt-panel { border-width: 1px; }
```

可以直接写带主题条件的选择器：

```css
:root[data-mediatree-theme="my-advanced-skin"] .mt-media-card {
  transform-origin: center;
}
```

如果要做大改造，建议先用 token 建立颜色、间距、圆角和阴影体系，再用 `customCss` 少量覆盖稳定选择器。不要覆盖过多内部实现类，否则后续页面结构调整时维护成本会明显升高。

## 安全边界

为了避免主题造成外部请求或脚本注入，导入时会拒绝：

- `@import`
- `javascript:`
- `data:`
- 远程 `url(https://...)` 或 `url(//...)`
- `expression(...)`
- `</style>` 和 `<script>`

主题文件大小上限为 128KB，`customCss` 上限为 60KB。

## 主题包格式

单主题文件可以直接导入。多个主题也可以整理成如下主题包结构后导入：

```json
{
  "version": 2,
  "activeTheme": "my-advanced-skin",
  "themes": [
    {
      "schemaVersion": 2,
      "name": "my-advanced-skin",
      "label": "我的高级外观",
      "tokens": {}
    }
  ]
}
```

导入主题包时，`themes` 内的所有主题会写入当前浏览器；如果 `activeTheme` 指向包内主题，会自动切换到该主题。
