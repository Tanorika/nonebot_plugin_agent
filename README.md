# NoneBot-Plugin-SmartAgent

这是一个基于 **NoneBot2** 框架开发的轻量级、可扩展的 AI Agent 助手插件。它不仅能通过大模型进行对话，还具备文件读写、指令执行、技能管理以及长效记忆功能。

## ✨ 功能特性

* **自主决策 (Thought-Action-Observation)**：Agent 会根据用户需求自主思考并调用相关工具。
* **文件系统操作**：支持对本地文件进行读取、写入和管理。
* **指令执行能力**：可以直接在宿主机（Windows）上执行终端命令或 Python 脚本。
* **模块化技能 (Skills)**：用户可以动态创建、修改或删除 Agent 的特定技能脚本。
* **长效记忆 (Memory)**：具备独立于对话历史的长期记忆库，重要信息永不丢失。
* **自定义表情库**：支持通过特定标签调用本地表情包，并能自动同步图片资源。

## 🚀 快速开始

### 1. 环境准备

确保你已经安装并配置好了 [NoneBot2](https://nonebot.dev/) 环境，并连接了 OneBot v11 适配器。
本插件在开发与测试阶段使用 [NapCat](https://napneko.github.io/) 作为协议端.
本项目在Windows环境下开发，建议使用Windows系统。

### 2. 安装插件

将本项目文件夹放入你的 NoneBot 插件目录中（通常为 `src/plugins`）。

### 3. 基础配置

打开 `config.py` 文件，修改以下核心参数：

```python
# config.py
class Config(BaseModel):
    url: str = "你的 API 代理或官方 URL"
    api_key: str = "Your-API-Key"  # 替换为你的有效 Key
    model: str = "DeepSeek-V3"     # 指定使用的模型名称
    preset: str = "..."            # 可选：自定义 Agent 的性格、规则或系统提示词

```

## 🖼️ 表情包管理 (Stickers)

本项目支持通过 AI 自动发送表情包。你需要对表情包进行手动“打标”以便 Agent 理解其用途。

1. 将图片放入 `stickers/` 文件夹下（支持 `.jpg`, `.png`, `.gif`）。
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


3. **注意**：`id` 建议与文件名保持一致。`desc` 是给 AI 看的，描述得越准确，AI 在对话中触发表情就越自然。


## ⚠️ 安全提示

本插件具备**执行系统命令**的能力。

* 默认开启了 `safe_commands` 白名单过滤。
* 所有涉及修改系统或执行命令的操作，Agent 都会通过 `(Y/N)` 询问用户，**请在确认指令安全后再回复 Y**。
