import os
import requests

def request_vector(text: str):
    """请求文本向量嵌入 (可选组件，支持通过环境变量 EMBEDDING_API_KEY 配置)"""
    api_key = os.environ.get("EMBEDDING_API_KEY", "")
    if not api_key:
        return None
        
    url = os.environ.get("EMBEDDING_BASE_URL", "https://api.edgefn.net/v1/embeddings")
    model = os.environ.get("EMBEDDING_MODEL", "BAAI/bge-m3")
    headers = {
        "Authorization": f"Bearer {api_key}", 
        "Content-Type": "application/json"
    }
    data = {
        "model": model,
        "input": text
    }
    
    try:
        response = requests.post(url, headers=headers, json=data, timeout=10)
        return response.json()
    except Exception as e:
        print(f"Embedding Network Error: {e}")
        return None
