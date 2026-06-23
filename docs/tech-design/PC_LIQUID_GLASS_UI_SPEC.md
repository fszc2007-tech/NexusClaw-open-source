# NexusClaw PC 端 Liquid Glass UI 优化方案

Last updated: 2026-04-24

## 1. 目标

- 为 `frontend/portal-web` 与 `frontend/admin-web` 建立统一的桌面端视觉语言。
- 保留 `NexusClaw` 在政务场景中的可信感、秩序感与高可读性，不做“炫技式”玻璃化。
- 将当前“局部半透明 + 若干渐变”的状态，升级为一套可持续扩展的 shell / surface / component 系统。
- 为后续 Figma、前端实现、动效细化提供单一执行依据。

---

## 2. 适用范围

- 平台：PC Web，优先面向 1280px 以上桌面端。
- 端：
  - `portal-web`：市民 / 访客可见的 chatbot 门户
  - `admin-web`：项目、知识、测试、日志、配置后台
- 技术约束：
  - React + Ant Design 已存在，不建议整套推翻
  - 优先复用 Ant Design 原生结构能力
  - 自定义 glass 主要用于 shell、导航、悬浮控制、对话输入 dock、上下文面板

---

## 3. 当前界面诊断

### 3.1 Portal Chatbot

- 当前首屏把品牌头、项目选择、语言切换、错误提示、服务入口、空状态、示例问题、输入框都包在同一大白盒里，层级过于扁平。
- `Gateway Timeout` 这类异常提示直接插入 header 横向布局，容易把桌面首屏压坏。
- 现有 hero 气质偏“展示页”，但真实对话区仍是传统消息流，前后语言不统一。
- 玻璃效果主要停留在大容器背景，未体现“浮动控制层”和“内容工作面”的分层逻辑。
- 输入区已接近悬浮 dock，但和消息区、推荐问题区之间仍缺少明显的深度关系。

### 3.2 Admin Console

- 登录页已经有较好的柔和玻璃雏形，但进入主后台后，整体仍偏传统 Ant Design 控制台。
- 左侧导航、顶部状态栏、工作区卡片都用了圆角和浅阴影，但缺少统一的“chrome vs content”规则。
- 顶部 header 目前把语言、项目、角色标签、退出按钮并列堆放，信息密度高但优先级不清。
- `experience/chat` 页面仍以大量 inline style 为主，和其余后台页面没有形成共享视觉系统。
- 后台首页工作台缺少“全局状态感”，看起来像若干普通卡片，而不是一个可操作的控制中枢。

---

## 4. 设计定位

### 4.1 产品 framing

- 产品类型：政务知识问答与运营管理平台
- 主用户：
  - chatbot：公众访客 / 办事用户
  - admin：运营、知识维护、测试、项目管理员
- 核心任务：
  - chatbot：快速找到可信答案或下一步办事入口
  - admin：高效维护知识、配置项目、回看日志、验证质量
- 产品模式：
  - chatbot：内容型 + 任务引导型
  - admin：工具型 + 数据操作型
- 界面气质：
  - 可信
  - 清晰
  - 克制
  - 流动
  - 专业

### 4.2 默认假设

- 本轮重点是“桌面端 UI 系统优化”，不是直接重写业务流程。
- 继续沿用现有 React + Ant Design 技术栈。
- “liquid glass” 作为视觉和交互原则使用，不做 Apple 页面照搬。
- 高密度业务内容区域保持偏实心 surface；glass 重点放在外层 shell、导航、控制区、悬浮面板。

---

## 5. 总体设计方向

### 5.1 三层结构

统一采用三层深度：

1. `Atmosphere Layer`
   - 页面背景、光晕、极淡纹理、品牌氛围色
   - 只负责气质，不承载信息

2. `Glass Chrome Layer`
   - 顶栏、侧栏、项目切换器、筛选胶囊、输入 dock、浮动工具条、轻量卡片壳
   - 特征：半透明、柔和高光、1px 内发光边、连续圆角

3. `Solid Work Surface`
   - 表格、长文、知识来源、日志详情、配置表单、聊天正文
   - 特征：更高不透明度、更稳定的排版、更少 blur，优先保证读写效率

### 5.2 核心原则

- glass 用于“控件和壳”，不是用于所有内容卡片
- 内容永远比材质更重要
- 状态反馈优先于装饰
- 交互强调连续性，不强调花哨弹跳
- 同一产品内，chatbot 与 admin 必须共享一套基础 token 和 motion 语言

---

## 6. 统一视觉系统

### 6.1 色彩策略

建议统一为 “海雾青蓝 + 冷白 + 深墨蓝” 体系。

```css
:root {
  --nx-color-bg: #edf4f7;
  --nx-color-bg-2: #f7fbfc;
  --nx-color-ink: #142331;
  --nx-color-ink-2: #51606f;
  --nx-color-primary: #2c7fb8;
  --nx-color-primary-2: #5da9d6;
  --nx-color-aqua: #73c7c7;
  --nx-color-line: rgba(255, 255, 255, 0.62);
  --nx-color-glass: rgba(255, 255, 255, 0.58);
  --nx-color-glass-strong: rgba(255, 255, 255, 0.76);
  --nx-color-surface: rgba(255, 255, 255, 0.92);
  --nx-color-surface-soft: rgba(247, 250, 252, 0.88);
  --nx-color-danger: #d95d5d;
  --nx-color-warning: #d08b2f;
  --nx-color-success: #2b9a74;
}
```

规则：

- chatbot 主色偏青蓝，增强亲和与信任。
- admin 主色偏更冷一点的蓝灰，提高工具属性。
- 风险、超时、错误统一用暖红或琥珀，不要继续混在正文布局里。

### 6.2 字体层级

- 标题：`"SF Pro Display", "PingFang SC", sans-serif`
- 正文：`"SF Pro Text", "PingFang SC", sans-serif`
- 等宽信息：日志、trace、ID 使用 `ui-monospace`

建议层级：

- Display 28/34，600
- H1 24/30，600
- H2 20/26，600
- H3 16/22，600
- Body 14/22，400
- Caption 12/18，500

### 6.3 圆角与描边

- 8: 小型 tag / state pill
- 12: input / small button
- 16: 普通卡片 / table toolbar
- 20: 中型 panel
- 28: shell card / 大型浮层 / layout 容器
- 999: capsule / chip / segmented control

描边策略：

- 玻璃壳使用 `1px rgba(255,255,255,.54)` + 轻微内阴影
- 实心工作面使用 `1px rgba(20,35,49,.06)`

### 6.4 阴影与模糊

- 大型 shell：
  - `0 24px 64px rgba(32, 64, 88, 0.12)`
- 中型浮层：
  - `0 14px 32px rgba(32, 64, 88, 0.10)`
- 控件 hover：
  - `0 8px 18px rgba(32, 64, 88, 0.10)`
- backdrop blur 建议：
  - 轻：`blur(14px)`
  - 中：`blur(20px)`
  - 强：`blur(28px)`

### 6.5 苹果原生控件取向

本项目桌面端控件默认追求的是“强 macOS / Apple app 体验”，不是普通 Web SaaS 按钮。

核心特征：

- 控件优先使用圆润连续几何，而不是锐利矩形
- 图标优先单色、细线、留白大，不做厚重填充图标
- 文案短、控件轻、状态明确，避免按钮像广告 banner
- hover 更像材质被光线扫过，而不是明显变色
- pressed 更像实体被手指轻压，而不是 CSS 按钮突变
- 输入框更像原生 macOS 搜索栏 / 文本输入场，而不是后台表单框

禁止项：

- 大面积高饱和纯色按钮排满一行
- 多层重描边 + 强发光同时出现
- 输入框 placeholder 过长、过灰、过像表单说明
- 图标和文字挤在一起，缺乏系统级留白

### 6.6 控件原生感细则

#### Primary Button

- 视觉目标：接近 macOS 强主操作按钮的克制高亮感
- 形态：44-48 高度，999 或 16 圆角
- 背景：青蓝或蓝灰 tint，不用过饱和电蓝
- 表现：
  - 默认：柔和实色 + 轻高光
  - hover：仅略微提亮和上浮
  - active：`scale(0.985)` + 高光收紧
- 文案：1 到 4 个字优先，最多一行

#### Secondary / Toolbar Button

- 视觉目标：像原生 toolbar control
- 形态：36-40 高度，999 胶囊或 14 圆角
- 背景：半透明 glass
- 边界：`1px` 浅亮边，不做明显硬边框
- 使用位置：
  - chatbot 顶部控制
  - admin toolbar
  - 右侧 inspector 操作

#### Icon Button

- 视觉目标：像 macOS window chrome / quick action
- 尺寸：
  - 常规：36x36
  - 重点输入 dock：40x40
- 图标：
  - 16-18px
  - 线性、统一 stroke
  - 视觉中心必须垂直水平居中
- 反馈：
  - hover：底色轻起雾
  - active：轻压 + 内阴影增强

#### Image Picker Button

- 这是本项目必须强化苹果感的重点控件。
- 角色：聊天中的“选图 / 上传附件 / 选择文件”
- 不应做成传统带边框上传按钮，应更接近 iMessage / Notes / Finder quick attach action
- 推荐两种形态：
  - `icon-only circular glass button`
  - `icon + short label capsule`
- 优先级：
  - 在 composer 内时：优先 icon-only
  - 在空态引导区时：可用 icon + label
- 图标建议：
  - 图片：`photo` / `image`
  - 文件：`paperclip`
  - 扫描：`doc.viewfinder` 语义的替代图标
- 交互：
  - hover 出现轻高光环
  - 点击后打开系统选择流程前，要有明显“被按下”的物理反馈
  - 选中图片后，按钮应切换为“已附加”状态，而不是保持无状态

#### Input / Textarea

- 视觉目标：接近 macOS 搜索栏与原生输入场的混合体验
- 高度：
  - 单行输入：44
  - composer textarea 外壳：56-64 起
- 结构：
  - 外层是 glass dock
  - 真正文字输入区是更清爽的内层 surface
- 细节：
  - placeholder 必须短
  - caret 和 focus ring 要明显但不刺眼
  - focus 时优先通过外层 halo 和边光表达，不要用粗蓝边框
- 禁止：
  - 多层边框
  - 默认就有明显阴影
  - focus 时突然变成浓蓝色 Ant Design 风格

#### Select / Segmented Control

- 视觉目标：接近 macOS segmented control / filter pill group
- 适用：
  - chat 模式切换
  - admin 状态筛选
  - 精准 / 标准 / 深度等模式切换
- 规则：
  - 容器整体是淡 glass
  - 选中项像被“推起”的实心药丸
  - 文案长度保持短促
  - 切换过渡强调平移和材质连续，不做大幅颜色闪烁

#### Search Field

- 左侧永远预留系统感搜索图标位
- 输入区比普通表单更像工具栏搜索
- 清空按钮、筛选前缀、项目范围标签都应作为内嵌胶囊，不要零碎外挂

---

## 7. Portal Chatbot 桌面端方案

### 7.1 页面结构

桌面端建议从“一个大白盒”升级成 `三段式聊天舞台`：

1. `Top Trust Bar`
   - 品牌、当前机构 / 项目、语言、系统状态
   - 错误提示不要横向挤在选择器旁边，应进入独立状态条

2. `Conversation Stage`
   - 左：机构信息 / 快捷入口 / 推荐主题
   - 中：对话流 + empty state + scene 卡片
   - 右：来源摘要 / 当前对话状态 / 最近推荐问题

3. `Composer Dock`
   - 固定在底部中央
   - 独立悬浮，不直接贴死内容面板底边

### 7.2 关键页面状态

#### A. 首屏未开始对话

- 左侧显示：
  - 项目身份 / 知识空间身份
  - 可信说明
  - 3-4 个服务分组入口
- 中间显示：
  - 欢迎说明
  - 推荐问题胶囊
  - 空态插图或抽象轨迹
- 右侧显示：
  - 可咨询范围
  - 示例问题
  - 系统状态

不再把所有内容堆在同一块白底 panel 里。

#### B. 对话进行中

- 左栏弱化为 slim rail，只保留项目切换和快捷入口
- 中间成为主要消息舞台
- 右栏切换为 `Sources / Context / Action` inspector

#### C. Scene / 表单引导模式

- 右栏升级为步骤上下文面板
- 中间消息流上方出现“当前办理任务” glass capsule
- 底部 composer 在 scene 收集模式下切换为单字段采集 dock

### 7.3 Portal 组件规则

#### `PortalShellBar`

- 角色：品牌和全局状态壳
- 形态：28px 圆角玻璃横条
- 内容：logo、产品名、项目选择器、语言切换、状态按钮
- 异常提示：作为单独 `Inline Status Ribbon` 出现在 bar 下方

#### `TrustPanel`

- 角色：解释这是可信官方/机构知识入口
- 形态：实心浅面板，局部使用 glass header
- 不要全玻璃，否则大段文字发虚

#### `ServiceEntryCard`

- 角色：承接“我要做什么”
- 形态：实心主卡 + 轻 glass 头部 + hover 浮起
- 每张卡只保留标题、描述、箭头，不要过多文本

#### `ConversationSurface`

- 角色：承载消息流
- 形态：高不透明度工作面
- 气泡上方可有轻玻璃 assistant identity badge
- 用户气泡更实色，助手气泡更浅

#### `SourceInspectorCard`

- 角色：展示来源、得分、摘要、跳转动作
- 形态：右侧可折叠 inspector stack
- 单条来源不要做太厚的重卡片，避免像后台表单

#### `ComposerDock`

- 角色：核心输入控制
- 形态：999 胶囊 + 玻璃底 + 内发光边
- 内部分三段：
  - mode/status
  - textarea
  - send / voice / action
- 苹果原生感要求：
  - 左侧 `选图 / 附件` 按钮优先做成 40x40 圆形 glass icon button
  - 中间输入区要像原生消息输入场，不像后台表单
  - 发送按钮应像被包进 dock 内的主操作 capsule，而不是外接普通 Button
  - 所有 action icon 的 stroke、尺寸、光泽感必须统一

#### `PromptChip`

- 角色：推荐问题 / 快捷追问
- 形态：半透明胶囊
- hover 时轻微上浮和描边提亮

#### `AttachmentPreviewStrip`

- 角色：展示已选择图片 / 文件
- 位置：composer dock 上方或 dock 内上缘
- 形态：一排 mini glass tiles
- 要求：
  - 缩略图有连续圆角和细高光边
  - 删除按钮必须是独立小圆点 icon control
  - 已附加状态要明显比“未附加”更接近系统原生附件感

### 7.4 Portal 布局建议

- `>= 1440px`
  - 左 280 / 中 1fr / 右 320
- `1280px - 1439px`
  - 左 240 / 中 1fr / 右 280
- `< 1280px`
  - 右侧 inspector 收到 Drawer
  - 左栏压缩为顶部可展开导航

### 7.5 Portal 当前代码落点

优先影响文件：

- `frontend/portal-web/src/pages/Chat.tsx`
- `frontend/portal-web/src/global.css`
- `frontend/portal-web/src/app.tsx`
- `frontend/portal-web/src/components/PortalPage.tsx`

建议：

- 先把 header / status / left rail / right inspector 从现有单列结构中拆出来
- 再统一 composer、bubble、prompt chip 的视觉层级

---

## 8. Admin Console 桌面端方案

### 8.1 页面结构

后台建议采用 `Command Center Shell`：

1. `Floating Sider`
   - 独立悬浮在背景上
   - 更像指挥台而不是普通白色菜单栏

2. `Context Header`
   - 仅保留当前页面标题、项目上下文、全局操作
   - 不要把所有筛选器和身份 tag 全堆在一行

3. `Work Surface`
   - 真正操作区域保持更稳、更实心
   - 表格、表单、编辑器尽量减少 blur

4. `Inspector / Utility Rail`
   - 对知识详情、日志详情、来源面板、测试任务侧栏统一复用

### 8.2 Admin 首页工作台

当前工作台更像“导航列表”。建议改为：

- 上部：项目运行概览
  - 当前项目
  - 知识库数量
  - 最近测试状态
  - 最近告警 / 异常
- 中部：主任务入口
  - 知识维护
  - 体验验证
  - 日志排查
  - 项目配置
- 右侧：最近动作与建议
  - 最近上传文件
  - 最近失败测试
  - 待处理风险

形成“总览 + 行动 + 异常”的后台首屏结构。

### 8.3 Admin 关键页面策略

#### 项目 / 知识 / 测试 / 日志列表页

- 使用实心表格区 + glass toolbar
- toolbar 内容：
  - 页面标题
  - 搜索
  - 筛选 capsule
  - 主操作按钮
- 表格上方保留 summary strip，避免用户只看到表格

#### 配置页（Opening / Prompt / Memory）

- 左：说明和影响范围
- 中：主表单
- 右：预览 / 注意事项 / 最近发布时间

#### 体验广场 Chat

- 不要继续用独立 inline style 聊天气泡体系
- 直接复用 portal 的 conversation 语言，但更偏“调试态”
- 增加 trace、rewritten query、sources 的 inspector 式查看

### 8.4 Admin 组件规则

#### `AdminSiderShell`

- 角色：主导航外壳
- 形态：28 圆角、轻玻璃、浅描边
- 一级菜单高亮采用“内嵌发光条 + 柔和填色”

#### `ProjectContextBar`

- 角色：承载项目切换、角色、环境、快捷动作
- 形态：横向 glass bar
- 内容分组：
  - 左：当前页标题 / 项目
  - 中：环境 / 项目切换
  - 右：身份 / 全局动作
- 苹果原生感要求：
  - Select 不直接裸露 Ant Design selector 外观
  - 项目切换器要更像原生 toolbar picker
  - 角色 tag 不应像运营标签墙，而应弱化成系统状态 badge

#### `MetricGlassCard`

- 角色：工作台指标卡
- 形态：玻璃外壳 + 实色数字核心
- 不要把大段描述塞进去

#### `WorkPanel`

- 角色：表格、表单、日志、列表主内容容器
- 形态：高不透明度白色工作面
- 标题区可轻 glass，正文保持实心

#### `FilterCapsuleGroup`

- 角色：筛选和状态切换
- 形态：999 胶囊分组
- 被选中项使用轻 tint，不使用过强纯色块
- 目标质感：接近原生 segmented control，而不是普通 tabs

#### `ToolbarSearchField`

- 角色：后台列表页搜索
- 形态：原生搜索场风格
- 要求：
  - 左搜索 icon 常驻
  - 清空按钮使用小圆形 icon control
  - 搜索框与筛选胶囊在视觉上属于同一条 toolbar 语言

#### `InspectorDrawer`

- 角色：日志详情、知识来源、测试样本详情
- 形态：右侧抽屉统一为高圆角大 panel

### 8.5 Admin 当前代码落点

优先影响文件：

- `frontend/admin-web/src/layouts/index.tsx`
- `frontend/admin-web/src/global.css`
- `frontend/admin-web/src/components/AdminPage.tsx`
- `frontend/admin-web/src/pages/Workbench.tsx`
- `frontend/admin-web/src/pages/experience/Chat.tsx`
- `frontend/admin-web/src/app.tsx`

建议：

- 第一轮先做 layout shell 和 workbench
- 第二轮统一表格页 toolbar / panel / filters
- 第三轮才细化 experience/chat 与 inspector

---

## 9. 统一组件边界

以下组件应尽量共享设计语义：

### 保持 Ant Design 原生为主

- Table
- Tabs
- Modal
- Drawer
- Select
- Input
- Button
- Tag

### 允许做自定义 glass 包装

- App shell
- Header / Sider 外壳
- Project switcher 容器
- Composer dock
- Capsule filter
- Prompt chip
- Source inspector
- Top status ribbon

### 不建议过度玻璃化

- 长表格主体
- 长文内容
- 日志正文
- 表单主编辑区
- 大段知识来源 snippet

---

## 10. Motion 规范

### 10.1 交互节奏

- hover 提亮：120ms - 160ms
- 按下压缩：80ms - 120ms
- 松开回弹：180ms - 240ms
- panel 出入场：220ms - 280ms
- drawer / inspector：260ms - 320ms

### 10.2 建议 starter values

```css
--nx-ease-standard: cubic-bezier(0.22, 1, 0.36, 1);
--nx-ease-soft: cubic-bezier(0.2, 0.8, 0.2, 1);
--nx-scale-press: 0.985;
--nx-lift-hover: translateY(-2px);
```

### 10.3 动效原则

- 只做轻微位移、透明度变化、边光变化
- 不做夸张缩放和大幅弹跳
- 对话发送按钮和 chip 可有微弱流光，但不能持续抢戏
- reduced motion 下应退化为纯 opacity / color 变化

---

## 11. 状态设计

### 11.1 错误状态

- 错误信息必须从正文布局中剥离出来
- chatbot 的超时、知识库未加载、项目为空，统一走 `Status Ribbon + Retry Button`
- admin 的权限不足、数据加载失败、无项目上下文，统一走 `Page Alert + Recovery Action`

### 11.2 空状态

- chatbot 空态强调“你可以问什么”
- admin 空态强调“下一步做什么”
- 所有空态都要有一主一辅两个动作

### 11.3 权限状态

- admin 中不可见优先于禁用
- 必须保留“为什么不可操作”的解释文本

---

## 12. 实施顺序

### Phase 1: Foundations

- 抽离统一 token
- 清理 portal / admin 各自分裂的背景、阴影、圆角规则
- 统一 glass shell 与 solid surface 的 CSS 命名

### Phase 2: Portal Shell

- 重构 `Chat.tsx` 顶部结构
- 拆出 `PortalShellBar`
- 引入左 rail / 右 inspector / 底部 dock
- 把错误提示从主 header 中拆开

### Phase 3: Admin Shell

- 重构 `layouts/index.tsx`
- 重新组织 header 信息优先级
- 重做 `Workbench.tsx` 为控制中枢页

### Phase 4: Shared Business Components

- 统一 source card、status chip、filter capsule、inspector drawer
- admin experience/chat 与 portal chat 共享消息和来源语言

### Phase 5: High-density Pages

- 知识库、日志、测试、项目列表页统一 table toolbar 方案
- 处理 loading / empty / error / permission 全套状态

---

## 13. Codex 落地提示词

### 13.1 Portal 重构 prompt

```text
请在 frontend/portal-web 中重构桌面端聊天页，目标是建立“glass shell + solid conversation surface”结构，而不是继续把所有模块堆在单一白色大卡片里。

要求：
- 保留现有业务逻辑和数据流
- 头部拆成品牌/项目/语言/状态的独立 shell bar
- 主体改为三栏：left trust rail / center conversation / right context inspector
- composer 做成独立底部悬浮 dock
- 错误提示从 header 行内移出，改成独立 status ribbon
- 优先修改 Chat.tsx、global.css、app.tsx，不先拆大范围业务组件
- 保持 Traditional Chinese 文案可读性
```

### 13.2 Admin Shell 重构 prompt

```text
请在 frontend/admin-web 中把后台桌面端 UI 从“普通 Ant Design 后台”升级为“command center shell”。

要求：
- 保留现有路由和权限逻辑
- 左侧导航、顶部上下文栏、主工作面形成明确三层
- 表格/表单区保持高可读性，不要过度毛玻璃
- 先统一 layout、AdminPage、Workbench 三个层级
- 减少页面内联样式，往 global.css 或共享组件收敛
- 统一圆角、描边、hover、阴影与 tag/button 语义
```

### 13.3 Shared Token Prompt

```text
请为 NexusClaw 的 portal-web 和 admin-web 建立共享的桌面端 liquid-glass token 体系。

输出：
- CSS variables
- glass shell / solid surface / capsule / status ribbon 四类基础样式
- motion tokens
- dark text on light glass 的可读性保障规则
- reduced motion / reduced transparency fallback
```

---

## 14. 质量检查清单

- chatbot 与 admin 是否看起来属于同一产品，而不是两个主题包
- glass 是否集中在导航、控制、悬浮层，而不是覆盖所有内容卡片
- 表格、日志、知识正文是否仍然足够稳定、易读
- 错误、空态、权限态是否被单独设计，而不是临时插入布局
- 桌面端是否明确利用左右栏和 inspector，而不是把移动端结构简单放大
- portal 的“可信感”和 admin 的“高效感”是否都被保留
- 实现层面是否能在现有 React + Ant Design 基础上渐进升级

---

## 15. 下一步建议

推荐按以下顺序进入开发：

1. 先做共享 token 与 shell 层，不急着改全部业务页
2. 优先重构 `portal-web/src/pages/Chat.tsx`
3. 再重构 `admin-web/src/layouts/index.tsx` 与 `pages/Workbench.tsx`
4. 最后把 `admin-web/src/pages/experience/Chat.tsx` 对齐到统一对话语言

如果需要进一步出图，可基于本文件继续补一份 Figma frame 清单和桌面端页面 wireframe。
