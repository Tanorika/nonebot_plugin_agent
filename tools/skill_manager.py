import os
import json
import shutil

# 获取当前文件(skill_manager.py)的绝对路径，并向上推导到插件根目录
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PLUGIN_DIR = os.path.dirname(CURRENT_DIR)

# 这样生成的绝对路径永远锁定在 workspace 下
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
            return "✅ 当前可用技能列表：\n" + "\n".join(result)
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
            
            # 获取主脚本的绝对路径，并统一使用正斜杠防止 Windows 转义报错
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