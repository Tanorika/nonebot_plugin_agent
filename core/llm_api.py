"""
LLM API 请求模块
<<<<<<< HEAD
负责封装 API 请求逻辑，与具体的 AI 提供商交互
不包含记忆管理、任务注入等逻辑
=======
适配标准 OpenAI 兼容接口 (如 EdgeFN, DeepSeek 等)
采用非流式请求逻辑
>>>>>>> 61bfc77 (feat: initial release of nonebot_plugin_agent (clean sanitized framework))
"""
import json
import requests
from typing import List, Dict, Optional, Any
from nonebot.log import logger

<<<<<<< HEAD

class LLMAPIClient:
    """LLM API 客户端"""
    
    def __init__(self, api_key: str, base_url: str, model: str):
        """
        初始化 API 客户端
        
        Args:
            api_key: API 密钥
            base_url: API 基础 URL
            model: 模型名称
        """
        self.api_key = api_key
        self.base_url = base_url
=======
class LLMAPIClient:
    """LLM API 客户端"""

    STRICT_MAX_TOKENS = 16384
    
    def __init__(self, api_key: str, base_url: str, model: str):
        self.api_key = api_key
        # 确保基础 URL 格式正确，移除末尾斜杠
        self.base_url = base_url.rstrip('/')
>>>>>>> 61bfc77 (feat: initial release of nonebot_plugin_agent (clean sanitized framework))
        self.model = model
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
    
    def chat_completion(
        self,
<<<<<<< HEAD
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        stream: bool = True,
        timeout: int = 180
    ) -> str:
        """
        发起聊天补全请求
        
        Args:
            messages: 消息列表，格式为 [{"role": "user", "content": "..."}, ...]
            temperature: 温度参数，控制输出的随机性
            max_tokens: 最大生成 token 数（可选）
            stream: 是否使用流式响应
            timeout: 请求超时时间（秒）
        
        Returns:
            API 返回的完整响应字符串
=======
        messages: List[Dict[str, Any]],
        temperature: float = 0.7,
        stream: bool = False, # 默认为 False
        timeout: int = 180,
        strict: bool = False,
        max_tokens: int = 4096,
    ) -> str:
        """
        发起非流式聊天补全请求
>>>>>>> 61bfc77 (feat: initial release of nonebot_plugin_agent (clean sanitized framework))
        """
        # 构建请求数据
        data = {
            "model": self.model,
            "messages": messages,
<<<<<<< HEAD
            "stream": stream,
            "temperature": temperature
        }
        
        # 如果指定了 max_tokens，添加到请求中
        if max_tokens is not None:
            data["max_tokens"] = max_tokens
        
        # 调试日志
        logger.info(f"[AGENT API] 准备发送 API 请求")
        logger.info(f"[AGENT API] Base URL: {self.base_url}")
        logger.info(f"[AGENT API] Model: {self.model}")
        logger.info(f"[AGENT API] Messages count: {len(messages)}")
        logger.info(f"[AGENT API] Temperature: {temperature}")
        logger.info(f"[AGENT API] Stream: {stream}")
        
        try:
            # 发送流式请求
            response = requests.post(
                url=f"{self.base_url}/chat/completions",
                headers=self.headers,
                json=data,
                stream=stream,
                timeout=timeout
            )
            
            logger.info(f"[AGENT API] 响应状态码: {response.status_code}")
            
            if response.status_code != 200:
                error_msg = f"❌ API 错误: {response.status_code} - {response.text}"
                logger.error(f"[AGENT API] {error_msg}")
                return error_msg
            
            if stream:
                # 处理流式响应，累积完整内容
                logger.info(f"[AGENT API] 开始处理流式响应")
                result = self._process_stream_response(response)
                logger.info(f"[AGENT API] 流式响应处理完成，内容长度: {len(result)}")
                return result
            else:
                # 处理非流式响应
                logger.info(f"[AGENT API] 开始处理非流式响应")
                result = self._process_normal_response(response)
                logger.info(f"[AGENT API] 非流式响应处理完成，内容长度: {len(result)}")
                return result
                
        except requests.exceptions.Timeout:
            return "❌ 请求超时: API 响应时间过长"
        except requests.exceptions.RequestException as e:
            return f"❌ 请求异常: {str(e)}"
        except Exception as e:
            return f"❌ 未知异常: {str(e)}"
    
    def _process_stream_response(self, response: requests.Response) -> str:
        """
        处理流式响应
        
        Args:
            response: requests 响应对象
        
        Returns:
            完整的响应内容
        """
        full_content = ""
        line_count = 0
        content_lines = 0
        
        for line in response.iter_lines():
            if not line:
                continue
                
            line_count += 1
            line_str = line.decode('utf-8')
            
            # SSE 格式每行以 "data: " 开头
            if line_str.startswith('data: '):
                data_str = line_str[6:]  # 去掉 "data: " 前缀
                
                # 检查是否是结束标志
                if data_str.strip() == '[DONE]':
                    logger.info(f"[AGENT API] 收到结束标志 [DONE]")
                    break
                
                try:
                    chunk_data = json.loads(data_str)
                    
                    # 提取内容
                    if 'choices' in chunk_data and len(chunk_data['choices']) > 0:
                        delta = chunk_data['choices'][0].get('delta', {})
                        content = delta.get('content', '')
                        
                        if content:
                            full_content += content
                            content_lines += 1
                            if content_lines <= 5:  # 只记录前 5 条，避免日志过多
                                logger.debug(f"[AGENT API] 收到内容片段: {content[:50]}...")
                            
                except json.JSONDecodeError as e:
                    # 忽略无法解析的行
                    logger.warning(f"[AGENT API] JSON 解析失败: {data_str[:100]}")
        
        logger.info(f"[AGENT API] 流式响应处理完成: 总行数={line_count}, 内容行数={content_lines}, 总长度={len(full_content)}")
        return full_content
    
    def _process_normal_response(self, response: requests.Response) -> str:
        """
        处理非流式响应
        
        Args:
            response: requests 响应对象
        
        Returns:
            响应内容
        """
        try:
            data = response.json()
            
            # 提取内容
            if 'choices' in data and len(data['choices']) > 0:
                return data['choices'][0].get('message', {}).get('content', '')
            
            return ""
            
        except json.JSONDecodeError:
            return f"❌ 响应解析失败: {response.text}"
    
    def list_models(self) -> List[str]:
        """
        列出可用的模型
        
        Returns:
            模型名称列表
        """
        try:
            response = requests.get(
                url=f"{self.base_url}/models",
                headers=self.headers,
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                models = []
                
                if 'data' in data:
                    for model_data in data['data']:
                        models.append(model_data.get('id', ''))
                
                return models
            else:
                return []
                
        except Exception as e:
            print(f"❌ 获取模型列表失败: {e}")
            return []


# 便捷函数：快速创建 API 客户端
def create_api_client(config: Dict[str, Any]) -> LLMAPIClient:
    """
    根据配置创建 API 客户端
    
    Args:
        config: 配置字典，包含 api_key, base_url, model
    
    Returns:
        LLMAPIClient 实例
    """
    return LLMAPIClient(
        api_key=config.get("api_key", ""),
        base_url=config.get("base_url", ""),
        model=config.get("model", "")
    )
=======
            "stream": False,  # 强制关闭流式
            "temperature": temperature
        }
        # DeepSeek JSON Output guarantees a machine-readable agent response.
        data["response_format"] = {"type": "json_object"}
        # Reasoning models count private reasoning against max_tokens. Strict
        # summary requests retry with more room when reasoning exhausts it.
        requested_tokens = max_tokens
        
        try:
            # 官方 endpoint 拼接
            endpoint = f"{self.base_url}/chat/completions"

            attempt = 0
            while True:
                attempt += 1
                request_data = dict(data)
                request_data["max_tokens"] = requested_tokens
                logger.info(
                    f"[API] 正在发送请求到 {self.model} "
                    f"(purpose={'memory_summary' if strict else 'chat'}, "
                    f"attempt={attempt}, max_tokens={requested_tokens})"
                )
                response = requests.post(
                    url=endpoint,
                    headers=self.headers,
                    json=request_data,
                    timeout=timeout
                )

                # 检查状态码
                if response.status_code != 200:
                    if strict:
                        raise RuntimeError(f"Summary API HTTP {response.status_code}")
                    logger.error(f"[API] 错误: {response.status_code} - {response.text}")
                    return json.dumps({"reply": f"API 访问失败 (Code: {response.status_code})", "action": None, "params": {}}, ensure_ascii=False)

                # 解析响应
                result = response.json()

                if 'choices' not in result or len(result['choices']) == 0:
                    if strict:
                        raise ValueError("Summary API response has no choices")
                    logger.warning(f"[API] 响应格式异常: {result}")
                    return "❌ API 返回了空结果"

                # 提取回复内容
                choice = result['choices'][0]
                message = choice.get('message', {}) or {}
                content = message.get('content', '') or ''
                finish_reason = choice.get('finish_reason')
                incomplete = not content.strip() or finish_reason == 'length'
                if strict and incomplete:
                    reasoning = message.get('reasoning_content') or message.get('reasoning') or ''
                    usage = result.get('usage', {}) or {}
                    can_retry = requested_tokens < self.STRICT_MAX_TOKENS
                    if can_retry:
                        next_tokens = min(
                            self.STRICT_MAX_TOKENS,
                            max(requested_tokens * 2, 8192),
                        )
                        logger.warning(
                            "[API] Summary response incomplete "
                            f"(finish_reason={finish_reason!r}, "
                            f"content_chars={len(content)}, "
                            f"reasoning_chars={len(reasoning)}, "
                            f"completion_tokens={usage.get('completion_tokens', '?')}); "
                            f"retrying with max_tokens={next_tokens}"
                        )
                        requested_tokens = next_tokens
                        continue
                    raise ValueError(
                        "Summary API returned empty or truncated output "
                        f"after {attempt} attempts "
                        f"(finish_reason={finish_reason!r}, content_chars={len(content)}, "
                        f"reasoning_chars={len(reasoning)}, "
                        f"completion_tokens={usage.get('completion_tokens', '?')})"
                    )
                if not content.strip():
                    logger.warning("[API] JSON Output returned empty content")
                    return '{"reply":"","action":null,"params":{}}'
                return content
                
        except requests.exceptions.Timeout:
            if strict:
                raise
            return json.dumps({"reply": "请求超时，请稍后再试", "action": None, "params": {}}, ensure_ascii=False)
        except Exception as e:
            if strict:
                raise
            logger.error(f"[API] 发生未预料的错误: {str(e)}")
            return json.dumps({"reply": f"系统异常: {str(e)}", "action": None, "params": {}}, ensure_ascii=False)
>>>>>>> 61bfc77 (feat: initial release of nonebot_plugin_agent (clean sanitized framework))
