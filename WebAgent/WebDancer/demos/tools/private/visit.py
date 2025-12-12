import os
import time
import json
import requests
from bs4 import BeautifulSoup
from openai import AzureOpenAI
from qwen_agent.tools.base import BaseTool
from qwen_agent.tools.base import register_tool

# 硬编码API配置
AZURE_ENDPOINT = "https://test-openai-startup.openai.azure.com/"
AZURE_DEPLOYMENT = "gpt-4o"
AZURE_API_KEY = "xxx"
AZURE_API_VERSION = "2025-01-01-preview"

# 英文提取提示词（注意JSON部分的大括号已转义）
extractor_prompt = """Process the following webpage content and user goal to extract detailed information about API version changes:

## Webpage Content
{webpage_content}

## User Goal
Extract the API's change information across different versions, including:
1. API name, its package, and programming language
2. Deprecation version (deprecated_in) and removal version (removed_in)
3. Replacement API (replaced_by) and change type (change_type)
4. Reason for the change (reason) and official source link (source)
5. Usage examples (before and after the change, if applicable)
6. The latest docstring (must include Parameters, Returns, Raises, and Examples sections)

## Extraction Rules
- If a field has no matching information, leave it empty but retain the field in the output
- The "examples" field must include code comparisons:
  - Example 1: Code usage before the change (if the API was modified/deprecated)
  - Example 2: Code usage after the change (or current usage for active APIs)
- The "docstring" must follow Python docstring standards (include Parameters, Returns, Raises, Examples)
- Valid values for "change_type": API Removal, API Deprecation, Parameter Change, Behavior Change, Performance Optimization

## Final Output Format (Strict JSON)
{{
  "api": "string",
  "package": "string",
  "language": "string",
  "deprecated_in": "string",
  "removed_in": "string",
  "replaced_by": "string",
  "change_type": "string",
  "reason": "string",
  "source": "string",
  "examples": [
    "Code example before the change (if applicable)",
    "Code example after the change (current usage)"
  ],
  "docstring": "Complete docstring with Parameters, Returns, Raises, Examples"
}}
"""
@register_tool('visit')
class Visit:
    name = 'visit'  # 与注册装饰器的名称完全一致
    
    # 以下是原有属性（保留不变）
    description = '访问指定URL并获取网页内容'
    parameters = {
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "需要访问的网页URL"
            }
        },
        "required": ["url"]
    }


    
    def __init__(self):
        # 初始化Azure OpenAI客户端
        self.client = AzureOpenAI(
            azure_endpoint=AZURE_ENDPOINT,
            api_key=AZURE_API_KEY,
            api_version=AZURE_API_VERSION,
        )

    def llm(self, messages):
        """调用Azure OpenAI进行内容提取"""
        max_retries = 10
        for attempt in range(max_retries):
            try:
                response = self.client.chat.completions.create(
                    model=AZURE_DEPLOYMENT,
                    messages=messages,
                    response_format={"type": "json_object"},
                )
                return response.choices[0].message.content
            except Exception as e:
                if attempt == max_retries - 1:
                    raise e
                time.sleep(2 **attempt)
        return ""

    def read_webpage(self, url):
        """使用requests和BeautifulSoup读取网页内容"""
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            }
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()  # 抛出HTTP错误
            
            # 使用BeautifulSoup提取文本内容
            soup = BeautifulSoup(response.text, 'html.parser')
            # 移除脚本和样式标签
            for script in soup(["script", "style"]):
                script.decompose()
            # 获取纯文本内容
            text = soup.get_text(separator='\n', strip=True)
            return text
        except Exception as e:
            print(f"网页读取错误: {str(e)}")
            return ""

    def call(self, params):
        """主调用方法：读取网页并提取信息"""
        params = json.loads(params)
        url = params.get("url")
        goal = params.get("goal")
        
        # 读取网页内容
        webpage_content = self.read_webpage(url)
        if not webpage_content:
            return json.dumps({"error": "无法读取网页内容"}, ensure_ascii=False)
        
        # 构建提示词
        prompt = extractor_prompt.format(webpage_content=webpage_content)
        
        # 调用LLM提取信息
        messages = [{"role": "user", "content": prompt}]
        result = self.llm(messages)
        
        return result

if __name__ == "__main__":
    # 测试代码
    visit = Visit()
    test_url = "https://docs.pytorch.org/docs/stable/generated/torch.linalg.lstsq.html"
    result = visit.call(json.dumps({
        "url": test_url,
        "goal": "提取API版本变更信息"
    }))
    print(result)
