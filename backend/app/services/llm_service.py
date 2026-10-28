"""LLM服务模块"""

from hello_agents import HelloAgentsLLM
import os

# 全局LLM实例
_llm_instance = None


def get_llm() -> HelloAgentsLLM:
    """
    获取LLM实例(单例模式)
    
    Returns:
        HelloAgentsLLM实例
    """
    global _llm_instance
    
    if _llm_instance is None:
        # HelloAgentsLLM会自动从环境变量读取配置
        # 包括OPENAI_API_KEY, OPENAI_BASE_URL, OPENAI_MODEL等
        candidate = HelloAgentsLLM(timeout=float(os.getenv("LLM_TIMEOUT", "90")))
        # The SDK otherwise resubmits timed-out generations twice. A failed
        # generation must not silently consume quota through repeated requests.
        candidate._client = candidate._client.with_options(max_retries=0)
        _llm_instance = candidate
        
        print(f"✅ LLM服务初始化成功")
        print(f"   提供商: {_llm_instance.provider}")
        print(f"   模型: {_llm_instance.model}")
    
    return _llm_instance


def reset_llm():
    """重置LLM实例(用于测试或重新配置)"""
    global _llm_instance
    _llm_instance = None

