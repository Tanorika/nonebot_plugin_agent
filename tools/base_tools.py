import os
import subprocess

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
                    return f.read()
            except UnicodeDecodeError:
                with open(filepath, 'r', encoding='gbk') as f:
                    return f.read()
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