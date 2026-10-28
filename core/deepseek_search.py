"""
DeepSeek 官方网页搜索与抓取模块 (Search & Fetch)
参考官方文档: https://api-docs.deepseek.com/zh-cn/guides/search
"""
import os
import json
import requests
from typing import Dict, Any, Optional, List
try:
    from nonebot.log import logger
except ImportError:
    import logging
    logger = logging.getLogger("DeepSeekSearch")


class DeepSeekSearchClient:
    """DeepSeek 官方搜索与抓取 API 客户端"""

    DEFAULT_BASE_URL = "https://api.deepseek.com"

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: int = 30,
    ):
        # 优先使用传入的 key，其次读取环境变量，最后尝试从 NoneBot 插件配置中获取
        self.api_key = api_key or os.environ.get("DEEPSEEK_API_KEY")
        self.base_url = (base_url or os.environ.get("DEEPSEEK_BASE_URL") or self.DEFAULT_BASE_URL).rstrip("/")
        self.timeout = timeout

        if not self.api_key:
            self.api_key = self._resolve_api_key_from_config()

    def _resolve_api_key_from_config(self) -> str:
        """从插件配置、环境变量或配置文件中安全解析 API Key 与 Base URL"""
        # 1. 尝试从 NoneBot 全局插件配置读取 (运行于 NoneBot 环境中)
        try:
            from ..config import Config
            from nonebot import get_plugin_config
            plugin_config = get_plugin_config(Config)
            key = getattr(plugin_config, "deepseek_search_api_key", "") or plugin_config.api_key
            if getattr(plugin_config, "deepseek_search_base_url", ""):
                self.base_url = plugin_config.deepseek_search_base_url.rstrip("/")
            elif plugin_config.base_url:
                self.base_url = plugin_config.base_url.rstrip("/")
            if key:
                return key
        except Exception:
            pass

        # 2. 降级：从 config.py 文件文本中直接提取，无须依赖完整 NoneBot 运行时环境
        try:
            import re
            from pathlib import Path
            plugin_dir = Path(__file__).resolve().parent.parent
            config_file = plugin_dir / "config.py"
            if config_file.exists():
                text = config_file.read_text(encoding="utf-8", errors="replace")
                
                # 检查专用 search key，如无则使用主 api_key
                m_search_key = re.search(r'deepseek_search_api_key\s*:\s*str\s*=\s*["\']([^"\']+)["\']', text)
                m_key = re.search(r'api_key\s*:\s*str\s*=\s*["\']([^"\']+)["\']', text)
                m_search_url = re.search(r'deepseek_search_base_url\s*:\s*str\s*=\s*["\']([^"\']+)["\']', text)
                m_url = re.search(r'base_url\s*:\s*str\s*=\s*["\']([^"\']+)["\']', text)

                if m_search_url and m_search_url.group(1):
                    self.base_url = m_search_url.group(1).rstrip("/")
                elif m_url and m_url.group(1):
                    self.base_url = m_url.group(1).rstrip("/")

                if m_search_key and m_search_key.group(1):
                    return m_search_key.group(1)
                if m_key and m_key.group(1):
                    return m_key.group(1)
        except Exception as e:
            logger.debug(f"[DeepSeek Search] 解析 config.py 失败: {e}")

        # 3. 尝试从父级工作区的 .env 文件中查找
        try:
            from pathlib import Path
            cur = Path(__file__).resolve().parent
            for _ in range(5):
                cur = cur.parent
                for env_name in [".env.prod", ".env.dev", ".env"]:
                    env_file = cur / env_name
                    if env_file.exists():
                        for line in env_file.read_text(encoding="utf-8", errors="replace").splitlines():
                            line = line.strip()
                            if line.startswith("#") or "=" not in line:
                                continue
                            k, v = line.split("=", 1)
                            k, v = k.strip().upper(), v.strip().strip("'\"")
                            if k in ("DEEPSEEK_API_KEY", "AGENT_API_KEY", "API_KEY") and v:
                                return v
        except Exception:
            pass

        return ""

    @property
    def headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def search(
        self,
        query: str,
        count: int = 5,
        ori_question: Optional[str] = None,
        need_content: bool = False,
        localization: str = "",
    ) -> Dict[str, Any]:
        """
        发起 DeepSeek 官方搜索请求 (POST /v1/tools/search)

        参数:
            query: 搜索词 (1~128 字符，支持 site:, -site:, -, lang:, after:, before:, 引号短语等)
            count: 返回条数 (1~50, 默认 5)
            ori_question: 触发搜索的用户原始问题 (1~128 字符，辅助理解意图)
            need_content: 是否在结果中返回网页正文 (默认 False)
            localization: 本地化搜索 IP 地址
        """
        if not self.api_key:
            return {"error": "未配置 DeepSeek API Key，无法使用官方网页搜索功能。"}

        query_clean = (query or "").strip()
        if not query_clean:
            return {"error": "搜索关键词 (query) 不能为空。"}

        # 截断与合法化
        if len(query_clean) > 128:
            logger.warning(f"[DeepSeek Search] query 长度超过 128 字符，将被截断: {query_clean}")
            query_clean = query_clean[:128]

        count = max(1, min(int(count), 50))

        payload: Dict[str, Any] = {
            "query": query_clean,
            "count": count,
            "need_content": bool(need_content),
        }

        if ori_question:
            payload["ori_question"] = str(ori_question).strip()[:128]
        if localization:
            payload["localization"] = str(localization).strip()

        endpoint = f"{self.base_url}/v1/tools/search"

        try:
            logger.info(f"[DeepSeek Search] 正在请求搜索接口: {endpoint} | query: {query_clean} | count: {count}")
            response = requests.post(
                endpoint,
                headers=self.headers,
                json=payload,
                timeout=self.timeout,
            )

            if response.status_code == 200:
                data = response.json()
                return data

            error_msg = self._handle_error_response(response.status_code, response.text, "Search")
            return {"error": error_msg, "status_code": response.status_code}

        except requests.exceptions.Timeout:
            return {"error": f"搜索请求超时（超过 {self.timeout} 秒），请稍后重试。"}
        except requests.exceptions.RequestException as e:
            return {"error": f"搜索网络请求异常: {str(e)}"}
        except Exception as e:
            return {"error": f"搜索发生意外错误: {str(e)}"}

    def fetch(self, url: str) -> Dict[str, Any]:
        """
        发起 DeepSeek 官方网页抓取请求 (POST /v1/tools/fetch)

        参数:
            url: 目标网页链接 (HTTP/HTTPS, 长度 <= 8192)
        """
        if not self.api_key:
            return {"error": "未配置 DeepSeek API Key，无法使用官方网页抓取功能。"}

        url_clean = (url or "").strip()
        if not url_clean:
            return {"error": "目标网页 URL 不能为空。"}

        if not (url_clean.startswith("http://") or url_clean.startswith("https://")):
            return {"error": "网页 URL 必须以 http:// 或 https:// 开头。"}

        if len(url_clean) > 8192:
            return {"error": "网页 URL 长度超过 8192 字符限制。"}

        endpoint = f"{self.base_url}/v1/tools/fetch"
        payload = {"url": url_clean}

        try:
            logger.info(f"[DeepSeek Fetch] 正在抓取网页: {endpoint} | url: {url_clean}")
            response = requests.post(
                endpoint,
                headers=self.headers,
                json=payload,
                timeout=self.timeout,
            )

            if response.status_code == 200:
                return response.json()

            error_msg = self._handle_error_response(response.status_code, response.text, "Fetch")
            return {"error": error_msg, "status_code": response.status_code}

        except requests.exceptions.Timeout:
            return {"error": f"抓取网页超时（超过 {self.timeout} 秒），请稍后重试。"}
        except requests.exceptions.RequestException as e:
            return {"error": f"抓取网络请求异常: {str(e)}"}
        except Exception as e:
            return {"error": f"抓取发生意外错误: {str(e)}"}

    def search_and_format(
        self,
        query: str,
        count: int = 5,
        ori_question: Optional[str] = None,
        need_content: bool = False,
        localization: str = "",
        max_chars: int = 4000,
    ) -> str:
        """执行搜索并将结果排版为适合 AI 模型理解的文本"""
        res = self.search(
            query=query,
            count=count,
            ori_question=ori_question,
            need_content=need_content,
            localization=localization,
        )

        if "error" in res:
            return f"❌ 搜索失败：{res['error']}"

        results = res.get("results", [])
        if not results:
            return f"🔍 未检索到关于「{query}」的相关网页结果。"

        lines = [f"🔍 DeepSeek 官方搜索结果（共 {len(results)} 条，关键词: {query}）：\n"]

        for idx, item in enumerate(results, 1):
            title = item.get("title", "无标题").strip()
            url = item.get("url", "")
            summary = item.get("summary") or item.get("snippet") or "无摘要"
            rerank_score = item.get("rerank_score")
            authority = item.get("authority")
            date = item.get("date")
            site_name = item.get("site_name")

            score_info = []
            if rerank_score is not None:
                # 官方规范：>= 1.5 属于优质结果
                quality = "优质" if rerank_score >= 1.5 else "一般"
                score_info.append(f"相关性评分: {rerank_score:.2f} ({quality})")
            if authority is not None and authority >= 0:
                auth_desc = "极权威" if authority >= 3 else f"等级 {authority}"
                score_info.append(f"权威度: {auth_desc}")
            if date:
                score_info.append(f"发布时间: {date[:10]}")
            if site_name:
                score_info.append(f"来源: {site_name}")

            meta_line = f" [{', '.join(score_info)}]" if score_info else ""

            lines.append(f"【{idx}】{title}{meta_line}")
            lines.append(f"    链接: {url}")
            lines.append(f"    摘要: {summary.strip()}")

            content = item.get("content")
            if need_content and content:
                # 截取一部分网页正文
                body_snippet = content.strip()[:400]
                lines.append(f"    正文片段: {body_snippet}...")

            lines.append("")

        output = "\n".join(lines).strip()
        if len(output) > max_chars:
            output = output[:max_chars] + f"\n\n[结果过长，已截断前 {max_chars} 字符]"
        return output

    def fetch_and_format(self, url: str, max_chars: int = 4000) -> str:
        """执行抓取并将 Markdown 结果排版为适合 AI 模型的文本"""
        res = self.fetch(url)

        if "error" in res:
            return f"❌ 网页抓取失败：{res['error']}"

        title = res.get("title", "").strip() or "未知标题"
        content = res.get("content", "").strip()

        if not content:
            return f"📄 网页「{title}」（{url}）未能提取到有效的 Markdown 正文。"

        output = f"📄 网页提取内容：【{title}】\n链接：{url}\n\n{content}"
        if len(output) > max_chars:
            output = output[:max_chars] + f"\n\n[网页内容过长，已保留前 {max_chars} 字符]"
        return output

    def _handle_error_response(self, status_code: int, response_text: str, action: str) -> str:
        """解析 DeepSeek 官方标准错误格式"""
        detail = ""
        try:
            err_json = json.loads(response_text)
            if "error" in err_json and isinstance(err_json["error"], dict):
                detail = err_json["error"].get("message", "")
        except Exception:
            detail = response_text[:200]

        error_map = {
            400: f"请求参数或格式不合法 (400): {detail}",
            401: f"API Key 缺失或无效 (401)，请检查配置。{detail}",
            402: f"账号余额不足 (402)，请充值后再试。{detail}",
            403: f"{action} 请求被安全策略拒绝 (403)。{detail}",
            404: f"未能获取可用的网页内容 (404)，URL 可能不存在或目标站点拦截了抓取。{detail}",
            408: f"请求体读取超时 (408)，请稍后重试。{detail}",
            413: f"请求体超过大小限制 (413)。{detail}",
            429: f"超过 {action} 的 QPS 速率限制 (429)，请稍等后重试。{detail}",
            500: f"DeepSeek 服务器内部错误 (500)。{detail}",
            504: f"下游请求超时 (504)。{detail}",
        }

        return error_map.get(status_code, f"{action} 接口返回 HTTP {status_code}: {detail or response_text[:150]}")
