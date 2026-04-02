# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 仓库定位

这是一个 MoviePilot 插件仓库，不是 MoviePilot 主程序仓库。

- 根目录 `package.json` 是 MoviePilot 使用的插件市场索引。
- 运行时代码位于 `plugins/` 和 `plugins.v2/`。
- `icons/` 存放可复用的插件图标。
- `README.md` 是主要的插件开发说明，定义了插件扩展点和约定。

本仓库没有定义仓库级的 build、lint 或 test 流程。

## 常用命令

### 查看插件元数据

```bash
python -m json.tool package.json
```

用于检查插件元数据，包括版本号、标签、图标以及 `"v2": true` 标记。

### 安装单个插件依赖

```bash
pip install -r plugins/<plugin_name>/requirements.txt
pip install -r plugins.v2/<plugin_name>/requirements.txt
```

依赖按插件维度维护，不在仓库根目录统一维护。

### 校验单个改动文件语法

```bash
python -m py_compile plugins/<plugin_name>/__init__.py
python -m py_compile plugins.v2/<plugin_name>/__init__.py
```

如果插件拆成多个 Python 文件，直接校验你修改过的那个文件。

### 运行单个测试

本仓库没有顶层测试套件。如果某个插件或外部配套环境提供了测试，使用标准 `pytest` 定位方式：

```bash
pytest path/to/test_file.py
pytest path/to/test_file.py -k <pattern>
pytest path/to/test_file.py::test_name
```

### 实际验证方式

大多数插件只能在 MoviePilot 实例中做真实验证，因为它们依赖宿主提供的模块，例如 `app.plugins._PluginBase`、`app.core.event`、`app.schemas`、`app.chain.*`、`app.db.*`。

## 架构概览

### 插件市场元数据 + 插件实现代码

这个仓库包含两层内容：

1. 根目录 `package.json`：所有插件的市场展示元数据
2. 各插件目录：实际运行的插件代码

当你修改插件版本时，必须同时保持两处一致：

- `__init__.py` 中的插件类元数据
- 根目录 `package.json` 中对应插件条目

MoviePilot 依赖这里的版本变化来识别插件更新。

### 插件目录结构

- `plugins/`：经典插件，通常以单个 `__init__.py` 为中心
- `plugins.v2/`：MoviePilot V2 插件，通常会使用更丰富的链式事件、异步服务、仪表板或远程前端资源

根据 `README.md` 的约定，每个插件必须放在独立目录中，目录名必须是插件类名的小写形式，主类放在该目录的 `__init__.py` 中。

### 常见插件契约

大多数插件继承 `app.plugins._PluginBase`，常见方法包括：

- `init_plugin(config)`
- `get_state()`
- `get_command()`
- `get_api()`
- `get_service()`
- `get_form()`
- `get_page()`

修改时优先参考现有插件实现，不要自行发明新的插件组织方式。

### 事件驱动集成

这个仓库最核心的扩展方式是 MoviePilot 事件总线。

本仓库中常见的 `EventType` 用法包括：

- `PluginAction`：远程命令和用户触发动作
- `NoticeMessage`：通知渠道插件
- `UserMessage`：对话类插件
- `TransferComplete`：整理/入库后的自动化处理
- `WebhookMessage`：媒体服务器集成
- `SiteDeleted`、`SiteRefreshed`、`DownloadAdded`、`PluginReload`：领域工作流事件

V2 插件还会使用 `ChainEventType`，例如：

- `NameRecognize`
- `DiscoverSource`
- `RecommendSource`
- `MediaRecognizeConvert`
- `TransferRename`

### UI 模式

大部分插件通过 Vuetify 风格的 JSON 结构定义配置 UI，常见组件包括 `VForm`、`VRow`、`VCol`、`VSwitch`、`VTextField`、`VAlert`。

部分 V2 插件还会携带远程前端资源。`plugins.v2/clashruleprovider/` 是最典型的参考：

- 后端 Python 插件 + service 层 + API 层
- `get_render_mode()` 返回 `("vue", "dist/assets")`
- 前端构建产物提交在 `dist/assets/`
- 仪表板集成通过 `get_dashboard_meta()` / `get_dashboard()` 完成

如果只看到构建产物，不要假设仓库里一定存在前端源码。

### 复杂度模式

简单插件通常是单文件实现。

更复杂的插件会拆出 helper、service 或 API 模块，例如：

- 与入口同目录的辅助文件：`openai.py`、`helper.py`、`ffmpeg_helper.py`、`iyuu_helper.py`
- V2 的 service / API 拆分：`plugins.v2/clashruleprovider/api.py`、`plugins.v2/clashruleprovider/services.py`

修改时优先匹配目标插件原有的复杂度和分层，不要无谓引入新结构。

## 重要仓库规则

- 插件元数据必须保持 `__init__.py` 与根目录 `package.json` 同步。
- 不要为插件专属依赖新增根级依赖清单，应使用插件目录下的 `requirements.txt`。
- 插件 API 是通过 `get_api()` 返回路由元数据暴露给 MoviePilot 的，不是自己启动独立服务。
- 定时任务应遵循插件既有模式：要么通过 `get_service()`，要么沿用插件自身初始化时创建 scheduler 的方式。
- 插件图标要么复用 `icons/` 中已有图标，要么使用完整的 HTTP URL。
- 避免使用与官方插件冲突的插件名称，否则上游升级时可能被覆盖。

## 高价值参考插件

- `plugins/autobackup/__init__.py` —— `get_api()`、`get_service()`、声明式表单配置的简洁示例
- `plugins/chatgpt/__init__.py` —— 经典事件驱动插件，包含配置 UI 和识别相关钩子
- `plugins/dirmonitor/__init__.py` —— 带 scheduler、文件监控和深度 MoviePilot 集成的经典插件
- `plugins.v2/chatgpt/__init__.py` —— V2 的事件 + 链式事件模式
- `plugins.v2/clashruleprovider/__init__.py` —— 本仓库最完整的 V2 架构参考
- `plugins.v2/clashruleprovider/api.py` 与 `plugins.v2/clashruleprovider/services.py` —— 路由层与编排层拆分示例

## 不要默认假设

- 不存在保证可用的根级 build、lint 或 test 命令。
- 不是所有 V2 插件都带前端源码，有些只提交构建产物。
- 大多数插件不能脱离 MoviePilot 单独运行。
- 一次插件发布通常不只是改代码，还需要同步修改根目录 `package.json` 元数据。
