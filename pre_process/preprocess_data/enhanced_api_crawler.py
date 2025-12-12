#!/usr/bin/env python3
"""
Enhanced API Crawler with Smart Identification
基于WebAgent/api_crawler.py的架构，增加了智能API识别功能
专门解决URL与API不匹配的问题，同时保持与api_crawler.py相同的输出格式
"""

import sys
import os
import json
import csv
import time
import threading
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse
from bs4 import BeautifulSoup
from openai import AzureOpenAI

# -------------------------- 核心配置 --------------------------
INPUT_CSV = "pre_data.csv"  # URL的输入文件（可修改为React等）
OUTPUT_CSV = "output.csv"  # 最终结果输出文件
TEMP_CSV = "enhanced_api_crawl_temp.csv"  # 临时文件（用于断点续爬）

# 爬取策略配置
MAX_RETRIES = 3
RETRY_DELAY = 1
MAX_WORKERS = 8
BATCH_SIZE = 50

# Azure OpenAI配置
AZURE_ENDPOINT = "https://test-openai-startup.openai.azure.com/"
AZURE_DEPLOYMENT = "gpt-4o"
AZURE_API_KEY = "xxx"

# 全局锁（避免多线程写入CSV冲突）
csv_lock = threading.Lock()


class EnhancedAPICrawler:
    def __init__(self):
        # 初始化Azure OpenAI客户端
        try:
            self.client = AzureOpenAI(
                azure_endpoint=AZURE_ENDPOINT,
                api_key=AZURE_API_KEY,
                api_version="2024-02-15-preview"
            )
            self.use_gpt = True
            print("✅ GPT-4o API已启用 - 智能API识别模式")
        except Exception as e:
            print(f"⚠️ GPT-4o API初始化失败: {e}，将使用基础识别")
            self.use_gpt = False

        # 初始化HTTP客户端
        import requests
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })

    def extract_api_from_url(self, url: str) -> Dict[str, str]:
        """从URL中提取API信息的多种策略"""
        result = {
            'api_name': '',
            'confidence': 0.0,
            'method': 'none'
        }

        # 解析URL结构
        parsed = urlparse(url)
        path_parts = parsed.path.strip('/').split('/')

        # 策略1: Fragment/Hash识别
        if parsed.fragment:
            api_from_fragment = self._extract_from_fragment(parsed.fragment)
            if api_from_fragment:
                result['api_name'] = api_from_fragment
                result['confidence'] = 0.9
                result['method'] = 'fragment'
                return result

        # 策略2: URL路径识别
        api_from_path = self._extract_from_path(path_parts, parsed.netloc)
        if api_from_path:
            result['api_name'] = api_from_path
            result['confidence'] = 0.8
            result['method'] = 'path'
            return result

        # 策略3: 查询参数识别
        if parsed.query:
            api_from_query = self._extract_from_query(parsed.query)
            if api_from_query:
                result['api_name'] = api_from_query
                result['confidence'] = 0.6
                result['method'] = 'query'
                return result

        return result

    def _extract_from_fragment(self, fragment: str) -> str:
        """从URL fragment中提取API名称"""
        clean_fragment = fragment

        # 处理文档的fragment格式
        if '#' in fragment:
            clean_fragment = fragment.split('#')[-1]

        # 移除常见的前缀
        prefixes_to_remove = ['_', '-', '/', 'api-', 'function-', 'method-']
        for prefix in prefixes_to_remove:
            if clean_fragment.startswith(prefix):
                clean_fragment = clean_fragment[len(prefix):]

        # 提取第一个有效的标识符
        match = re.match(r'^([a-zA-Z][\w\.]*)', clean_fragment)
        if match:
            api_name = match.group(1)
            # 添加_前缀（如果缺失）
            if not api_name.startswith('_') and len(api_name) > 1:
                return f"_{api_name}"
            return api_name

        return ''

    def _extract_from_path(self, path_parts: List[str], domain: str) -> str:
        """从URL路径中提取API名称"""
        if not path_parts:
            return ''

        # React文档的特殊处理
        if 'react.dev' in domain or 'reactjs.org' in domain:
            for part in reversed(path_parts):
                if part and not part in ['reference', 'docs', 'api', 'hooks']:
                    return part

        # Lodash文档的特殊处理
        if 'lodash.com' in domain:
            for part in reversed(path_parts):
                if part and part not in ['docs', 'api']:
                    # Lodash函数通常是_.开头或者纯函数名
                    if not part.startswith('_'):
                        return f"_{part}"
                    return part

        #可添加其他文档的特殊处理

        # 通用路径提取
        for part in reversed(path_parts):
            if part and len(part) > 1 and not part in ['docs', 'api', 'reference', 'v1', 'v2', 'v3']:
                return part

        return ''

    def _extract_from_query(self, query: str) -> str:
        """从查询参数中提取API名称"""
        from urllib.parse import parse_qs
        params = parse_qs(query)

        # 常见的API参数名
        api_param_names = ['api', 'function', 'method', 'func', 'name']

        for param_name in api_param_names:
            if param_name in params and params[param_name]:
                return params[param_name][0]

        return ''

    def crawl_page_content(self, url: str) -> Dict[str, Any]:
        """爬取页面内容并提取结构化信息"""
        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, 'html.parser')

            # 提取页面标题
            title = ''
            title_tag = soup.find('title')
            if title_tag:
                title = title_tag.get_text().strip()

            # 提取所有标题
            headings = []
            for h1 in soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6']):
                headings.append({
                    'level': int(h1.name[1]),
                    'text': h1.get_text().strip(),
                    'id': h1.get('id', '')
                })

            # 提取页面主要文本内容
            for script in soup(["script", "style", "nav", "footer", "header"]):
                script.decompose()

            main_content = soup.get_text(separator='\n', strip=True)

            return {
                'url': url,
                'title': title,
                'headings': headings,
                'content': main_content,
                'status': 'success'
            }

        except Exception as e:
            return {
                'url': url,
                'status': 'failed',
                'error': str(e)
            }

    def identify_target_api_with_gpt(self, url: str, api_from_url: str, page_content: Dict) -> Dict[str, Any]:
        """使用GPT-4o智能识别目标API"""
        if not self.use_gpt or page_content.get('status') != 'success':
            return self._fallback_identification(api_from_url, page_content)

        # 准备提示信息
        prompt = f"""你是一个API文档分析专家。请分析以下URL和页面内容，识别出这个URL主要对应的是哪个API。

URL信息:
- 完整URL: {url}
- 从URL解析的API: {api_from_url}

页面信息:
- 标题: {page_content.get('title', '')}
- 主要标题: {json.dumps(page_content.get('headings', [])[:3], ensure_ascii=False)}

分析规则:
1. 检查页面标题是否明确提到了某个API名称
2. 检查主要标题(h1, h2)中是否包含API名称
3. 考虑URL解析的结果，但以页面实际内容为准
4. 对于React文档，API名称通常是Hook名称或组件名称
5. 对于Lodash文档，API名称通常是_开头的函数名

请返回JSON格式的分析结果:
{{
    "target_api": "识别出的主要API名称",
    "package": "对应的包名（react/lodash等）",
    "language": "编程语言（JavaScript等）",
    "deprecated_in": "弃用版本（如果适用）",
    "removed_in": "移除版本（如果适用）",
    "replaced_by": "替代API（如果适用）",
    "change_type": "变更类型",
    "reason": "变更原因",
    "source": "来源链接",
    "confidence": 0.9,
    "evidence": "判断依据的详细说明"
}}

注意：
- target_api应该是具体的API名称
- confidence是0-1之间的置信度分数
- 如果没有相关信息，字段留空"""

        try:
            messages = [
                {"role": "system", "content": "你是一个专业的API文档分析专家，擅长从URL和页面内容中识别目标API信息。"},
                {"role": "user", "content": prompt}
            ]

            response = self.client.chat.completions.create(
                model=AZURE_DEPLOYMENT,
                messages=messages,
                temperature=0.1,
                max_tokens=1500
            )

            result = json.loads(response.choices[0].message.content.strip())
            print(f"GPT识别结果: {result.get('target_api', 'N/A')} (置信度: {result.get('confidence', 0):.2f})")
            return result

        except Exception as e:
            print(f"GPT识别失败: {e}，使用回退方法")
            return self._fallback_identification(api_from_url, page_content)

    def _fallback_identification(self, api_from_url: str, page_content: Dict) -> Dict[str, Any]:
        """回退识别方法（不使用GPT）"""
        title = page_content.get('title', '')
        api_from_title = self._extract_api_from_text(title)

        # 确定包名
        package = ''
        if 'react' in title.lower() or 'react' in str(page_content.get('url', '')):
            package = 'react'
        elif 'lodash' in title.lower() or 'lodash' in str(page_content.get('url', '')):
            package = 'lodash'

        # 确定API名称
        target_api = api_from_title if api_from_title else api_from_url

        return {
            'target_api': target_api,
            'package': package,
            'language': 'JavaScript',
            'deprecated_in': '',
            'removed_in': '',
            'replaced_by': '',
            'change_type': '',
            'reason': '',
            'source': page_content.get('url', ''),
            'confidence': 0.6,
            'evidence': f"基于URL解析和页面标题分析: {title}"
        }

    def _extract_api_from_text(self, text: str) -> str:
        """从文本中提取API名称"""
        if not text:
            return ''

        # 常见的API模式
        patterns = [
            r'_([a-zA-Z][\w]*)',  # Lodash模式: _.functionName
            r'use([A-Z]\w*)',     # React Hook模式: useHookName
            r'react\.([A-Z]\w*)', # React API模式: React.Component
            r'\b([A-Z]\w*)\b',    # 组件模式: ComponentName
        ]

        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                match = matches[0]
                if pattern == patterns[0]:  # Lodash
                    return f"_{match}"
                elif pattern == patterns[1]:  # React Hook
                    return f"use{match}"
                elif pattern == patterns[2]:  # React API
                    return f"react.{match}"
                else:
                    return match

        return ''

    def crawl_single_api(self, url: str, original_row_num: int) -> Dict[str, str]:
        """单URL爬取函数（增强版，包含智能API识别）"""
        result = {
            "original_row_num": original_row_num,
            "url": url,
            "crawl_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "crawl_status": "failed",
            "error_msg": ""
        }

        for retry in range(MAX_RETRIES):
            try:
                print(f"正在处理: {url} (尝试 {retry+1}/{MAX_RETRIES})")

                # 第一步：从URL解析API
                url_info = self.extract_api_from_url(url)
                api_from_url = url_info.get('api_name', '')

                # 第二步：爬取页面内容
                page_content = self.crawl_page_content(url)
                if page_content.get('status') != 'success':
                    raise ValueError(f"页面爬取失败: {page_content.get('error', 'Unknown error')}")

                # 第三步：使用GPT智能识别API信息
                api_data = self.identify_target_api_with_gpt(url, api_from_url, page_content)

                # 合并结果到输出格式
                result.update({
                    "api": api_data.get('target_api', api_from_url),
                    "package": api_data.get('package', ''),
                    "language": api_data.get('language', 'JavaScript'),
                    "deprecated_in": api_data.get('deprecated_in', ''),
                    "removed_in": api_data.get('removed_in', ''),
                    "replaced_by": api_data.get('replaced_by', ''),
                    "change_type": api_data.get('change_type', ''),
                    "reason": api_data.get('reason', ''),
                    "source": api_data.get('source', url),
                    "crawl_status": "success",
                    "error_msg": ""
                })

                print(f"✅ 成功识别API: {result['api']} (置信度: {api_data.get('confidence', 0):.2f})")
                return result

            except Exception as e:
                error_msg = f"第{retry+1}次重试失败：{str(e)}"
                result["error_msg"] = error_msg
                if retry < MAX_RETRIES - 1:
                    time.sleep(RETRY_DELAY)

        # 所有重试失败，返回失败结果
        result["error_msg"] = f"超过{MAX_RETRIES}次重试：{result['error_msg']}"
        result["api"] = url_info.get('api_name', 'unknown')
        return result


# -------------------------- 基础工具函数 --------------------------
def load_urls_from_csv(csv_file, temp_file=TEMP_CSV):
    """加载URL列表，支持断点续爬"""
    completed_urls = set()
    if os.path.exists(temp_file):
        with open(temp_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            if "url" in reader.fieldnames and "crawl_status" in reader.fieldnames:
                for row in reader:
                    if row["crawl_status"] == "success":
                        completed_urls.add(row["url"].strip())
        print(f"🔍 发现临时文件，已爬取成功 {len(completed_urls)} 条URL，将跳过这些URL")

    # 读取输入CSV的所有URL，过滤已完成的
    all_urls = []
    try:
        with open(csv_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            if "url" not in reader.fieldnames:
                raise ValueError("输入CSV必须包含'url'表头")

            for row_num, row in enumerate(reader, 2):
                url = row["url"].strip()
                if url and url not in completed_urls:
                    all_urls.append({
                        "url": url,
                        "original_row_num": row_num
                    })

        total_input = len(all_urls) + len(completed_urls)
        print(f"✅ 从输入CSV加载完成：总计 {total_input} 条URL，待爬取 {len(all_urls)} 条，已完成 {len(completed_urls)} 条")
        return all_urls

    except FileNotFoundError:
        print(f"❌ 输入CSV文件不存在：{csv_file}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ 读取输入CSV失败：{str(e)}")
        sys.exit(1)


def init_temp_csv(temp_file=TEMP_CSV):
    """初始化临时CSV文件"""
    if not os.path.exists(temp_file):
        with open(temp_file, "w", newline="", encoding="utf-8") as f:
            csv_columns = get_csv_columns()
            writer = csv.DictWriter(f, fieldnames=csv_columns, restval="")
            writer.writeheader()
    return temp_file


def get_csv_columns():
    """定义CSV输出字段（与api_crawler.py保持一致）"""
    return [
        # 基础定位信息
        "original_row_num", "url", "crawl_time", "crawl_status", "error_msg",
        # API核心信息
        "api", "package", "language",
        # API变更信息
        "deprecated_in", "removed_in", "replaced_by", "change_type", "reason",
        # 来源信息
        "source"
    ]


def write_result_to_csv(result, csv_file, lock):
    """线程安全的CSV写入函数"""
    with lock:
        with open(csv_file, "a", newline="", encoding="utf-8") as f:
            csv_columns = get_csv_columns()
            writer = csv.DictWriter(f, fieldnames=csv_columns, restval="")
            # 过滤掉不在字段列表中的键
            filtered_result = {k: result.get(k, "") for k in csv_columns}
            writer.writerow(filtered_result)


# -------------------------- 批量爬取主逻辑 --------------------------
def batch_crawl_large_scale(input_csv, output_csv, temp_csv):
    # 1. 初始化
    all_urls = load_urls_from_csv(input_csv, temp_csv)
    if not all_urls:
        print("🎉 所有URL已爬取完成，无需继续执行")
        if os.path.exists(temp_csv) and not os.path.exists(output_csv):
            os.rename(temp_csv, output_csv)
        sys.exit(0)

    init_temp_csv(temp_csv)

    # 2. 初始化进度统计
    total_to_crawl = len(all_urls)
    completed_count = 0
    success_count = 0
    fail_count = 0
    start_time = datetime.now()

    print(f"\n🚀 开始批量爬取：{start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"📊 配置：线程数={MAX_WORKERS}，重试次数={MAX_RETRIES}")
    print(f"🤖 智能API识别：{'启用' if AZURE_API_KEY else '禁用'}")
    print(f"⏳ 预计耗时：{total_to_crawl / MAX_WORKERS * 2:.1f} 秒（估算）\n")

    # 3. 创建爬虫实例
    crawler = EnhancedAPICrawler()

    # 4. 多线程批量爬取
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_tasks = {
            executor.submit(crawler.crawl_single_api, url_info["url"], url_info["original_row_num"]):
            url_info for url_info in all_urls
        }

        # 实时处理完成的任务
        for future in as_completed(future_tasks):
            url_info = future_tasks[future]
            url = url_info["url"]
            completed_count += 1

            try:
                result = future.result(timeout=60)
                write_result_to_csv(result, temp_csv, csv_lock)

                if result["crawl_status"] == "success":
                    success_count += 1
                    print(f"✅ [{completed_count}/{total_to_crawl}] 成功：{url} → {result.get('api', 'N/A')}")
                else:
                    fail_count += 1
                    print(f"❌ [{completed_count}/{total_to_crawl}] 失败：{url}（{result['error_msg'][:50]}...）")

                # 批量进度汇总
                if completed_count % BATCH_SIZE == 0 or completed_count == total_to_crawl:
                    elapsed_time = (datetime.now() - start_time).total_seconds()
                    avg_time_per_url = elapsed_time / completed_count if completed_count > 0 else 0
                    remaining_time = avg_time_per_url * (total_to_crawl - completed_count)
                    print(f"\n 进度汇总：已完成{completed_count}/{total_to_crawl}（成功{success_count}，失败{fail_count}）")
                    print(f"⏱  已耗时：{elapsed_time:.1f}秒，预计剩余：{remaining_time:.1f}秒\n")

            except Exception as e:
                fail_count += 1
                error_result = {
                    "original_row_num": url_info["original_row_num"],
                    "url": url,
                    "crawl_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "crawl_status": "failed",
                    "error_msg": f"线程执行异常：{str(e)}"
                }
                write_result_to_csv(error_result, temp_csv, csv_lock)
                print(f"❌ [{completed_count}/{total_to_crawl}] 异常：{url}（{str(e)[:50]}...）")

    # 5. 完成：生成最终报告
    end_time = datetime.now()
    total_elapsed = (end_time - start_time).total_seconds()

    # 将临时文件重命名为最终输出文件
    if os.path.exists(temp_csv):
        if os.path.exists(output_csv):
            os.remove(output_csv)
        os.rename(temp_csv, output_csv)
        print(f" 临时文件已合并为最终结果：{os.path.abspath(output_csv)}")

    # 打印最终汇总报告
    print("\n" + "=" * 60)
    print(" 增强版批量爬取任务完成")
    print("=" * 60)
    print(f" 总统计：")
    print(f"   - 输入URL总数：{len(all_urls) + success_count + fail_count}")
    print(f"   - 待爬URL数：{total_to_crawl}")
    print(f"   - 成功数：{success_count}")
    print(f"   - 失败数：{fail_count}")
    print(f"   - 成功率：{success_count / total_to_crawl * 100:.1f}%" if total_to_crawl > 0 else "0%")
    print(f"⏱  耗时：{total_elapsed // 60:.0f}分{total_elapsed % 60:.1f}秒")
    print(f" 智能识别：{'GPT-4o增强' if crawler.use_gpt else '基础解析'}")
    print(f" 结果文件：{os.path.abspath(output_file)}")
    print("=" * 60)


# -------------------------- 执行入口 --------------------------
if __name__ == "__main__":
    # 1. 添加项目路径
    current_dir = os.path.dirname(os.path.abspath(__file__))
    sys.path.append(current_dir)

    # 添加必要的导入
    import re

    # 2. 检查依赖文件
    if not os.path.exists(INPUT_CSV):
        print(f"❌ 输入CSV文件不存在：{INPUT_CSV}")
        print("💡 提示：请修改INPUT_CSV变量为正确的文件路径")
        sys.exit(1)

    # 3. 启动增强版批量爬取
    batch_crawl_large_scale(
        input_csv=INPUT_CSV,
        output_csv=OUTPUT_CSV,
        temp_csv=TEMP_CSV
    )