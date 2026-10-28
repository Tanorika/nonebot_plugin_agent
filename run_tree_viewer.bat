@echo off
chcp 65001 > nul
echo 正在启动 Agent 记忆树可视化工作台...
cd /d "%~dp0"
python tools/visualize_memory_tree.py %*
pause
