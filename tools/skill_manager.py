import os
import json
import shutil
import subprocess
import tempfile

# 【关键修复】获取当前文件(skill_manager.py)的绝对路径，并向上推导到插件根目录
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PLUGIN_DIR = os.path.dirname(CURRENT_DIR)

<<<<<<< HEAD
# 生成的绝对路径锁定在 nonebot_plugin_agent/workspace 下
=======
# 这样生成的绝对路径锁定在 nonebot_plugin_agent/workspace 下
>>>>>>> 61bfc77 (feat: initial release of nonebot_plugin_agent (clean sanitized framework))
WORKSPACE_DIR = os.path.join(PLUGIN_DIR, "workspace")
SKILLS_DIR = os.path.join(WORKSPACE_DIR, "skills")
SKILLS_JSON_PATH = os.path.join(WORKSPACE_DIR, "skills.json")

class SkillManager:
    @classmethod
    def _init_workspace(cls):
        """初始化工作区目录和索引文件"""
        os.makedirs(SKILLS_DIR, exist_ok=True)
        if not os.path.exists(SKILLS_JSON_PATH):
            with open(SKILLS_JSON_PATH, 'w', encoding='utf-8') as f:
                json.dump({}, f, ensure_ascii=False, indent=4)

    @classmethod
    def list_skills(cls) -> str:
        """[LIST] 获取所有可用技能的压缩摘要"""
        cls._init_workspace()
        try:
            with open(SKILLS_JSON_PATH, 'r', encoding='utf-8') as f:
                skills = json.load(f)
            if not skills:
                return "当前没有任何已保存的 Skill。"
            
            result = []
            for name, info in skills.items():
                result.append(f"- 【{name}】: {info.get('desc', '无描述')} (路径: {info.get('script_path')})")
            return "\n".join(result)
        except Exception as e:
            return f"❌ 错误：读取技能列表失败 -> {str(e)}"

    @classmethod
    def get_skill_detail(cls, skill_name: str) -> str:
        """[DETAIL] 获取技能的具体用法说明"""
        cls._init_workspace()
        usage_path = os.path.join(SKILLS_DIR, skill_name, "usage.md")
        if not os.path.exists(usage_path):
            return f"❌ 错误：未找到名为 '{skill_name}' 的技能或其 usage.md 文件。"
        
        try:
            with open(usage_path, 'r', encoding='utf-8') as f:
                return f"✅ 【{skill_name}】使用说明：\n" + f.read()
        except Exception as e:
            return f"❌ 错误：读取使用说明失败 -> {str(e)}"

    @classmethod
    def create_skill(cls, name: str, desc: str, usage: str, script: str) -> str:
        """[CREATE] 创建一个新的技能模块"""
        cls._init_workspace()
        
        # 安全检查：防止路径穿越
        name = "".join([c for c in name if c.isalnum() or c in ('_', '-')])
        if not name: return "❌ 错误：技能名称不合法。"

        skill_path = os.path.join(SKILLS_DIR, name)
        if os.path.exists(skill_path):
            return f"❌ 错误：技能 '{name}' 已存在。请使用 MODIFY 修改或更换名称。"

        try:
            os.makedirs(skill_path)
            
            # 【关键修复】获取主脚本的绝对路径，并统一使用正斜杠防止 Windows 转义报错
            main_script_path = os.path.join(skill_path, "main.py").replace("\\", "/")
            
            # 写入主脚本和说明文档
            with open(main_script_path, 'w', encoding='utf-8') as f:
                f.write(script)
            with open(os.path.join(skill_path, "usage.md"), 'w', encoding='utf-8') as f:
                f.write(usage)
            
            # 更新全局索引
            with open(SKILLS_JSON_PATH, 'r', encoding='utf-8') as f:
                skills = json.load(f)
            
            skills[name] = {
                "desc": desc,
                "script_path": main_script_path # 将绝对路径存入，告诉 AI 执行时的准确位置
            }
            
            with open(SKILLS_JSON_PATH, 'w', encoding='utf-8') as f:
                json.dump(skills, f, ensure_ascii=False, indent=4)
                
            return f"✅ 成功：技能 '{name}' 已创建。请使用命令 `python {main_script_path}` 来运行它。"
        except Exception as e:
            return f"❌ 错误：创建技能失败 -> {str(e)}"

    @classmethod
    def modify_skill(cls, name: str, script: str = None, usage: str = None, desc: str = None) -> str:
        """[MODIFY] 修改现有技能"""
        cls._init_workspace()
        skill_path = os.path.join(SKILLS_DIR, name)
        if not os.path.exists(skill_path):
            return f"❌ 错误：技能 '{name}' 不存在。"

        try:
            if script:
                with open(os.path.join(skill_path, "main.py"), 'w', encoding='utf-8') as f:
                    f.write(script)
            if usage:
                with open(os.path.join(skill_path, "usage.md"), 'w', encoding='utf-8') as f:
                    f.write(usage)
            if desc:
                with open(SKILLS_JSON_PATH, 'r', encoding='utf-8') as f:
                    skills = json.load(f)
                skills[name]["desc"] = desc
                with open(SKILLS_JSON_PATH, 'w', encoding='utf-8') as f:
                    json.dump(skills, f, ensure_ascii=False, indent=4)
                    
            return f"✅ 成功：技能 '{name}' 已更新。"
        except Exception as e:
            return f"❌ 错误：修改技能失败 -> {str(e)}"

    @classmethod
    def delete_skill(cls, name: str) -> str:
        """[DELETE] 删除技能"""
        cls._init_workspace()
        skill_path = os.path.join(SKILLS_DIR, name)
        if not os.path.exists(skill_path):
            return f"❌ 错误：技能 '{name}' 不存在。"

        try:
            shutil.rmtree(skill_path)
            
            with open(SKILLS_JSON_PATH, 'r', encoding='utf-8') as f:
                skills = json.load(f)
            
            if name in skills:
                del skills[name]
                with open(SKILLS_JSON_PATH, 'w', encoding='utf-8') as f:
                    json.dump(skills, f, ensure_ascii=False, indent=4)
                    
            return f"✅ 成功：技能 '{name}' 已被彻底删除。"
        except Exception as e:
            return f"❌ 错误：删除技能失败 -> {str(e)}"

    @classmethod
    def execute_skill(cls, skill_name: str, params: dict = None) -> str:
        """
        执行指定技能（支持参数传递）
        
        Args:
            skill_name: 技能名称
            params: 技能参数字典，会自动转换为命令行参数
                   - 简单参数（字符串、数字、布尔）直接作为命令行参数
                   - 复杂参数（列表、字典）通过临时 JSON 文件传递
        
        Returns:
            执行结果字符串，包含 stdout 和 stderr
        """
        try:
            # 读取技能索引
            if not os.path.exists(SKILLS_JSON_PATH):
                return f"❌ 错误：技能索引文件不存在。"
            
            with open(SKILLS_JSON_PATH, 'r', encoding='utf-8') as f:
                skills = json.load(f)
            
            if skill_name not in skills:
                return f"❌ 错误：技能 '{skill_name}' 不存在。"
            
            script_path = skills[skill_name].get("script_path")
            if not script_path or not os.path.exists(script_path):
                return f"❌ 错误：技能 '{skill_name}' 的脚本文件不存在。"
            
            # 构建命令行参数
            cmd = ["python", script_path]
            
            # 初始化变量
            has_complex_params = False
            params_file = None
            
            # 处理参数
            if params:
                # 将参数字典转换为命令行参数
                # 简单参数：--key value
                # 复杂参数：写入临时 JSON 文件，传递 --params /path/to/params.json
                
                # 检查是否需要创建临时参数文件（如果参数值是列表或字典等复杂类型）
                has_complex_params = any(isinstance(v, (list, dict)) for v in params.values())
                
                if has_complex_params:
                    # 创建临时参数文件
                    params_file = tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8')
                    json.dump(params, params_file, ensure_ascii=False, indent=2)
                    params_file.close()
                    
                    cmd.append("--params")
                    cmd.append(params_file.name)
                else:
                    # 简单参数，直接作为命令行参数
                    for key, value in params.items():
                        cmd.append(f"--{key}")
                        if isinstance(value, bool):
                            # 布尔值只添加标志
                            if value:
                                continue  # 已经添加了标志
                        else:
                            cmd.append(str(value))
            
            # 执行脚本
            env = os.environ.copy()
            env["PYTHONUNBUFFERED"] = "1"
            env["PYTHONIOENCODING"] = "utf-8"
            
            process = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                env=env,
                encoding="utf-8",
                errors="replace",
                timeout=60
            )
            
            # 清理临时文件
            if has_complex_params and params_file:
                try:
                    os.unlink(params_file.name)
                except:
                    pass
            
            stdout = process.stdout.strip()
            stderr = process.stderr.strip()
            
            if not stdout and not stderr:
                params_str = f" (参数: {params})" if params else ""
                return f"✅ 技能 '{skill_name}' 已执行{params_str}，但无输出。"
            
            result = f"✅ 技能 '{skill_name}' 执行结果：\n"
            if stdout: result += f"【STDOUT】\n{stdout}"
            if stderr: result += f"\n【STDERR】\n{stderr}"
            
            return result
            
        except Exception as e:
            return f"❌ 错误：执行技能 '{skill_name}' 失败 -> {str(e)}"