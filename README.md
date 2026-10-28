<<<<<<< HEAD
# NoneBot-Plugin-Agent

这是一个基于 NoneBot2 框架开发的轻量级、可扩展的 AI Agent 助手插件。它不仅能通过大模型进行对话，还具备文件读写、指令执行、技能管理以及长效记忆功能。

## 功能特性

- **自主决策 (Thought-Action-Observation)**：Agent 会根据用户需求自主思考并调用相关工具。
- **文件系统操作**：支持对本地文件进行读取、写入和管理。
- **指令执行能力**：可以直接在宿主机（Windows）上执行终端命令或 Python 脚本。
- **模块化技能 (Skills)**：用户可以动态创建、修改或删除 Agent 的特定技能脚本。
- **长效记忆 (Memory)**：具备独立于对话历史的长期记忆库，重要信息永不丢失。
- **多媒体支持**：支持通过特定标签发送图片、语音、视频、文件，以及自定义表情包。

## 快速开始

### 1. 环境准备

确保你已经安装并配置好了 NoneBot2 环境，并连接了 OneBot v11 适配器。本插件在开发与测试阶段使用 NapCat 作为协议端。

本项目在 Windows 环境下开发，建议使用 Windows 系统。

### 2. 安装插件

将本项目文件夹放入你的 NoneBot 插件目录中（通常为 `src/plugins`）。

### 3. 基础配置

打开 `config.py` 文件，修改以下核心参数：

```python
class Config(BaseModel):
    # API 配置
    api_key: str = "YOUR-API-KEY"  # 替换为你的有效 Key
    base_url: str = "https://api.openai.com/v1"  # API 地址
    model: str = "gpt-4o-mini"  # 指定使用的模型名称
    # ...
```

## 核心能力

### Base 能力（底层能力）

- `base_read`：读取文件
- `base_write`：写入文件
- `base_modify`：使用 LLM 智能修改文件
- `base_exec`：执行终端命令

### Skill 能力（模块化技能管理）

- `skill_detail`：读取技能用法
- `skill_exec`：执行技能
- `skill_create`：创建新技能
- `skill_modify`：修改技能
- `skill_delete`：删除技能

### 记忆能力

- `mem_rag`：检索相关记忆
- `mem_save`：存入长期记忆
- `mem_delete`：删除记忆

### 任务调度能力

- `task_set`：设置专注任务
- `task_finish`：标记任务完成
- `task_schedule`：设置延时任务
- `task_cancel`：取消延时任务
- `task_list`：列出延时任务
- `task_clear`：清除延时任务

## 表情包管理 (Stickers)

本项目支持通过 AI 自动发送表情包。你需要对表情包进行手动"打标"以便 Agent 理解其用途。

1. 将图片放入 `stickers/` 文件夹下（支持 .jpg, .png, .gif）。
2. 编辑 `stickers/stickers.json` 文件：

```json
{
  "stickers": [
    {
      "id": "1",
      "file": "1.jpg",
      "desc": "赞同 点赞"
    },
    {
      "id": "2",
      "file": "2.png",
      "desc": "惊讶、不可思议"
    }
  ]
}
```

注意：`id` 建议与文件名保持一致。`desc` 是给 AI 看的，描述得越准确，AI 在对话中触发表情就越自然。

## 安全提示

本插件具备执行系统命令的能力。

- 默认开启了 `safe_commands` 白名单过滤。
- 所有涉及修改系统或执行命令的操作，Agent 都会通过 (Y/N) 询问用户，请在确认指令安全后再回复 Y。

## 许可证

MIT License
=======
# NoneBot Plugin Agent

<div align="center">

基于 NoneBot2 的全自主通用智能体框架，集成多层混合记忆树、长任务延时调度、动态技能扩展与双轨权限机制。

</div>

---

## 🌟 核心特性

- 🧠 **多层混合记忆系统 (Hybrid Memory System)**
  - **短期窗口**：多轮会话实时保留与连续消息批处理聚合。
  - **两阶段长效检索 (`mem_rag`)**：纯本地关键词与字词 Bigram 高速匹配，首阶段返回摘要，按需自动扩展上下文窗口。
  - **分层记忆树 (Memory Tree)**：基于模型自动分叉归纳的会话历史树，支持旧历史 O(log n) 预算压缩与 `mem_expand` 逐层展开。
  - **独立事实库 (`mem_save`)**：独立持久化记录用户个人偏好与关键约定。
- ⏱️ **任务规划与延时唤醒 (Task & Scheduling)**
  - **专注目标锁定 (`task_set`)**：面对多步复杂任务时锚定核心目标，防止多轮思考跑题。
  - **后台挂起与定时恢复 (`task_schedule`)**：支持分钟/小时级延时唤醒，异步工作进程定时无缝唤醒 Agent 继续执行后续链路。
- 🛠️ **稳健工具链与权限机制 (Dual-track Tooling)**
  - **Base 底层能力**：跨编码文本文件安全读写（`base_read`, `base_write`）、结构化精确行修改（`base_modify`）与终端指令执行（`base_exec`）。
  - **静默/授权双轨安全设计**：安全读取与常规操作静默执行，危险写操作或未授权指令自动向用户发起 `(Y/N)` 交互确认。
  - **终端命令白名单**：内置 Windows CMD 与 PowerShell 常用安全诊断命令。
- 🧩 **动态技能扩展框架 (Dynamic Skills)**
  - 提供 `SkillManager` 模块化接口，Agent 可在运行态通过 `skill_create` / `skill_modify` 自主编写与运行 Python 技能。
- 🔍 **联网检索与正文抓取 (Web Search & Fetch)**
  - 集成 DeepSeek 官方搜索与网页内容结构化 Markdown 转换能力。
- 💬 **拟人化多媒体交互 (Multimedia Messaging)**
  - **连续消息合并**：独立缓冲聚合层，合并用户短时间内的连发文本与多张图片。
  - **自主分段输出**：支持 `[SEND]` 标签像真人一样分段发送多条消息，避免大段长文刷屏。
  - **富媒体输出**：支持本地表情包 `[STICKER:ID]`、图片 `[IMG:path]`、语音 `[VOICE:path]`、视频 `[VIDEO:path]` 与文件 `[FILE:path]`。

---

## 📁 目录结构

```text
nonebot_plugin_agent/
├── __init__.py               # 插件主入口、消息监听与事件路由
├── config.py                 # 插件全局配置模型与默认提示词
├── run_tree_viewer.bat       # 记忆树独立可视化工作台启动脚本
├── core/                     # Agent 核心逻辑
│   ├── agent_loop.py         # 核心动作循环与动作分发器
│   ├── deepseek_search.py    # 联网搜索与正文抓取客户端
│   ├── embedding_client.py   # 向量嵌入客户端 (可选组件)
│   ├── llm_api.py            # LLM API 统一封装 (支持超时自动扩容)
│   ├── llm_client.py         # 提示词拼装与会话上下文管理
│   ├── memory_manager.py     # 统一记忆管理器
│   ├── memory_summarizer.py  # 记忆树节点模型摘要器
│   ├── memory_time.py        # 结构化时间展示与解析
│   ├── memory_tree.py        # 记忆树分叉算法与序列化
│   ├── message_batcher.py    # 多消息聚合缓冲队列
│   ├── Similarity.py         # 本地文本相似度与关键词检索
│   └── tag_parser.py         # JSON 结构化动作解析器
├── docs/                     # 架构文档
│   └── memory_tree.md        # 记忆树算法与设计规范
├── memory/                   # 用户对话历史与记忆树存储 (默认被 git 忽略)
│   ├── long_term/            # 长期事实记忆文件
│   └── trees/                # 记忆树索引 JSON
├── stickers/                 # 自定义表情包库 (可选)
│   └── stickers.json         # 表情包索引
├── tasks/                    # 延时调度任务数据存储 (默认被 git 忽略)
├── temp/                     # 运行时临时图片缓存目录
├── tools/                    # 辅助与管理工具
│   ├── base_tools.py         # 文件读写与命令执行工具
│   ├── build_memory_tree.py  # 离线批量构建记忆树脚本
│   ├── skill_manager.py      # 动态技能管理模块
│   ├── sticker_manager.py    # 表情包同步管理模块
│   ├── task_manager.py       # 任务目标与延时队列管理器
│   └── visualize_memory_tree.py # 记忆树独立可视化工作台
├── utils/
│   └── message_sender.py     # 多媒体分段发送适配层
└── workspace/                # Agent 运行时工作区
    ├── skills.json           # 动态技能注册表
    └── skills/               # 自定义技能目录
```

---

## ⚙️ 配置说明

在 NoneBot 项目的 `.env` 或 `.env.prod` 中添加以下配置项：

| 配置项 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| `API_KEY` | string | `""` | **必填**，OpenAI 兼容协议的 API 密钥 (如 DeepSeek API Key) |
| `BASE_URL` | string | `"https://api.deepseek.com"` | API 服务端点 |
| `MODEL` | string | `"deepseek-chat"` | 主对话大模型名称 |
| `TEMPERATURE` | float | `0.7` | 模型采样温度 |
| `MAX_HISTORY` | int | `40` | 记忆树关闭时的最近历史消息条数 |
| `MEMORY_TREE_ENABLED` | bool | `true` | 是否启用多层模型记忆树 |
| `MEMORY_TREE_MAX_CHARS` | int | `6000` | 旧记忆树摘要注入上下文的字符预算 |
| `MEMORY_TREE_RECENT_MESSAGES` | int | `40` | 最近保留原文的非系统消息条数 |
| `MEMORY_TREE_FANOUT` | int | `4` | 记忆树叉数 (每层几个节点合成一个父摘要) |
| `MEMORY_TREE_SUMMARY_CHARS` | int | `700` | 每个摘要节点的字符上限 |
| `MEMORY_TREE_MODEL` | string | `""` | 摘要模型 (留空则复用主模型) |
| `MEMORY_TREE_API_KEY` | string | `""` | 摘要 API Key (留空则复用主凭证) |
| `DEEPSEEK_SEARCH_API_KEY` | string | `""` | 专用搜索 API Key (留空则复用主凭证) |
| `SKILL_SAFE_MODE` | int | `0` | 技能安全模式 (`0`: 黑名单模式, `1`: 白名单模式) |

---

## 📦 动作列表 (Agent Actions)

Agent 每轮决策输出规范的 JSON 结构：`{"reply": "...", "action": "...", "params": {...}}`。

### 1. 记忆检索与存储
- `mem_rag`: 关键词检索历史记录，支持两阶段展开前后文。
- `mem_expand`: 展开记忆树节点，查看下层摘要或原始消息。
- `mem_save`: 永久保存关键事实与用户偏好。
- `mem_delete`: 删除指定序号的长期记忆。

### 2. 任务调度
- `task_set`: 锁定当前专注执行的任务目标。
- `task_finish`: 宣告任务完成，清除专注状态。
- `task_schedule`: 注册定时延时恢复任务（挂起当前执行链路并在指定秒数后自动唤醒）。
- `task_cancel`: 取消指定的挂起任务。
- `task_list`: 查看当前所有挂起延时任务。

### 3. 基础系统与文件
- `base_read`: 读取指定路径文件。
- `base_write`: 写入文件（覆盖模式）。
- `base_modify`: 精确替换或按行号修改文件。
- `base_exec`: 执行终端命令（安全命令静默执行，高危命令需用户 Y/N 确认）。

### 4. 技能系统 (Skills)
- `skill_exec`: 执行指定技能脚本。
- `skill_detail`: 读取技能的 `usage.md` 说明。
- `skill_create`: 创建新的 Python 技能。
- `skill_modify`: 修改已有技能。
- `skill_delete`: 删除技能。

---

## 🌲 记忆树可视化工作台

项目内置独立的可视化工作台，用于直观查看记忆树的分叉、覆盖时间跨度、各层归纳摘要及原始对话节点。

### 启动工作台
- **Windows 用户**：双击运行 `run_tree_viewer.bat`。
- **命令行启动**：
  ```bash
  python tools/visualize_memory_tree.py --user-id <用户QQ号>
  ```
- **离线回填构建**：
  ```bash
  python tools/build_memory_tree.py --user-id <用户QQ号>
  ```

---

## 🧪 运行测试

在插件根目录下运行单元测试套件：

```bash
python -m unittest discover -s tests -p "test_*.py"
```

---

## 📄 开源许可证

本项目采用 [MIT License](LICENSE) 开源。
>>>>>>> 61bfc77 (feat: initial release of nonebot_plugin_agent (clean sanitized framework))
