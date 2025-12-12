import os
import time
import json
import requests
from bs4 import BeautifulSoup
from openai import OpenAI

# OpenAI配置 - 使用GPT-4o
OPENAI_API_KEY = "xxx"
OPENAI_MODEL = "gpt-4o"

# 严格的事实提取提示词 - 只提取页面中明确且可验证的信息，严禁编造任何内容
extractor_prompt = """CRITICAL: Extract ONLY information that is explicitly and verifiably present in the webpage content. You must NOT invent, infer, or assume any information.

## Target URL
{url}

## Webpage Content
{webpage_content}

## STRICT INSTRUCTIONS

### STEP 1: Page Content Analysis
First, analyze what type of content this page actually contains:
- License file → Contains only legal text, NEVER contains API change information
- General index/overview → Usually contains no specific change information
- API reference documentation → May contain version notes, but often doesn't
- Migration guide/Release notes → Most likely to contain change information

### STEP 2: Evidence-Based Extraction
ONLY extract information if you find EXPLICIT EVIDENCE in the content:

#### ACCEPTABLE EVIDENCE (extract if found):
- Exact text containing: "deprecated", "removed", "obsolete", "replaced", "superseded"
- Version-specific statements: "since version X.X", "deprecated in version X.X"
- Direct replacement statements: "Use X instead of Y", "X replaces Y"
- Explicit migration instructions

#### UNACCEPTABLE EVIDENCE (DO NOT extract):
- General descriptions of what the API does
- Feature benefits or performance claims
- Comparisons between APIs without explicit replacement statements
- Any information that requires inference or assumption

### STEP 3: Truthfulness Verification
For each piece of information you extract, ask yourself:
1. "Can I point to the exact sentence that says this?"
2. "Is this stated as a fact, not as a possibility?"
3. "Is this about version changes or just general description?"

If you cannot answer YES to all three questions, DO NOT extract the information.

## Extraction Rules

1. **EMPTY IS BETTER THAN WRONG**: If no clear evidence exists, leave fields empty
2. **EXACT QUOTES**: When possible, use the exact wording from the page
3. **NO INFERENCE**: Never assume relationships between APIs unless explicitly stated
4. **HONESTY ABOUT LIMITATIONS**: If the page doesn't contain change info, state that

## JSON Output Format
Please respond with a JSON object containing the following fields:

{{
  "api": "string",
  "package": "string",
  "language": "string",
  "deprecated_in": "string",
  "removed_in": "string",
  "replaced_by": "string",
  "change_type": "string",
  "reason": "string",
  "source": "string"
}}

## FINAL REMINDER
- Your primary responsibility is TRUTH, not completeness
- It's better to return empty fields than to invent information
- If you cannot find explicit evidence of API changes in the content, change_type and reason must be empty
- NEVER extract information about API changes from license files, general overviews, or basic API documentation unless explicit change statements are present
- Please return your response as valid JSON format.
"""

class VisitGPT4o:
    def __init__(self):
        self.client = OpenAI(api_key=OPENAI_API_KEY)

    def llm(self, messages):
        """调用OpenAI GPT-4o进行内容提取"""
        max_retries = 3  # 减少重试次数
        for attempt in range(max_retries):
            try:
                response = self.client.chat.completions.create(
                    model=OPENAI_MODEL,  # 使用GPT-4o
                    messages=messages,
                    response_format={"type": "json_object"},
                    max_tokens=1000,  # 限制响应长度
                    temperature=0.1,  # 降低随机性
                    timeout=30,  # 30秒超时
                )
                return response.choices[0].message.content
            except Exception as e:
                print(f"GPT API调用第{attempt+1}次失败: {str(e)}")
                if attempt == max_retries - 1:
                    raise e
                time.sleep(3)  # 固定3秒等待时间
        return ""

    def read_webpage(self, url):
        """使用requests和BeautifulSoup读取网页内容，并定位到目标API部分"""
        try:
            import re
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
            }
            response = requests.get(url, headers=headers, timeout=15)  # 增加超时时间
            response.raise_for_status()  # 抛出HTTP错误
            print(f"成功获取网页内容: {url} (长度: {len(response.text)})")

            # 使用BeautifulSoup解析HTML
            soup = BeautifulSoup(response.text, 'html.parser')

            # 提取目标API名称（从URL的hash部分）
            target_api = ""
            if "#" in url:
                target_api = url.split("#")[-1]

            # 尝试定位到目标API部分
            if target_api:
                # 方法1: 通过id属性查找对应的元素
                target_element = soup.find(id=target_api)
                if target_element:
                    # 找到该元素及其后续兄弟元素，直到下一个主要API部分
                    content_parts = []
                    current = target_element

                    # 添加目标元素的内容
                    content_parts.append(str(current))

                    # 添加后续兄弟元素，直到遇到下一个API section
                    next_sibling = current.next_sibling
                    while next_sibling:
                        if hasattr(next_sibling, 'name'):
                            # 如果遇到同级别的标题，停止
                            if next_sibling.name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6'] and next_sibling.get('id') != target_api:
                                # 检查这个标题是否是另一个API section
                                sibling_text = next_sibling.get_text().strip()
                                if any(keyword in sibling_text.lower() for keyword in ['class', 'function', 'method', 'api']):
                                    break
                            content_parts.append(str(next_sibling))
                        next_sibling = next_sibling.next_sibling

                    # 创建新的soup对象来处理定位到的内容
                    targeted_html = '\n'.join(content_parts)
                    targeted_soup = BeautifulSoup(targeted_html, 'html.parser')

                    # 移除脚本和样式标签
                    for script in targeted_soup(["script", "style"]):
                        script.decompose()

                    # 添加一些上下文信息
                    text = f"TARGET API: {target_api}\n"
                    text += "TARGET API SECTION:\n"
                    text += targeted_soup.get_text(separator='\n', strip=True)
                    return text

            # 如果无法精确定位，则返回整个页面的内容
            # 移除脚本和样式标签
            for script in soup(["script", "style"]):
                script.decompose()

            # 获取纯文本内容
            text = soup.get_text(separator='\n', strip=True)

            # 如果有目标API名称，在内容前添加提示
            if target_api:
                text = f"TARGET API: {target_api}\nFULL PAGE CONTENT:\n{text}"

            return text

        except requests.exceptions.Timeout:
            print(f"网页读取超时: {url}")
            return ""
        except requests.exceptions.RequestException as e:
            print(f"网页请求错误: {url} - {str(e)}")
            return ""
        except Exception as e:
            print(f"网页读取错误: {url} - {str(e)}")
            return ""

    def call(self, params):
        """主调用方法：读取网页并提取信息"""
        params = json.loads(params)
        url = params.get("url")
        goal = params.get("goal")

        print(f"开始处理: {url}")

        # 读取网页内容
        webpage_content = self.read_webpage(url)
        if not webpage_content:
            print(f"❌ 无法读取网页内容: {url}")
            return json.dumps({"error": "无法读取网页内容"}, ensure_ascii=False)

        print(f"网页内容长度: {len(webpage_content)} 字符")

        # 如果内容过长，截断前2000个字符
        if len(webpage_content) > 2000:
            webpage_content = webpage_content[:2000] + "...\n[内容已截断]"
            print(f"网页内容已截断至2000字符")

        # 构建提示词
        prompt = extractor_prompt.format(url=url, webpage_content=webpage_content)

        # 调用GPT-4o提取信息
        print(f"正在调用GPT-4o分析...")
        messages = [{"role": "user", "content": prompt}]
        result = self.llm(messages)

        print(f"✅ 处理完成: {url}")
        return result