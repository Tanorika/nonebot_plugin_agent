#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Agent 记忆树独立可视化工作台 (Memory Tree Visualizer)
读取 memory/trees 目录下的记忆树 JSON 与 memory 原始日志，
以交互式拓扑树状图呈现记忆结构，并支持点击节点在右侧文本框查看详情。
"""

import argparse
import json
import os
import re
import socket
import sys
import threading
import urllib.parse
import webbrowser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TREES_DIR = ROOT / "memory" / "trees"
MEMORY_DIR = ROOT / "memory"


def find_free_port(preferred_port: int = 8765) -> int:
    """寻找可用端口，优先使用 preferred_port，若被占用则顺延。"""
    for port in range(preferred_port, preferred_port + 100):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(("127.0.0.1", port))
                return port
        except OSError:
            continue
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def get_available_trees():
    """扫描 memory/trees 目录下所有可用的树结构 JSON 文件。"""
    if not TREES_DIR.exists():
        return []
    files = sorted(
        TREES_DIR.glob("*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    result = []
    for f in files:
        try:
            size_kb = round(f.stat().st_size / 1024, 1)
            result.append({
                "filename": f.name,
                "path": str(f),
                "size_kb": size_kb,
                "user_id": f.stem.split(".")[0],
            })
        except OSError:
            continue
    return result


def load_tree_data(filename: str, recent_messages: int = 40):
    """读取指定树文件及其对应的原始聊天记录，构建前端渲染所需的数据拓扑结构。"""
    tree_path = TREES_DIR / filename
    if not tree_path.exists():
        return {"error": f"找不到文件：{filename}"}

    try:
        raw_tree = json.loads(tree_path.read_text(encoding="utf-8"))
    except Exception as e:
        return {"error": f"解析树文件失败：{e}"}

    nodes = raw_tree.get("nodes", {})
    frontier = raw_tree.get("frontier", [])
    fanout = raw_tree.get("fanout", 4)
    leaf_count = raw_tree.get("leaf_count", 0)
    version = raw_tree.get("version", 3)

    user_id = tree_path.stem.split(".")[0]
    history_path = MEMORY_DIR / f"{user_id}.json"
    history = []
    if history_path.exists():
        try:
            history = json.loads(history_path.read_text(encoding="utf-8"))
        except Exception:
            history = []

    # 计算反向父节点映射
    parents_map = {}
    for nid, n in nodes.items():
        for cid in n.get("children", []):
            parents_map[cid] = nid

    # 计算活跃上下文视窗节点 (Active Window Nodes)
    cutoff = max(0, leaf_count - max(1, recent_messages))
    window_nodes = set()

    def collect_window(ref):
        n = nodes.get(ref)
        if not n:
            return
        if n["start"] >= cutoff:
            return
        if n["end"] <= cutoff:
            window_nodes.add(ref)
        else:
            for child in n.get("children", []):
                collect_window(child)

    for ref in frontier:
        collect_window(ref)

    # 统计信息
    parents_count = sum(1 for n in nodes.values() if not n.get("leaf"))
    ready_count = sum(1 for n in nodes.values() if not n.get("leaf") and n.get("status") == "ready")
    pending_count = parents_count - ready_count
    max_level = max((n.get("level", 0) for n in nodes.values()), default=0)

    # 格式化所有节点数据供前端使用
    formatted_nodes = {}
    for nid, n in nodes.items():
        is_leaf = bool(n.get("leaf"))
        level = n.get("level", 0)
        start = n.get("start", 0)
        end = n.get("end", 0)
        status = "ready" if is_leaf else n.get("status", "pending")
        children = n.get("children", [])
        parent = parents_map.get(nid)

        preview = ""
        role = ""
        created_at = n.get("created_at", "")

        if is_leaf:
            h_idx = n.get("history_index")
            if h_idx is not None and 0 <= h_idx < len(history):
                h_item = history[h_idx]
                role = h_item.get("role", "")
                created_at = created_at or h_item.get("created_at", "")
                content_str = str(h_item.get("content", "")).strip()
                preview = content_str[:80].replace("\n", " ")
        else:
            summary = n.get("summary") or ""
            preview = summary[:80].replace("\n", " ") if summary else "（模型摘要待生成）"

        formatted_nodes[nid] = {
            "id": nid,
            "leaf": is_leaf,
            "level": level,
            "start": start,
            "end": end,
            "leaf_count": end - start,
            "status": status,
            "children": children,
            "parent": parent,
            "is_frontier": nid in frontier,
            "is_window": nid in window_nodes,
            "preview": preview,
            "role": role,
            "created_at": created_at,
            "model": n.get("summary_model", ""),
            "prompt_version": n.get("prompt_version"),
        }

    return {
        "filename": filename,
        "user_id": user_id,
        "version": version,
        "fanout": fanout,
        "leaf_count": leaf_count,
        "parents_count": parents_count,
        "ready_count": ready_count,
        "pending_count": pending_count,
        "max_level": max_level,
        "frontier": frontier,
        "window_nodes": list(window_nodes),
        "recent_messages": recent_messages,
        "cutoff": cutoff,
        "nodes": formatted_nodes,
    }


def get_node_detail(filename: str, node_id: str):
    """获取单个节点的完整正文详情（叶子节点读取原始消息，父节点读取完整摘要）。"""
    tree_path = TREES_DIR / filename
    if not tree_path.exists():
        return {"error": f"找不到树文件：{filename}"}

    try:
        raw_tree = json.loads(tree_path.read_text(encoding="utf-8"))
    except Exception as e:
        return {"error": f"解析树文件失败：{e}"}

    nodes = raw_tree.get("nodes", {})
    node = nodes.get(node_id)
    if not node:
        return {"error": f"未找到节点：{node_id}"}

    user_id = tree_path.stem.split(".")[0]
    history_path = MEMORY_DIR / f"{user_id}.json"
    history = []
    if history_path.exists():
        try:
            history = json.loads(history_path.read_text(encoding="utf-8"))
        except Exception:
            history = []

    is_leaf = bool(node.get("leaf"))
    full_content = ""
    role = ""
    created_at = node.get("created_at", "")
    history_index = node.get("history_index")

    if is_leaf:
        if history_index is not None and 0 <= history_index < len(history):
            h_item = history[history_index]
            role = h_item.get("role", "未知")
            created_at = created_at or h_item.get("created_at", "未记录")
            full_content = str(h_item.get("content", ""))
        else:
            full_content = "（未在本地对话历史中找到该叶子消息）"
    else:
        full_content = node.get("summary") or "（模型摘要待生成，子节点与原文完好保留）"

    return {
        "id": node_id,
        "leaf": is_leaf,
        "level": node.get("level", 0),
        "start": node.get("start", 0),
        "end": node.get("end", 0),
        "leaf_count": node.get("end", 0) - node.get("start", 0),
        "status": "leaf" if is_leaf else node.get("status", "pending"),
        "role": role,
        "created_at": created_at,
        "history_index": history_index,
        "digest": node.get("digest", ""),
        "summary_model": node.get("summary_model", ""),
        "prompt_version": node.get("prompt_version"),
        "children": node.get("children", []),
        "content": full_content,
    }


HTML_PAGE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Agent 记忆树可视化工作台</title>
<style>
  :root {
    --bg-main: #0b0f19;
    --bg-panel: #111827;
    --bg-card: #1f2937;
    --border: #374151;
    --border-hover: #4b5563;
    --text-primary: #f3f4f6;
    --text-secondary: #9ca3af;
    --text-muted: #6b7280;
    --accent: #3b82f6;
    --accent-glow: rgba(59, 130, 246, 0.4);
    --window-highlight: #f97316;
    --window-glow: rgba(249, 115, 22, 0.45);
  }

  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "PingFang SC", "Microsoft YaHei", sans-serif;
    background: var(--bg-main);
    color: var(--text-primary);
    height: 100vh;
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }

  /* 顶部工具栏 */
  header {
    height: 60px;
    background: var(--bg-panel);
    border-bottom: 1px solid var(--border);
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0 16px;
    z-index: 10;
  }
  .header-left {
    display: flex;
    align-items: center;
    gap: 12px;
  }
  .app-title {
    font-size: 16px;
    font-weight: 700;
    display: flex;
    align-items: center;
    gap: 8px;
    color: #60a5fa;
  }
  .tree-select {
    background: var(--bg-card);
    border: 1px solid var(--border);
    color: var(--text-primary);
    padding: 6px 12px;
    border-radius: 6px;
    font-size: 13px;
    outline: none;
    cursor: pointer;
  }
  .header-stats {
    display: flex;
    gap: 8px;
  }
  .stat-chip {
    background: var(--bg-card);
    border: 1px solid var(--border);
    padding: 4px 10px;
    border-radius: 6px;
    font-size: 12px;
    color: var(--text-secondary);
  }
  .stat-chip b {
    color: var(--text-primary);
    margin-left: 4px;
  }

  .header-controls {
    display: flex;
    align-items: center;
    gap: 8px;
  }
  .btn {
    background: var(--bg-card);
    border: 1px solid var(--border);
    color: var(--text-primary);
    padding: 6px 12px;
    border-radius: 6px;
    font-size: 12px;
    cursor: pointer;
    display: inline-flex;
    align-items: center;
    gap: 6px;
    transition: all 0.15s ease;
  }
  .btn:hover {
    background: #374151;
    border-color: #6b7280;
  }
  .btn.active {
    background: #1e3a8a;
    border-color: #3b82f6;
    color: #93c5fd;
  }
  .btn-highlight.active {
    background: rgba(249, 115, 22, 0.2);
    border-color: var(--window-highlight);
    color: #fdba74;
  }

  /* 搜索框 */
  .search-box {
    position: relative;
    display: flex;
    align-items: center;
  }
  .search-input {
    background: var(--bg-card);
    border: 1px solid var(--border);
    color: var(--text-primary);
    padding: 6px 12px 6px 28px;
    border-radius: 6px;
    font-size: 12px;
    width: 170px;
    transition: width 0.2s ease;
  }
  .search-input:focus {
    width: 230px;
    border-color: var(--accent);
    outline: none;
  }
  .search-icon {
    position: absolute;
    left: 8px;
    font-size: 12px;
    color: var(--text-muted);
  }

  /* 主体区域 */
  main {
    flex: 1;
    display: flex;
    position: relative;
    overflow: hidden;
  }

  /* 画布区域 */
  #canvas-container {
    flex: 1;
    position: relative;
    background: radial-gradient(#1f2937 1px, transparent 1px);
    background-size: 24px 24px;
    background-color: var(--bg-main);
    overflow: hidden;
  }
  svg#tree-svg {
    width: 100%;
    height: 100%;
    cursor: grab;
  }
  svg#tree-svg:active {
    cursor: grabbing;
  }

  /* 浮动操作条 */
  .canvas-floating-bar {
    position: absolute;
    bottom: 20px;
    left: 20px;
    background: rgba(17, 24, 39, 0.85);
    backdrop-filter: blur(8px);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 6px 10px;
    display: flex;
    align-items: center;
    gap: 8px;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.5);
    z-index: 5;
  }
  .level-legend {
    display: flex;
    gap: 6px;
    align-items: center;
    font-size: 11px;
    color: var(--text-muted);
    margin-right: 8px;
    padding-right: 8px;
    border-right: 1px solid var(--border);
  }
  .legend-dot {
    width: 10px;
    height: 10px;
    border-radius: 50%;
    display: inline-block;
  }

  /* 可拖拽分割条 */
  #resizer {
    width: 6px;
    background: var(--border);
    cursor: col-resize;
    transition: background 0.2s;
    z-index: 5;
  }
  #resizer:hover, #resizer.resizing {
    background: var(--accent);
  }

  /* 右侧详情面板 */
  #inspector {
    width: 480px;
    min-width: 320px;
    max-width: 800px;
    background: var(--bg-panel);
    border-left: 1px solid var(--border);
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }
  .inspector-header {
    padding: 16px;
    border-bottom: 1px solid var(--border);
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
  }
  .node-title-group {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }
  .node-id-badge {
    font-size: 20px;
    font-weight: 700;
    color: var(--text-primary);
    display: flex;
    align-items: center;
    gap: 8px;
  }
  .level-tag {
    font-size: 11px;
    font-weight: 600;
    padding: 2px 8px;
    border-radius: 4px;
    text-transform: uppercase;
  }
  .status-tag {
    font-size: 11px;
    padding: 2px 8px;
    border-radius: 4px;
    background: #374151;
    color: #e5e7eb;
  }
  .status-tag.ready {
    background: rgba(16, 185, 129, 0.2);
    color: #34d399;
    border: 1px solid rgba(16, 185, 129, 0.4);
  }
  .status-tag.pending {
    background: rgba(245, 158, 11, 0.2);
    color: #fbbf24;
    border: 1px solid rgba(245, 158, 11, 0.4);
  }
  .window-badge {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    background: rgba(249, 115, 22, 0.2);
    color: #fb923c;
    border: 1px solid rgba(249, 115, 22, 0.4);
    font-size: 11px;
    padding: 2px 8px;
    border-radius: 4px;
    font-weight: 600;
  }

  .inspector-body {
    flex: 1;
    display: flex;
    flex-direction: column;
    padding: 16px;
    gap: 16px;
    overflow-y: auto;
  }
  .meta-grid {
    display: grid;
    grid-template-columns: 80px 1fr;
    gap: 8px 12px;
    font-size: 13px;
    background: var(--bg-card);
    padding: 12px;
    border-radius: 8px;
    border: 1px solid var(--border);
  }
  .meta-label {
    color: var(--text-muted);
  }
  .meta-val {
    color: var(--text-primary);
    word-break: break-all;
  }
  .meta-val a {
    color: #60a5fa;
    text-decoration: none;
    cursor: pointer;
  }
  .meta-val a:hover {
    text-decoration: underline;
  }
  .child-pills {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
  }
  .child-pill {
    background: #374151;
    color: #d1d5db;
    padding: 2px 8px;
    border-radius: 4px;
    font-size: 11px;
    cursor: pointer;
    transition: background 0.15s;
  }
  .child-pill:hover {
    background: #4b5563;
    color: #fff;
  }

  .text-box-wrapper {
    flex: 1;
    display: flex;
    flex-direction: column;
    gap: 8px;
    min-height: 250px;
  }
  .text-box-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-size: 13px;
    font-weight: 600;
    color: var(--text-secondary);
  }
  .content-textarea {
    flex: 1;
    width: 100%;
    min-height: 240px;
    background: #090d16;
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 14px;
    color: #e2e8f0;
    font-family: Consolas, "Fira Code", Monaco, Menlo, "PingFang SC", monospace;
    font-size: 13px;
    line-height: 1.6;
    resize: none;
    outline: none;
    white-space: pre-wrap;
    word-break: break-word;
  }
  .content-textarea:focus {
    border-color: var(--accent);
  }

  /* SVG 节点与连线样式 */
  .link-line {
    fill: none;
    stroke: #374151;
    stroke-width: 2px;
    transition: stroke 0.2s, stroke-width 0.2s;
  }
  .link-line.active {
    stroke: #60a5fa;
    stroke-width: 2.5px;
  }
  .link-line.window-link {
    stroke: rgba(249, 115, 22, 0.5);
    stroke-width: 2.5px;
  }

  .tree-node {
    cursor: pointer;
  }
  .node-bg {
    fill: #1e293b;
    stroke: #334155;
    stroke-width: 1.5px;
    rx: 8;
    transition: all 0.2s;
  }
  .tree-node:hover .node-bg {
    stroke: #60a5fa;
    filter: drop-shadow(0 0 6px var(--accent-glow));
  }
  .tree-node.selected .node-bg {
    stroke: #38bdf8;
    stroke-width: 2.5px;
    filter: drop-shadow(0 0 10px rgba(56, 189, 248, 0.6));
  }
  .tree-node.window-active .node-bg {
    stroke: var(--window-highlight);
    stroke-width: 2.5px;
    filter: drop-shadow(0 0 8px var(--window-glow));
  }
  .tree-node.frontier-node .node-bg {
    stroke-dasharray: 4 2;
  }

  .node-title {
    font-size: 13px;
    font-weight: 700;
    fill: #f8fafc;
  }
  .node-level-badge {
    font-size: 10px;
    font-weight: 700;
    text-anchor: middle;
  }
  .node-sub {
    font-size: 11px;
    fill: #94a3b8;
  }
  .node-preview {
    font-size: 10.5px;
    fill: #64748b;
  }
  .toggle-btn {
    cursor: pointer;
    transition: transform 0.15s;
  }
  .toggle-btn:hover {
    transform: scale(1.15);
  }

  /* 提示吐司 */
  #toast {
    position: fixed;
    bottom: 24px;
    right: 24px;
    background: #10b981;
    color: #fff;
    padding: 8px 16px;
    border-radius: 6px;
    font-size: 13px;
    font-weight: 600;
    box-shadow: 0 4px 12px rgba(0,0,0,0.4);
    opacity: 0;
    transform: translateY(10px);
    transition: all 0.2s ease;
    pointer-events: none;
    z-index: 100;
  }
  #toast.show {
    opacity: 1;
    transform: translateY(0);
  }
</style>
</head>
<body>

<header>
  <div class="header-left">
    <div class="app-title">🌲 Agent 记忆树可视化</div>
    <select id="treeSelect" class="tree-select" onchange="onTreeChange()"></select>
    <div class="header-stats">
      <span class="stat-chip">叶子消息: <b id="statLeaves">-</b></span>
      <span class="stat-chip">父级摘要: <b id="statParents">-</b></span>
      <span class="stat-chip">最高层数: <b id="statLevels">-</b></span>
      <span class="stat-chip">当前视窗: <b id="statWindow">-</b></span>
    </div>
  </div>

  <div class="header-controls">
    <div class="search-box">
      <span class="search-icon">🔍</span>
      <input type="text" id="searchInput" class="search-input" placeholder="搜索 ID/序号/关键词..." onkeydown="handleSearchKey(event)">
    </div>
    <button class="btn" onclick="toggleOrientation()" id="btnOrientation">↔ 水平树</button>
    <button class="btn btn-highlight active" onclick="toggleWindowHighlight()" id="btnWindowHighlight">🎯 当前 Prompt 视窗</button>
    <button class="btn" onclick="collapseAll()">仅看前沿</button>
    <button class="btn" onclick="expandToLevel(3)">展开至 L3</button>
    <button class="btn" onclick="expandToLevel(1)">展开至 L1</button>
    <button class="btn" onclick="expandAll()">全部展开</button>
    <button class="btn" onclick="refreshTree()">🔄 刷新</button>
  </div>
</header>

<main>
  <div id="canvas-container">
    <svg id="tree-svg">
      <g id="viewport">
        <g id="links-group"></g>
        <g id="nodes-group"></g>
      </g>
    </svg>

    <div class="canvas-floating-bar">
      <div class="level-legend">
        <span>层级：</span>
        <span class="legend-dot" style="background: #ec4899"></span> L5
        <span class="legend-dot" style="background: #8b5cf6"></span> L4
        <span class="legend-dot" style="background: #3b82f6"></span> L3
        <span class="legend-dot" style="background: #06b6d4"></span> L2
        <span class="legend-dot" style="background: #10b981"></span> L1
        <span class="legend-dot" style="background: #64748b"></span> L0 (叶子)
      </div>
      <button class="btn" onclick="zoomIn()">➕ 放大</button>
      <button class="btn" onclick="zoomOut()">➖ 缩小</button>
      <button class="btn" onclick="fitView()">🎯 适应画布</button>
    </div>
  </div>

  <div id="resizer"></div>

  <div id="inspector">
    <div class="inspector-header">
      <div class="node-title-group">
        <div class="node-id-badge">
          <span id="detailId">请选择节点</span>
          <span id="detailLevelTag" class="level-tag"></span>
          <span id="detailStatusTag" class="status-tag"></span>
        </div>
        <div id="detailWindowBadge" style="display: none;" class="window-badge">🎯 当前 Prompt 视窗节点 (覆盖此范围)</div>
      </div>
      <button class="btn" onclick="copyContent()">📋 复制正文</button>
    </div>

    <div class="inspector-body">
      <div class="meta-grid">
        <span class="meta-label">覆盖范围</span>
        <span class="meta-val" id="detailRange">-</span>

        <span class="meta-label">记录时间</span>
        <span class="meta-val" id="detailTime">-</span>

        <span class="meta-label" id="labelModel">归纳模型</span>
        <span class="meta-val" id="detailModel">-</span>

        <span class="meta-label">父级节点</span>
        <span class="meta-val" id="detailParent">-</span>

        <span class="meta-label">子级节点</span>
        <div class="meta-val child-pills" id="detailChildren">-</div>
      </div>

      <div class="text-box-wrapper">
        <div class="text-box-header">
          <span id="detailContentTitle">节点完整内容 / 摘要</span>
          <span id="detailCharCount" style="color: var(--text-muted); font-size: 11px;">0 字符</span>
        </div>
        <textarea id="detailContent" class="content-textarea" readonly placeholder="点击左侧拓扑图中的任意节点，在此处显示该节点完整内容..."></textarea>
      </div>
    </div>
  </div>
</main>

<div id="toast">已复制到剪贴板！</div>

<script>
let currentTreeData = null;
let selectedNodeId = null;
let collapsedNodes = new Set();
let isHorizontal = true;
let showWindowHighlight = true;

// 变换状态（平移与缩放）
let transform = { x: 80, y: 80, scale: 0.85 };
let isDragging = false;
let startPoint = { x: 0, y: 0 };

const LEVEL_COLORS = {
  5: "#ec4899",
  4: "#8b5cf6",
  3: "#3b82f6",
  2: "#06b6d4",
  1: "#10b981",
  0: "#64748b"
};

const svg = document.getElementById("tree-svg");
const viewport = document.getElementById("viewport");
const linksGroup = document.getElementById("links-group");
const nodesGroup = document.getElementById("nodes-group");

// 初始化页面
window.addEventListener("DOMContentLoaded", async () => {
  initResizer();
  initPanZoom();
  await loadTreeList();
});

// 分割条拖拽
function initResizer() {
  const resizer = document.getElementById("resizer");
  const inspector = document.getElementById("inspector");
  let startX = 0, startWidth = 0;

  resizer.addEventListener("mousedown", (e) => {
    startX = e.clientX;
    startWidth = inspector.offsetWidth;
    resizer.classList.add("resizing");
    document.body.style.userSelect = "none";
    window.addEventListener("mousemove", onMouseMove);
    window.addEventListener("mouseup", onMouseUp);
  });

  function onMouseMove(e) {
    const newWidth = Math.max(300, Math.min(800, startWidth - (e.clientX - startX)));
    inspector.style.width = newWidth + "px";
  }

  function onMouseUp() {
    resizer.classList.remove("resizing");
    document.body.style.userSelect = "";
    window.removeEventListener("mousemove", onMouseMove);
    window.removeEventListener("mouseup", onMouseUp);
  }
}

// 平移与缩放
function initPanZoom() {
  svg.addEventListener("mousedown", (e) => {
    if (e.target.closest(".tree-node")) return;
    isDragging = true;
    startPoint = { x: e.clientX - transform.x, y: e.clientY - transform.y };
  });

  window.addEventListener("mousemove", (e) => {
    if (!isDragging) return;
    transform.x = e.clientX - startPoint.x;
    transform.y = e.clientY - startPoint.y;
    applyTransform();
  });

  window.addEventListener("mouseup", () => isDragging = false);

  svg.addEventListener("wheel", (e) => {
    e.preventDefault();
    const zoomFactor = e.deltaY < 0 ? 1.15 : 0.87;
    const rect = svg.getBoundingClientRect();
    const mouseX = e.clientX - rect.left;
    const mouseY = e.clientY - rect.top;

    transform.x = mouseX - (mouseX - transform.x) * zoomFactor;
    transform.y = mouseY - (mouseY - transform.y) * zoomFactor;
    transform.scale = Math.min(Math.max(transform.scale * zoomFactor, 0.08), 3.0);
    applyTransform();
  }, { passive: false });
}

function applyTransform() {
  viewport.setAttribute("transform", `translate(${transform.x}, ${transform.y}) scale(${transform.scale})`);
}

function zoomIn() {
  transform.scale = Math.min(transform.scale * 1.25, 3.0);
  applyTransform();
}
function zoomOut() {
  transform.scale = Math.max(transform.scale * 0.8, 0.08);
  applyTransform();
}

// 适应画布
function fitView() {
  const bbox = viewport.getBBox();
  if (bbox.width === 0 || bbox.height === 0) return;
  const svgRect = svg.getBoundingClientRect();
  const padding = 60;
  const scaleX = (svgRect.width - padding * 2) / bbox.width;
  const scaleY = (svgRect.height - padding * 2) / bbox.height;
  transform.scale = Math.min(Math.max(Math.min(scaleX, scaleY), 0.15), 1.2);
  transform.x = (svgRect.width - bbox.width * transform.scale) / 2 - bbox.x * transform.scale;
  transform.y = (svgRect.height - bbox.height * transform.scale) / 2 - bbox.y * transform.scale;
  applyTransform();
}

// 读取树文件列表
async function loadTreeList() {
  try {
    const res = await fetch("/api/trees");
    const trees = await res.json();
    const select = document.getElementById("treeSelect");
    select.innerHTML = "";
    if (!trees || trees.length === 0) {
      select.innerHTML = "<option>未找到树文件</option>";
      return;
    }
    trees.forEach(t => {
      const opt = document.createElement("option");
      opt.value = t.filename;
      opt.textContent = `${t.filename} (${t.size_kb} KB)`;
      select.appendChild(opt);
    });
    await loadTree(trees[0].filename);
  } catch (err) {
    console.error("加载文件列表失败", err);
  }
}

async function onTreeChange() {
  const filename = document.getElementById("treeSelect").value;
  await loadTree(filename);
}

async function refreshTree() {
  const filename = document.getElementById("treeSelect").value;
  await loadTree(filename);
  showToast("树结构已更新！");
}

// 加载指定树数据
async function loadTree(filename) {
  try {
    const res = await fetch(`/api/tree?file=${encodeURIComponent(filename)}&recent=40`);
    const data = await res.json();
    if (data.error) {
      alert(data.error);
      return;
    }
    currentTreeData = data;

    // 默认折叠：保留 L3 及以上展开，L2/L1/L0 默认折叠以保持界面清爽
    collapsedNodes.clear();
    for (const [nid, node] of Object.entries(data.nodes)) {
      if (!node.leaf && node.level < 3) {
        collapsedNodes.add(nid);
      }
    }

    // 更新统计栏
    document.getElementById("statLeaves").textContent = data.leaf_count;
    document.getElementById("statParents").textContent = data.parents_count;
    document.getElementById("statLevels").textContent = `L${data.max_level} (${data.max_level + 1}层)`;
    document.getElementById("statWindow").textContent = `${data.window_nodes.length} 个节点`;

    renderGraph();
    fitView();

    // 默认选中第一个前沿根节点
    if (data.frontier && data.frontier.length > 0) {
      selectNode(data.frontier[0]);
    }
  } catch (err) {
    console.error("加载树失败", err);
  }
}

// 布局计算与渲染
function renderGraph() {
  if (!currentTreeData) return;
  const nodes = currentTreeData.nodes;
  const frontier = currentTreeData.frontier;

  // 虚拟根节点，挂接所有前沿根节点
  const virtualRoot = {
    id: "__ROOT__",
    isVirtual: true,
    children: frontier
  };

  const nodeWidth = isHorizontal ? 220 : 170;
  const nodeHeight = isHorizontal ? 68 : 74;
  const levelGap = isHorizontal ? 300 : 130;
  const siblingGap = isHorizontal ? 18 : 22;

  let currentCoord = 0;
  const layoutNodes = new Map();

  function postOrder(nodeId) {
    const node = nodeId === "__ROOT__" ? virtualRoot : nodes[nodeId];
    if (!node) return;

    const isCollapsed = collapsedNodes.has(nodeId);
    const visibleChildren = (!isCollapsed && node.children) ? node.children : [];

    if (visibleChildren.length === 0) {
      layoutNodes.set(nodeId, { id: nodeId, coord: currentCoord });
      currentCoord += (isHorizontal ? nodeHeight : nodeWidth) + siblingGap;
      return;
    }

    let minCoord = Infinity, maxCoord = -Infinity;
    for (const cid of visibleChildren) {
      postOrder(cid);
      const childLayout = layoutNodes.get(cid);
      if (childLayout) {
        minCoord = Math.min(minCoord, childLayout.coord);
        maxCoord = Math.max(maxCoord, childLayout.coord);
      }
    }
    const centerCoord = (minCoord + maxCoord) / 2;
    layoutNodes.set(nodeId, { id: nodeId, coord: centerCoord });
  }

  postOrder("__ROOT__");

  // 分配深度坐标与生成图元
  const renderedNodes = [];
  const renderedLinks = [];

  function preOrder(nodeId, depth = 0) {
    const node = nodeId === "__ROOT__" ? virtualRoot : nodes[nodeId];
    if (!node) return;

    const layout = layoutNodes.get(nodeId);
    if (!layout) return;

    let x, y;
    if (isHorizontal) {
      x = (depth - 1) * levelGap;
      y = layout.coord;
    } else {
      x = layout.coord;
      y = (depth - 1) * levelGap;
    }

    if (nodeId !== "__ROOT__") {
      renderedNodes.push({ id: nodeId, node, x, y });
    }

    const isCollapsed = collapsedNodes.has(nodeId);
    if (!isCollapsed && node.children) {
      for (const cid of node.children) {
        const childLayout = layoutNodes.get(cid);
        if (childLayout) {
          let cx, cy;
          if (isHorizontal) {
            cx = depth * levelGap;
            cy = childLayout.coord;
          } else {
            cx = childLayout.coord;
            cy = depth * levelGap;
          }

          if (nodeId !== "__ROOT__") {
            renderedLinks.push({
              sourceId: nodeId,
              targetId: cid,
              sx: isHorizontal ? x + nodeWidth : x + nodeWidth / 2,
              sy: isHorizontal ? y + nodeHeight / 2 : y + nodeHeight,
              tx: isHorizontal ? cx : cx + nodeWidth / 2,
              ty: isHorizontal ? cy + nodeHeight / 2 : cy
            });
          }
          preOrder(cid, depth + 1);
        }
      }
    }
  }

  preOrder("__ROOT__", 0);

  // 绘制连线
  linksGroup.innerHTML = "";
  for (const link of renderedLinks) {
    const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
    const { sx, sy, tx, ty } = link;
    let d = "";
    if (isHorizontal) {
      const mx = (sx + tx) / 2;
      d = `M ${sx} ${sy} C ${mx} ${sy}, ${mx} ${ty}, ${tx} ${ty}`;
    } else {
      const my = (sy + ty) / 2;
      d = `M ${sx} ${sy} C ${sx} ${my}, ${tx} ${my}, ${tx} ${ty}`;
    }
    path.setAttribute("d", d);
    path.setAttribute("class", "link-line");

    const targetNode = nodes[link.targetId];
    if (showWindowHighlight && targetNode && targetNode.is_window) {
      path.classList.add("window-link");
    }
    linksGroup.appendChild(path);
  }

  // 绘制节点卡片
  nodesGroup.innerHTML = "";
  for (const item of renderedNodes) {
    const { id, node, x, y } = item;
    const g = document.createElementNS("http://www.w3.org/2000/svg", "g");
    g.setAttribute("class", "tree-node");
    g.setAttribute("id", `node-${id}`);
    g.setAttribute("transform", `translate(${x}, ${y})`);
    g.onclick = (e) => {
      e.stopPropagation();
      selectNode(id);
    };

    if (id === selectedNodeId) g.classList.add("selected");
    if (showWindowHighlight && node.is_window) g.classList.add("window-active");
    if (node.is_frontier) g.classList.add("frontier-node");

    const levelColor = LEVEL_COLORS[node.level] || "#64748b";

    // 背景卡片
    const rect = document.createElementNS("http://www.w3.org/2000/svg", "rect");
    rect.setAttribute("class", "node-bg");
    rect.setAttribute("width", nodeWidth);
    rect.setAttribute("height", nodeHeight);
    g.appendChild(rect);

    // 层级圆点/指示标
    const levelBadge = document.createElementNS("http://www.w3.org/2000/svg", "circle");
    levelBadge.setAttribute("cx", 16);
    levelBadge.setAttribute("cy", 20);
    levelBadge.setAttribute("r", 6);
    levelBadge.setAttribute("fill", levelColor);
    g.appendChild(levelBadge);

    // 节点 ID 与层级
    const title = document.createElementNS("http://www.w3.org/2000/svg", "text");
    title.setAttribute("class", "node-title");
    title.setAttribute("x", 28);
    title.setAttribute("y", 24);
    title.textContent = `${id}  (L${node.level})`;
    g.appendChild(title);

    // 覆盖范围
    const sub = document.createElementNS("http://www.w3.org/2000/svg", "text");
    sub.setAttribute("class", "node-sub");
    sub.setAttribute("x", 12);
    sub.setAttribute("y", 42);
    if (node.leaf) {
      sub.textContent = `消息 #${node.start + 1} (${node.role || 'leaf'})`;
    } else {
      sub.textContent = `消息 #${node.start + 1}-${node.end} (${node.leaf_count}条)`;
    }
    g.appendChild(sub);

    // 摘要缩略
    const preview = document.createElementNS("http://www.w3.org/2000/svg", "text");
    preview.setAttribute("class", "node-preview");
    preview.setAttribute("x", 12);
    preview.setAttribute("y", 58);
    let pText = node.preview || "";
    if (pText.length > (isHorizontal ? 18 : 14)) {
      pText = pText.slice(0, isHorizontal ? 18 : 14) + "...";
    }
    preview.textContent = pText;
    g.appendChild(preview);

    // 折叠/展开按键
    if (node.children && node.children.length > 0) {
      const isCollapsed = collapsedNodes.has(id);
      const toggleG = document.createElementNS("http://www.w3.org/2000/svg", "g");
      toggleG.setAttribute("class", "toggle-btn");
      const bx = isHorizontal ? nodeWidth - 22 : nodeWidth / 2 - 10;
      const by = isHorizontal ? nodeHeight / 2 - 10 : nodeHeight - 12;
      toggleG.setAttribute("transform", `translate(${bx}, ${by})`);

      const tRect = document.createElementNS("http://www.w3.org/2000/svg", "rect");
      tRect.setAttribute("width", 20);
      tRect.setAttribute("height", 20);
      tRect.setAttribute("rx", 10);
      tRect.setAttribute("fill", isCollapsed ? "#3b82f6" : "#374151");
      toggleG.appendChild(tRect);

      const tText = document.createElementNS("http://www.w3.org/2000/svg", "text");
      tText.setAttribute("x", 10);
      tText.setAttribute("y", 14);
      tText.setAttribute("text-anchor", "middle");
      tText.setAttribute("fill", "#fff");
      tText.setAttribute("font-size", "12");
      tText.setAttribute("font-weight", "bold");
      tText.textContent = isCollapsed ? "+" : "-";
      toggleG.appendChild(tText);

      toggleG.onclick = (e) => {
        e.stopPropagation();
        toggleCollapse(id);
      };
      g.appendChild(toggleG);
    }

    nodesGroup.appendChild(g);
  }
}

// 折叠/展开切换
function toggleCollapse(nodeId) {
  if (collapsedNodes.has(nodeId)) {
    collapsedNodes.delete(nodeId);
  } else {
    collapsedNodes.add(nodeId);
  }
  renderGraph();
}

// 快捷展开/折叠
function collapseAll() {
  if (!currentTreeData) return;
  for (const [nid, node] of Object.entries(currentTreeData.nodes)) {
    if (!node.leaf && node.children && node.children.length > 0) {
      collapsedNodes.add(nid);
    }
  }
  renderGraph();
  fitView();
}

function expandToLevel(targetLevel) {
  if (!currentTreeData) return;
  collapsedNodes.clear();
  for (const [nid, node] of Object.entries(currentTreeData.nodes)) {
    if (!node.leaf && node.level < targetLevel) {
      collapsedNodes.add(nid);
    }
  }
  renderGraph();
  fitView();
}

function expandAll() {
  collapsedNodes.clear();
  renderGraph();
  fitView();
}

function toggleOrientation() {
  isHorizontal = !isHorizontal;
  document.getElementById("btnOrientation").textContent = isHorizontal ? "↔ 水平树" : "↕ 垂直树";
  renderGraph();
  fitView();
}

function toggleWindowHighlight() {
  showWindowHighlight = !showWindowHighlight;
  const btn = document.getElementById("btnWindowHighlight");
  if (showWindowHighlight) {
    btn.classList.add("active");
  } else {
    btn.classList.remove("active");
  }
  renderGraph();
}

// 选中节点并在右侧文本框加载详情
async function selectNode(nodeId) {
  selectedNodeId = nodeId;

  // 更新左侧选定高亮
  document.querySelectorAll(".tree-node.selected").forEach(el => el.classList.remove("selected"));
  const currentEl = document.getElementById(`node-${nodeId}`);
  if (currentEl) currentEl.classList.add("selected");

  const filename = document.getElementById("treeSelect").value;
  try {
    const res = await fetch(`/api/node_detail?file=${encodeURIComponent(filename)}&id=${encodeURIComponent(nodeId)}`);
    const detail = await res.json();
    if (detail.error) return;

    // 更新右侧标题与徽章
    document.getElementById("detailId").textContent = detail.id;
    const levelTag = document.getElementById("detailLevelTag");
    levelTag.textContent = `L${detail.level} ${detail.leaf ? '叶子消息' : '归纳摘要'}`;
    levelTag.style.background = LEVEL_COLORS[detail.level] || "#64748b";
    levelTag.style.color = "#fff";

    const statusTag = document.getElementById("detailStatusTag");
    if (detail.leaf) {
      statusTag.textContent = `角色: ${detail.role || 'user'}`;
      statusTag.className = "status-tag ready";
    } else {
      statusTag.textContent = detail.status === "ready" ? "✅ 摘要已就绪" : "⏳ 摘要生成中";
      statusTag.className = `status-tag ${detail.status}`;
    }

    const isWindow = currentTreeData && currentTreeData.window_nodes.includes(detail.id);
    document.getElementById("detailWindowBadge").style.display = isWindow ? "inline-flex" : "none";

    // 更新元数据
    document.getElementById("detailRange").textContent =
      `第 ${detail.start + 1} 至 ${detail.end} 条消息（涵盖 ${detail.leaf_count} 条）`;

    document.getElementById("detailTime").textContent = detail.created_at || "未记录时间";

    if (detail.leaf) {
      document.getElementById("labelModel").textContent = "历史日志索引";
      document.getElementById("detailModel").textContent = `#${detail.history_index}`;
    } else {
      document.getElementById("labelModel").textContent = "归纳模型";
      document.getElementById("detailModel").textContent =
        `${detail.summary_model || '主模型'} (v${detail.prompt_version || 1})`;
    }

    // 父级节点链接
    const nodeObj = currentTreeData ? currentTreeData.nodes[nodeId] : null;
    const parentId = nodeObj ? nodeObj.parent : null;
    const parentContainer = document.getElementById("detailParent");
    if (parentId) {
      parentContainer.innerHTML = `<a onclick="locateAndSelect('${parentId}')">${parentId}</a>`;
    } else {
      parentContainer.textContent = "无（前沿顶层根节点）";
    }

    // 子级节点列表
    const childrenContainer = document.getElementById("detailChildren");
    childrenContainer.innerHTML = "";
    if (detail.children && detail.children.length > 0) {
      detail.children.forEach(cid => {
        const span = document.createElement("span");
        span.className = "child-pill";
        span.textContent = cid;
        span.onclick = () => locateAndSelect(cid);
        childrenContainer.appendChild(span);
      });
    } else {
      childrenContainer.textContent = "无（底层原始叶子）";
    }

    // 更新文本框正文
    let contentDisplay = detail.content || "";
    if (detail.leaf) {
      contentDisplay = `【角色】：${detail.role}\n【时间】：${detail.created_at}\n【索引】：#${detail.history_index}\n` +
                       `--------------------------------------------------\n${contentDisplay}`;
    }
    const textarea = document.getElementById("detailContent");
    textarea.value = contentDisplay;
    document.getElementById("detailCharCount").textContent = `${contentDisplay.length} 字符`;

  } catch (err) {
    console.error("加载节点详情失败", err);
  }
}

// 在画布中展开、定位并选中指定节点
function locateAndSelect(nodeId) {
  if (!currentTreeData || !currentTreeData.nodes[nodeId]) return;

  // 展开所有祖先节点以确保该节点可见
  let curr = currentTreeData.nodes[nodeId].parent;
  let changed = false;
  while (curr) {
    if (collapsedNodes.has(curr)) {
      collapsedNodes.delete(curr);
      changed = true;
    }
    curr = currentTreeData.nodes[curr] ? currentTreeData.nodes[curr].parent : null;
  }
  if (changed) {
    renderGraph();
  }

  selectNode(nodeId);

  // 移动视角聚焦该节点
  setTimeout(() => {
    const el = document.getElementById(`node-${nodeId}`);
    if (el) {
      const transformAttr = el.getAttribute("transform");
      const match = /translate\(([^,]+),\s*([^)]+)\)/.exec(transformAttr);
      if (match) {
        const nx = parseFloat(match[1]);
        const ny = parseFloat(match[2]);
        const svgRect = svg.getBoundingClientRect();
        transform.x = svgRect.width / 2 - (nx + 100) * transform.scale;
        transform.y = svgRect.height / 2 - (ny + 30) * transform.scale;
        applyTransform();
      }
    }
  }, 50);
}

// 搜索处理
function handleSearchKey(event) {
  if (event.key === "Enter") {
    const query = event.target.value.trim().toUpperCase();
    if (!query || !currentTreeData) return;

    // 1. 精确匹配节点 ID (如 N1450)
    if (currentTreeData.nodes[query]) {
      locateAndSelect(query);
      return;
    }

    // 2. 匹配消息序号 (如 #500 或 500)
    const numMatch = query.replace("#", "");
    if (/^\d+$/.test(numMatch)) {
      const idx = parseInt(numMatch, 10) - 1;
      for (const [nid, node] of Object.entries(currentTreeData.nodes)) {
        if (node.leaf && node.start === idx) {
          locateAndSelect(nid);
          return;
        }
      }
    }

    // 3. 关键词匹配节点内容
    for (const [nid, node] of Object.entries(currentTreeData.nodes)) {
      if (node.preview && node.preview.toUpperCase().includes(query)) {
        locateAndSelect(nid);
        return;
      }
    }

    showToast("未找到匹配的节点");
  }
}

// 复制文本框内容
function copyContent() {
  const text = document.getElementById("detailContent").value;
  if (!text) return;
  navigator.clipboard.writeText(text).then(() => {
    showToast("正文已复制到剪贴板！");
  }).catch(() => {
    const textarea = document.getElementById("detailContent");
    textarea.select();
    document.execCommand("copy");
    showToast("正文已复制！");
  });
}

function showToast(msg) {
  const toast = document.getElementById("toast");
  toast.textContent = msg;
  toast.classList.add("show");
  setTimeout(() => toast.classList.remove("show"), 2000);
}
</script>

</body>
</html>
"""


class TreeServerHandler(SimpleHTTPRequestHandler):
    """处理前端 API 请求与静态资源服务的 HTTP 请求处理器。"""

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        if path in ("", "/"):
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(HTML_PAGE.encode("utf-8"))
            return

        if path == "/api/trees":
            trees = get_available_trees()
            self.send_json(trees)
            return

        if path == "/api/tree":
            filename = query.get("file", [""])[0]
            if not filename:
                trees = get_available_trees()
                filename = trees[0]["filename"] if trees else ""
            recent = int(query.get("recent", [40])[0])
            data = load_tree_data(filename, recent_messages=recent)
            self.send_json(data)
            return

        if path == "/api/node_detail":
            filename = query.get("file", [""])[0]
            node_id = query.get("id", [""])[0]
            detail = get_node_detail(filename, node_id)
            self.send_json(detail)
            return

        self.send_error(404, "Not Found")

    def send_json(self, data):
        payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, format, *args):
        # 静默控制台访问日志，保持输出整洁
        return


def start_server(port: int):
    """在后台线程中启动轻量级 HTTP 服务。"""
    server = ThreadingHTTPServer(("127.0.0.1", port), TreeServerHandler)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    return server


def main():
    parser = argparse.ArgumentParser(description="Agent 记忆树独立可视化工作台")
    parser.add_argument("--port", type=int, default=8765, help="本地服务端口 (默认 8765)")
    parser.add_argument("--browser", action="store_true", help="强制使用系统默认浏览器打开，不使用 PySide6 窗口")
    parser.add_argument("--no-open", action="store_true", help="仅启动服务，不自动弹出任何窗口")
    args = parser.parse_args()

    port = find_free_port(args.port)
    server = start_server(port)
    url = f"http://127.0.0.1:{port}"

    print("=" * 65)
    print(f"🌲 Agent 记忆树可视化工作台已启动！")
    print(f"🔗 本地访问地址: {url}")
    print(f"📁 树文件监控目录: {TREES_DIR}")
    print("=" * 65)

    if args.no_open:
        try:
            while True:
                threading.Event().wait(1)
        except KeyboardInterrupt:
            print("\n服务已停止。")
        return

    # 优先尝试使用 PySide6 原生桌面窗口
    use_qt = not args.browser
    if use_qt:
        try:
            from PySide6.QtCore import QUrl
            from PySide6.QtGui import QIcon
            from PySide6.QtWebEngineWidgets import QWebEngineView
            from PySide6.QtWidgets import QApplication, QMainWindow

            app = QApplication.instance() or QApplication(sys.argv)
            window = QMainWindow()
            window.setWindowTitle("Agent 记忆树可视化工作台 (Memory Tree Visualizer)")
            window.resize(1440, 900)

            view = QWebEngineView(window)
            view.setUrl(QUrl(url))
            window.setCentralWidget(view)
            window.show()

            print("💻 已启动 PySide6 原生桌面应用窗口...")
            sys.exit(app.exec())
        except Exception as e:
            print(f"ℹ️ 未启动 Qt 桌面窗口 ({e})，正在切换至系统默认浏览器打开...")
            use_qt = False

    # 若未使用 Qt 或启动失败，自动使用默认浏览器打开
    if not use_qt:
        webbrowser.open(url)
        print("🌐 已在系统默认浏览器中打开页面。按 Ctrl+C 可停止服务。")
        try:
            while True:
                threading.Event().wait(1)
        except KeyboardInterrupt:
            print("\n服务已停止。")


if __name__ == "__main__":
    main()
