import os
import subprocess
import asyncio
class BaseTools:
    @staticmethod
    def read_file(filepath: str) -> str:
        """[READ] 读取指定文件的内容"""
        if not os.path.exists(filepath):
            return f"❌ 错误：文件 {filepath} 不存在。"
        try:
            # 尝试用 utf-8 读取，失败则退避到 gbk (Windows常见)
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
<<<<<<< HEAD
                    return f.read()
            except UnicodeDecodeError:
                with open(filepath, 'r', encoding='gbk') as f:
                    return f.read()
=======
                    content = f.read()
                    return "\n".join(f"{i}: {line}" for i, line in enumerate(content.splitlines(), 1))
            except UnicodeDecodeError:
                with open(filepath, 'r', encoding='gbk') as f:
                    content = f.read()
                    return "\n".join(f"{i}: {line}" for i, line in enumerate(content.splitlines(), 1))
>>>>>>> 61bfc77 (feat: initial release of nonebot_plugin_agent (clean sanitized framework))
        except Exception as e:
            return f"❌ 错误：读取文件失败 -> {str(e)}"

    @staticmethod
    def write_file(filepath: str, content: str) -> str:
        """[WRITE] 将内容写入指定文件（如果目录不存在会自动创建）"""
        try:
            # 确保父目录存在
            os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
            
            # Windows 下 bat/cmd 优先使用 GBK，其余 UTF-8
            encoding = "gbk" if filepath.lower().endswith(('.bat', '.cmd')) else "utf-8"
            with open(filepath, 'w', encoding=encoding) as f:
                f.write(content)
            return f"✅ 成功：已将内容写入 {filepath}"
        except Exception as e:
            return f"❌ 错误：写入文件失败 -> {str(e)}"

    @staticmethod
    def modify_file(
        filepath: str, 
        line_number: int = None, 
        start_line: int = None, 
        end_line: int = None, 
        new_content: str = None, 
        search_text: str = None, 
        replace_text: str = None,
        mode: str = "auto",
        context_lines: int = 2,
        instruction: str = None
    ) -> str:
<<<<<<< HEAD
        """[MODIFY] 修改文件内容（使用 LLM 智能修改，最稳健）
        
        参数：
        - filepath: 要修改的文件路径
        - instruction: 修改指令（自然语言描述）- **推荐使用此参数**
        - 其他参数（line_number, start_line, end_line, search_text 等）已废弃，仅为兼容保留
        
        使用方式（推荐）：
        - instruction="将 old_function 改名为 new_function"
        - instruction="在 process_data 函数中添加日志输出"
        - instruction="将配置文件中的 timeout 从 30 改为 60"
        - instruction="优化 calculate 函数的性能"
        
        特点：
        - ✅ 使用 DeepSeek V3.2 API 智能修改
        - ✅ 支持任意类型的文件（代码、配置、文本等）
        - ✅ 自动保持原有格式和缩进
        - ✅ 不会出现行号偏移问题
        - ✅ 支持复杂的文件修改
        - ✅ 详细的修改前后对比
        
        注意：此方法底层调用 llm_modify.py 脚本
        """
        # 如果提供了 instruction，直接使用 LLM 修改
        if instruction:
            return BaseTools.llm_modify(filepath, instruction)
=======
        """[MODIFY] 修改文件内容（精确结构化行号/全文替换修改）
        
        参数：
        - filepath: 要修改的文件路径
        - line_number: 单行替换行号 (1-based)
        - start_line, end_line: 多行替换起止行号 (1-based)
        - new_content: 替换后的新内容
        - search_text, replace_text: 唯一文本精确搜索与替换
        """
        # Structured edits are deterministic; natural-language delegation is disabled.
        if instruction and not any((line_number, start_line, search_text)):
            return "Error: use line_number, start_line/end_line, or search_text; instruction delegation is disabled."
>>>>>>> 61bfc77 (feat: initial release of nonebot_plugin_agent (clean sanitized framework))
        
        # 否则，尝试从其他参数构造 instruction（兼容旧版）
        if line_number:
            instruction = f"修改第 {line_number} 行的内容为：{new_content}"
        elif start_line and end_line:
            instruction = f"替换第 {start_line} 行到第 {end_line-1} 行的内容，新的内容是：{new_content}"
        elif search_text:
            instruction = f"搜索文本「{search_text}」并替换为「{new_content or replace_text}」"
        else:
            return "❌ 错误：缺少参数。请提供 instruction 参数，或者使用其他兼容参数。"
        
<<<<<<< HEAD
        return BaseTools.llm_modify(filepath, instruction)
=======
        return BaseTools._apply_structured_edit(filepath, line_number, start_line, end_line, new_content, search_text, replace_text)

    @staticmethod
    def _apply_structured_edit(filepath, line_number, start_line, end_line, new_content, search_text, replace_text):
        if not os.path.isfile(filepath):
            return f"Error: file does not exist: {filepath}"
        try:
            with open(filepath, "r", encoding="utf-8", newline="") as f:
                content = f.read()
            if search_text is not None:
                replacement = replace_text if replace_text is not None else new_content
                if replacement is None or content.count(search_text) != 1:
                    return "Error: search_text must match exactly once and provide replacement."
                updated = content.replace(search_text, replacement, 1)
            else:
                if line_number is not None:
                    start_line = end_line = int(line_number)
                if start_line is None or end_line is None or new_content is None:
                    return "Error: provide line_number/new_content or start_line/end_line/new_content."
                lines = content.splitlines(keepends=True)
                if start_line < 1 or end_line < start_line or end_line > len(lines):
                    return f"Error: invalid line range; file has {len(lines)} lines."
                ending = "\r\n" if "\r\n" in content else "\n"
                replacement = new_content if new_content.endswith(("\n", "\r")) else new_content + ending
                updated = "".join(lines[:start_line - 1] + [replacement] + lines[end_line:])
            if updated == content:
                return "No change: replacement equals original content."
            with open(filepath, "w", encoding="utf-8", newline="") as f:
                f.write(updated)
            return f"Success: modified {filepath}"
        except Exception as e:
            return f"Error: modification failed -> {e}"
>>>>>>> 61bfc77 (feat: initial release of nonebot_plugin_agent (clean sanitized framework))

    @staticmethod
    def execute_command(command: str) -> str:
        """[EXEC] 执行终端命令并返回回显"""
        try:
            # 【关键修复】设置环境变量，强制 Python 不缓存输出 (PYTHONUNBUFFERED=1)
            # 并且强制指定 UTF-8 编码，防止 Windows 默认 GBK 导致的乱码
            env = os.environ.copy()
            env["PYTHONUNBUFFERED"] = "1"
            env["PYTHONIOENCODING"] = "utf-8"

            process = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                env=env,
                encoding="utf-8", # 显式指定读取回显的编码
                errors="replace",  # 遇到无法解码的字符（如GBK残余）进行替换而非崩溃
                timeout=60
            )
            
            stdout = process.stdout.strip()
            stderr = process.stderr.strip()
            
            # 如果 AI 又忘了写调用逻辑或 print
            if not stdout and not stderr:
                return "⚠️ 成功：命令已执行，但没有任何输出（STDOUT/STDERR 均为空）。\n提示：如果执行的是 Python 脚本，请检查是否包含 if __name__ == '__main__': main() 且有 print 语句。"
            
            result = ""
            if stdout: result += f"【STDOUT】\n{stdout}"
            if stderr: result += f"\n【STDERR】\n{stderr}"
            return result
        except Exception as e:
            return f"❌ 错误：命令执行失败 -> {str(e)}"
    
    @staticmethod
    def llm_modify(filepath: str, instruction: str) -> str:
        """内部方法：调用 llm_modify.py 脚本进行文件修改
        
        注意：这是内部方法，应该通过 modify_file 调用
        """
        try:
            # 获取 llm_modify.py 的绝对路径
            current_dir = os.path.dirname(os.path.abspath(__file__))
            llm_modify_script = os.path.join(current_dir, "llm_modify.py")
            
            if not os.path.exists(llm_modify_script):
                return f"❌ 错误：llm_modify.py 脚本不存在（路径：{llm_modify_script}）"
            
            # 构造命令
            # 注意：instruction 可能包含空格，需要正确转义
            command = f'python "{llm_modify_script}" "{filepath}" "{instruction}"'
            
            # 执行命令
            env = os.environ.copy()
            env["PYTHONUNBUFFERED"] = "1"
            env["PYTHONIOENCODING"] = "utf-8"
            
            process = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                env=env,
                encoding="utf-8",
                errors="replace",
                timeout=60
            )
            
            stdout = process.stdout.strip()
            stderr = process.stderr.strip()
            
            result = ""
            if stdout: result += f"{stdout}"
            if stderr: result += f"\n{stderr}"
            
            return result
            
        except Exception as e:
            import traceback
            return f"❌ 错误：LLM 修改失败 -> {str(e)}\n详细堆栈：{traceback.format_exc()}"
