<<<<<<< HEAD
import os
import json
import time
import uuid
from datetime import datetime, timedelta
from typing import List, Dict, Optional

# 存储路径
PLUGIN_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TASK_DIR = os.path.join(PLUGIN_DIR, "tasks")

class TaskManager:
    """
    任务管理器
    支持两种任务类型：
    1. 专注任务 (Executing): 长期专注的任务
    2. 延时任务 (Scheduled): 定时触发的任务
    """
    
    def __init__(self, user_id: str):
        self.user_id = user_id
        self.file_path = os.path.join(TASK_DIR, f"{user_id}_tasks.json")
        os.makedirs(TASK_DIR, exist_ok=True)
        self._init_file()
        
        # 调度器实例（延迟初始化）
        self._scheduler = None
    
    def _init_file(self):
        """初始化任务文件"""
        if not os.path.exists(self.file_path):
            self._save_data({
                "executing": "",
                "scheduled": {}
            })
        else:
            # 如果文件已存在，确保包含 scheduled 字段
            data = self._get_data()
            if "scheduled" not in data:
                data["scheduled"] = {}
                self._save_data(data)
    
    def _get_data(self) -> dict:
        try:
            with open(self.file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {"executing": "", "scheduled": {}}
    
    def _save_data(self, data: dict):
        with open(self.file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    
    @property
    def scheduler(self):
        """获取调度器实例（延迟加载）"""
        if self._scheduler is None:
            try:
                # 尝试加载 nonebot_plugin_apscheduler
                from nonebot import require
                scheduler_plugin = require("nonebot_plugin_apscheduler")
                self._scheduler = scheduler_plugin.scheduler
            except Exception as e:
                print(f"⚠️ 无法加载调度器: {e}")
                self._scheduler = None
        return self._scheduler
    
    # --- 专注任务 (Executing) ---
    def get_executing(self) -> str:
        return self._get_data().get("executing", "")
    
=======
import json
import math
import os
import uuid
from datetime import datetime, timedelta
from typing import Optional

PLUGIN_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TASK_DIR = os.path.join(PLUGIN_DIR, "tasks")


class TaskManager:
    """管理专注目标与持久化的 LLM 挂起任务。"""

    def __init__(self, user_id: str):
        self.user_id = str(user_id)
        self.file_path = os.path.join(TASK_DIR, f"{self.user_id}_tasks.json")
        os.makedirs(TASK_DIR, exist_ok=True)
        if not os.path.exists(self.file_path):
            self._save_data({"executing": "", "scheduled": {}})

    def _get_data(self) -> dict:
        try:
            with open(self.file_path, encoding="utf-8") as task_file:
                data = json.load(task_file)
            data.setdefault("scheduled", {})
            return data
        except FileNotFoundError:
            return {"executing": "", "scheduled": {}}

    def _save_data(self, data: dict):
        temp_path = self.file_path + ".tmp"
        with open(temp_path, "w", encoding="utf-8") as task_file:
            json.dump(data, task_file, ensure_ascii=False, indent=4)
        os.replace(temp_path, self.file_path)

    @classmethod
    def user_ids(cls) -> list[str]:
        if not os.path.isdir(TASK_DIR):
            return []
        return [name[:-11] for name in os.listdir(TASK_DIR) if name.endswith("_tasks.json")]

    def get_executing(self) -> str:
        return self._get_data().get("executing", "")

>>>>>>> 61bfc77 (feat: initial release of nonebot_plugin_agent (clean sanitized framework))
    def set_executing(self, text: str):
        data = self._get_data()
        data["executing"] = text
        self._save_data(data)
<<<<<<< HEAD
    
    def clear_executing(self):
        self.set_executing("")
    
    # --- 延时任务 (Scheduled) ---
    
    def schedule_delayed_task(
        self,
        message: str,
        delay_seconds: int,
        task_name: Optional[str] = None
    ) -> str:
        """
        设置延时任务
        
        Args:
            message: 要发送的消息内容
            delay_seconds: 延时秒数
            task_name: 任务名称（可选，默认自动生成）
        
        Returns:
            任务ID
        """
        if not self.scheduler:
            return "❌ 错误：调度器未初始化，请确保已安装 nonebot_plugin_apscheduler"
        
        # 生成任务ID
        task_id = task_name or f"task_{uuid.uuid4().hex[:8]}"
        
        # 计算执行时间
        run_time = datetime.now() + timedelta(seconds=delay_seconds)
        
        # 保存任务信息
        data = self._get_data()
        data["scheduled"][task_id] = {
            "message": message,
            "delay_seconds": delay_seconds,
            "scheduled_time": run_time.strftime("%Y-%m-%d %H:%M:%S"),
            "status": "pending"
        }
        self._save_data(data)
        
        try:
            # 添加定时任务
            self.scheduler.add_job(
                self._execute_scheduled_task,
                'date',
                run_date=run_time,
                args=[task_id, message],
                id=task_id,
                replace_existing=True
            )
            
            return f"✅ 成功：已设置延时任务「{task_id}」，{delay_seconds} 秒后执行"
        except Exception as e:
            # 如果添加失败，清理保存的任务信息
            data = self._get_data()
            if task_id in data["scheduled"]:
                del data["scheduled"][task_id]
            self._save_data(data)
            return f"❌ 错误：设置延时任务失败 -> {str(e)}"
    
    def _execute_scheduled_task(self, task_id: str, message: str):
        """
        执行延时任务（内部方法）
        注意：此方法在调度器线程中执行，不能使用 await
        """
        # 更新任务状态
        data = self._get_data()
        if task_id in data["scheduled"]:
            data["scheduled"][task_id]["status"] = "completed"
            data["scheduled"][task_id]["executed_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self._save_data(data)
        
        # 将消息放入全局队列，由主循环处理发送
        # 这样可以避免在调度器线程中调用异步函数
        try:
            if not hasattr(self, '_message_queue'):
                self._message_queue = []
            
            self._message_queue.append({
                'user_id': self.user_id,
                'message': message,
                'task_id': task_id,
                'timestamp': datetime.now().timestamp()
            })
            
            print(f"🕐 延时任务执行 [{task_id}]: {message}")
            print(f"📨 消息已加入发送队列（队列长度: {len(self._message_queue)}）")
        except Exception as e:
            print(f"❌ 延时任务执行失败: {e}")
    
    def get_pending_messages(self) -> list:
        """
        获取待发送的消息队列
        此方法应该在主循环中定期调用，处理消息发送
        """
        if not hasattr(self, '_message_queue'):
            return []
        
        messages = self._message_queue.copy()
        self._message_queue.clear()
        return messages
    
    def cancel_scheduled_task(self, task_id: str) -> str:
        """
        取消延时任务
        
        Args:
            task_id: 任务ID
        
        Returns:
            操作结果
        """
        if not self.scheduler:
            return "❌ 错误：调度器未初始化"
        
        # 检查任务是否存在
        data = self._get_data()
        if task_id not in data["scheduled"]:
            return f"❌ 错误：任务「{task_id}」不存在"
        
        try:
            # 移除定时任务
            job = self.scheduler.get_job(task_id)
            if job:
                self.scheduler.remove_job(task_id)
            
            # 更新任务状态
            data["scheduled"][task_id]["status"] = "cancelled"
            self._save_data(data)
            
            return f"✅ 成功：已取消延时任务「{task_id}」"
        except Exception as e:
            return f"❌ 错误：取消任务失败 -> {str(e)}"
    
    def list_scheduled_tasks(self) -> str:
        """
        列出所有延时任务
        
        Returns:
            任务列表字符串
        """
        data = self._get_data()
        scheduled_tasks = data.get("scheduled", {})
        
        if not scheduled_tasks:
            return "✅ 当前没有延时任务"
        
        result = f"📋 延时任务列表（共 {len(scheduled_tasks)} 个）：\n\n"
        
        for task_id, task_info in scheduled_tasks.items():
            status = task_info.get("status", "unknown")
            status_icon = "⏳" if status == "pending" else "✅" if status == "completed" else "❌"
            
            result += f"{status_icon} 任务ID: {task_id}\n"
            result += f"   消息: {task_info.get('message', '')}\n"
            result += f"   预定时间: {task_info.get('scheduled_time', '')}\n"
            result += f"   状态: {status}\n\n"
        
        return result
    
    def clear_scheduled_tasks(self) -> str:
        """
        清除所有延时任务
        
        Returns:
            操作结果
        """
        if not self.scheduler:
            return "❌ 错误：调度器未初始化"
        
        data = self._get_data()
        scheduled_tasks = data.get("scheduled", {})
        
        if not scheduled_tasks:
            return "✅ 当前没有延时任务"
        
        try:
            # 移除所有定时任务
            for task_id in scheduled_tasks:
                job = self.scheduler.get_job(task_id)
                if job:
                    self.scheduler.remove_job(task_id)
            
            # 清空任务列表
            data["scheduled"] = {}
            self._save_data(data)
            
            return f"✅ 成功：已清除 {len(scheduled_tasks)} 个延时任务"
        except Exception as e:
            return f"❌ 错误：清除任务失败 -> {str(e)}"

=======

    def clear_executing(self):
        self.set_executing("")

    def schedule_delayed_task(self, message: str, delay_seconds: int,
                              task_name: Optional[str] = None,
                              callback_prompt: Optional[str] = None,
                              context: str = "") -> str:
        """message 保留为旧调用的兼容参数；新调用使用 callback_prompt。"""
        prompt = callback_prompt if callback_prompt is not None else message
        if not isinstance(prompt, str) or not prompt.strip():
            return "❌ 错误：请提供非空的 callback_prompt（到期后的恢复指令）"
        try:
            delay = float(delay_seconds)
            if isinstance(delay_seconds, bool) or not math.isfinite(delay) or delay < 0 or not delay.is_integer():
                raise ValueError
            delay = int(delay)
            run_time = datetime.now() + timedelta(seconds=delay)
        except (TypeError, ValueError, OverflowError):
            return "❌ 错误：delay_seconds 必须是有效的非负整数"
        if task_name is not None and (not isinstance(task_name, str) or not task_name.strip()):
            return "❌ 错误：task_name 必须是非空字符串"
        task_id = task_name or f"task_{uuid.uuid4().hex[:8]}"
        data = self._get_data()
        if data["scheduled"].get(task_id, {}).get("status") in {"pending", "suspended", "running", "awaiting_confirmation"}:
            return f"❌ 错误：任务「{task_id}」仍在执行或挂起，请取消后再创建"
        data["scheduled"][task_id] = {
            "callback_prompt": prompt.strip(), "context": context,
            "delay_seconds": delay,
            "created_time": datetime.now().isoformat(timespec="seconds"),
            "scheduled_time": run_time.isoformat(timespec="seconds"),
            "status": "suspended",
        }
        self._save_data(data)
        return f"✅ 已挂起任务「{task_id}」，{delay} 秒后恢复并回调 LLM"

    def get_due_tasks(self) -> list[tuple[str, dict]]:
        now = datetime.now()
        due = []
        for task_id, info in self._get_data()["scheduled"].items():
            if info.get("status") not in {"pending", "suspended"}:
                continue
            try:
                is_due = datetime.fromisoformat(info["scheduled_time"]) <= now
            except (KeyError, ValueError, TypeError):
                is_due = False
            if is_due:
                due.append((task_id, info.copy()))
        return due

    def update_status(self, task_id: str, status: str, error: Optional[str] = None):
        data = self._get_data()
        info = data["scheduled"].get(task_id)
        if info is None or info.get("status") == "cancelled":
            return
        info["status"] = status
        info["updated_time"] = datetime.now().isoformat(timespec="seconds")
        if error:
            info["error"] = str(error)
        self._save_data(data)

    def recover_interrupted_tasks(self):
        data = self._get_data()
        changed = False
        for info in data["scheduled"].values():
            if info.get("status") in {"running", "awaiting_confirmation"}:
                info["status"] = "suspended"
                changed = True
        if changed:
            self._save_data(data)

    def cancel_scheduled_task(self, task_id: str) -> str:
        data = self._get_data()
        if task_id not in data["scheduled"]:
            return f"❌ 错误：任务「{task_id}」不存在"
        if data["scheduled"][task_id].get("status") in {"running", "awaiting_confirmation"}:
            return "❌ 错误：该任务已经恢复，无法取消正在执行的回调"
        data["scheduled"][task_id]["status"] = "cancelled"
        self._save_data(data)
        return f"✅ 已取消挂起任务「{task_id}」"

    def list_scheduled_tasks(self) -> str:
        tasks = self._get_data()["scheduled"]
        if not tasks:
            return "✅ 当前没有挂起任务"
        return "📋 任务列表：\n" + "\n\n".join(
            f"任务ID: {task_id}\n恢复指令: {info.get('callback_prompt') or info.get('message', '')}"
            f"\n预定时间: {info.get('scheduled_time', '')}\n状态: {info.get('status', 'unknown')}"
            + (f"\n错误: {info['error']}" if info.get("error") else "")
            for task_id, info in tasks.items()
        )

    def clear_scheduled_tasks(self) -> str:
        data = self._get_data()
        retained = {key: info for key, info in data["scheduled"].items()
                    if info.get("status") in {"running", "awaiting_confirmation"}}
        count = len(data["scheduled"]) - len(retained)
        data["scheduled"] = retained
        self._save_data(data)
        return f"✅ 已清除 {count} 个任务，保留 {len(retained)} 个已恢复的任务"
>>>>>>> 61bfc77 (feat: initial release of nonebot_plugin_agent (clean sanitized framework))
