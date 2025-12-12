#!/usr/bin/env python3
"""
Enhanced Documentation Crawler and Code Example Separator
爬取文档页面，使用GPT-4o智能识别和提取与特定API相关的代码示例
"""

import os
import re
import csv
import json
import time
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from typing import List, Dict, Any, Optional
from openai import AzureOpenAI


class EnhancedLodashDocProcessor:
    def __init__(self, azure_endpoint: str = None, azure_deployment: str = None, azure_api_key: str = None,
                 use_gpt: bool = True):
        # 对于增强版，默认启用GPT
        self.use_gpt = use_gpt and all([azure_endpoint, azure_deployment, azure_api_key])

        if self.use_gpt:
            try:
                self.azure_deployment = azure_deployment
                self.client = AzureOpenAI(
                    azure_endpoint=azure_endpoint,
                    api_key=azure_api_key,
                    api_version="2024-02-15-preview"
                )
                print("✅ GPT-4o API已启用 - 智能API匹配模式")
            except Exception as e:
                print(f"⚠️ GPT-4o API初始化失败: {e}，将使用手动分离")
                self.use_gpt = False
        else:
            print("ℹ️ GPT-4o未启用 - 将使用手动模式")

        # 初始化爬虫会话
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })

    def read_csv_sources(self, csv_file: str) -> List[Dict[str, str]]:
        """读取CSV文件，提取source列的URL"""
        sources = []
        try:
            with open(csv_file, 'r', encoding='utf-8') as file:
                reader = csv.DictReader(file)
                for row in reader:
                    if row.get('source') and row['source'].strip():
                        sources.append({
                            'url': row['source'].strip(),
                            'api': row.get('api', ''),
                            'package': row.get('package', ''),
                            'change_type': row.get('change_type', ''),
                            'reason': row.get('reason', '')
                        })
        except Exception as e:
            print(f"读取CSV文件出错: {e}")
        return sources

    def crawl_page(self, url: str) -> Optional[str]:
        """爬取页面内容"""
        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            return response.text
        except Exception as e:
            print(f"爬取页面失败 {url}: {e}")
            return None

    def extract_all_code_blocks(self, html_content: str) -> List[Dict[str, Any]]:
        """提取页面中所有的代码块，不进行过滤"""
        soup = BeautifulSoup(html_content, 'html.parser')
        code_blocks = []

        # 查找所有的pre标签
        pre_tags = soup.find_all('pre')

        for i, pre_tag in enumerate(pre_tags):
            code_text = pre_tag.get_text().strip()
            if not code_text:
                continue

            # 查找代码块之前的描述文本
            description = ""
            for prev in pre_tag.find_all_previous(['p', 'div', 'li', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6'], limit=5):
                text = prev.get_text().strip()
                if text and len(text) > 10 and not text.startswith('Example') and not text.startswith('Code'):
                    description = text
                    break

            code_blocks.append({
                'index': i,
                'code': code_text,
                'description': description,
                'element': pre_tag
            })

        return code_blocks

    def filter_examples_with_gpt(self, code_blocks: List[Dict], target_api: str, page_url: str) -> List[Dict[str, Any]]:
        """使用GPT-4o智能识别与目标API相关的代码示例"""
        if not self.use_gpt or not code_blocks:
            return []

        # 准备代码块文本用于分析
        code_blocks_text = ""
        for i, block in enumerate(code_blocks):
            code_blocks_text += f"代码块 {i+1}:\n```\n{block['code']}\n```\n"
            if block['description']:
                code_blocks_text += f"描述: {block['description']}\n"
            code_blocks_text += "\n" + "-"*50 + "\n\n"

        prompt = f"""你是一个文档分析专家。请分析以下文档页面的代码块，识别哪些代码示例是专门用来演示API "{target_api}" 的。

页面URL: {page_url}

所有代码块:
{code_blocks_text}

请按以下规则分析：
1. 识别直接使用 "{target_api}" 函数的代码示例
2. 识别演示 "{target_api}" 核心功能的示例
3. 排除只使用其他Lodash函数的示例
4. 排除与 "{target_api}" 无关的通用示例
5. 如果示例中同时包含多个API，但主要演示的是 "{target_api}"，则包含它
6. 注意代码描述中的提示，描述通常会说明这个示例演示的是哪个API

请返回JSON格式，只包含与 "{target_api}" 相关的代码示例：
{{
    "relevant_examples": [
        {{
            "block_index": 0,
            "is_relevant": true,
            "reason": "这个示例直接使用了{target_api}函数",
            "confidence": 0.9
        }},
        {{
            "block_index": 1,
            "is_relevant": false,
            "reason": "这个示例使用的是其他API",
            "confidence": 0.1
        }}
    ]
}}

注意：
- block_index 对应代码块在页面中的顺序（从0开始）
- confidence 是0-1之间的置信度分数
- 只返回is_relevant为true的示例的block_index列表"""

        try:
            response = self.client.chat.completions.create(
                model=self.azure_deployment,
                messages=[
                    {"role": "system", "content": "你是一个专业的Lodash文档分析专家，擅长识别代码示例与特定API的关联性。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=2000
            )

            content = response.choices[0].message.content.strip()
            result = json.loads(content)

            # 提取相关的代码块
            relevant_blocks = []
            if 'relevant_examples' in result:
                for example in result['relevant_examples']:
                    if example.get('is_relevant', False) and example.get('block_index') is not None:
                        block_index = example['block_index']
                        if 0 <= block_index < len(code_blocks):
                            relevant_blocks.append({
                                **code_blocks[block_index],
                                'gpt_confidence': example.get('confidence', 0.5),
                                'gpt_reason': example.get('reason', '')
                            })

            print(f"GPT识别出 {len(relevant_blocks)} 个与 {target_api} 相关的示例")
            return relevant_blocks

        except Exception as e:
            print(f"GPT API匹配失败: {e}，回退到关键词匹配")
            return self.filter_examples_by_keywords(code_blocks, target_api)

    def filter_examples_by_keywords(self, code_blocks: List[Dict], target_api: str) -> List[Dict[str, Any]]:
        """使用关键词匹配过滤示例（GPT失败时的回退方案）"""
        relevant_blocks = []

        # 清理API名称，移除可能的别名前缀
        clean_api = target_api.replace('_.', '').strip()

        for block in code_blocks:
            code = block['code']
            description = block['description']

            # 检查代码中是否包含目标API
            api_patterns = [
                rf'_\.{clean_api}',
                rf'lodash\.{clean_api}',
                rf'\.{clean_api}\(',
                rf'{clean_api}\(',
                rf'["\'`]{clean_api}["\'`]'  # 字符串中提到API名
            ]

            found_api = any(re.search(pattern, code, re.IGNORECASE) for pattern in api_patterns)

            # 检查描述中是否提到API
            description_mention = clean_api.lower() in description.lower() if description else False

            if found_api or description_mention:
                relevant_blocks.append({
                    **block,
                    'keyword_confidence': 0.7 if found_api else 0.5,
                    'keyword_reason': f"关键词匹配: {clean_api}"
                })

        print(f"关键词匹配识别出 {len(relevant_blocks)} 个与 {target_api} 相关的示例")
        return relevant_blocks

    def extract_and_separate_examples(self, relevant_blocks: List[Dict], target_api: str) -> List[Dict[str, str]]:
        """分离相关代码块为独立的示例"""
        if not relevant_blocks:
            return []

        # 合并所有相关代码块
        mixed_code = ""
        for block in relevant_blocks:
            mixed_code += f"{block['code']}\n\n"

        # 使用GPT分离示例
        if self.use_gpt:
            return self.extract_examples_gpt(mixed_code, target_api)
        else:
            return self.extract_examples_manual(mixed_code, target_api)

    def extract_examples_gpt(self, mixed_code: str, target_api: str) -> List[Dict[str, str]]:
        """使用GPT-4o提取并分离代码示例"""
        prompt = f"""你是一个JavaScript代码分析专家。请分析以下Lodash代码示例，专注于API "{target_api}"，将其分离为独立的代码示例，每个示例包含输入代码和对应的输出。

规则：
1. 只分析与 "{target_api}" 相关的代码示例
2. 识别独立的代码示例块（通常包含Lodash函数调用）
3. 每个示例应该包含完整的输入代码和对应的输出
4. 保持代码的原始格式和缩进
5. 错误信息也属于输出
6. 如果有多个相关的代码行，将它们组合为一个示例
7. **重要**：不要提取只有import/require语句的示例
8. 确保每个示例都包含 "{target_api}" 的使用

混合的代码：
```
{mixed_code}
```

请以JSON格式返回提取的结果：
[
    {{
        "code": "输入代码1，包含必要的require/import语句",
        "output": "对应的输出1"
    }},
    {{
        "code": "输入代码2，包含必要的require/import语句",
        "output": "对应的输出2"
    }}
]

注意：
- 每个code字段都应该包含完整的可执行代码，包括必要的require/import语句
- 保持代码的原始缩进和格式
- 不要添加任何额外的解释文字
- 如果没有输出，output字段设为空字符串
- **重要**：跳过只有require/import语句而没有实际操作的示例
- **重要**：确保每个示例都演示了 "{target_api}" 的用法"""

        try:
            response = self.client.chat.completions.create(
                model=self.azure_deployment,
                messages=[
                    {"role": "system", "content": f"你是一个专业的JavaScript代码分析专家，擅长识别和分离Lodash {target_api} 的代码示例。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=3000
            )

            content = response.choices[0].message.content.strip()
            result = json.loads(content)
            return result

        except Exception as e:
            print(f"GPT提取失败: {e}，回退到手动分离")
            return self.extract_examples_manual(mixed_code, target_api)

    def extract_examples_manual(self, mixed_code: str, target_api: str) -> List[Dict[str, str]]:
        """手动提取并分离代码示例"""
        lines = mixed_code.split('\n')
        examples = []
        current_example = {
            'code_lines': [],
            'output_lines': []
        }

        # 清理API名称
        clean_api = target_api.replace('_.', '').strip()

        # 检查是否包含Lodash引用
        has_lodash_import = any(
            ('import' in line and ('lodash' in line or '_' in line)) or
            ('require' in line and ('lodash' in line or '_' in line))
            for line in lines
        )

        for line in lines:
            stripped = line.strip()

            # 检测新的示例开始
            if ((stripped.startswith('>>>') or stripped.startswith('//') or
                 re.match(r'^(_|lodash|\w+)', stripped)) and
                ('=' in stripped or any(x in stripped for x in ['_.', 'function', '=>']) or
                 stripped.startswith('>>> console')) and
                current_example['code_lines']):

                # 保存当前示例（只有在有实际代码内容时）
                if self._has_actual_code(current_example['code_lines'], clean_api):
                    examples.append({
                        'code': self._format_code(current_example['code_lines'], has_lodash_import),
                        'output': '\n'.join(current_example['output_lines']).strip()
                    })

                # 开始新示例
                current_example = {
                    'code_lines': [line],
                    'output_lines': []
                }
            elif (stripped.startswith('>>>') or stripped.startswith('...') or
                  stripped.startswith('//') or re.match(r'^(_|lodash|\w+)', stripped)):
                # 继续当前示例的输入代码
                current_example['code_lines'].append(line)
            else:
                # 这是输出
                if stripped or current_example['output_lines']:
                    current_example['output_lines'].append(line)

        # 保存最后一个示例
        if current_example['code_lines'] and self._has_actual_code(current_example['code_lines'], clean_api):
            examples.append({
                'code': self._format_code(current_example['code_lines'], has_lodash_import),
                'output': '\n'.join(current_example['output_lines']).strip()
            })

        return examples

    def _has_actual_code(self, code_lines: List[str], target_api: str) -> bool:
        """检查代码行是否包含实际的功能代码且与目标API相关"""
        if not code_lines:
            return False

        # 检查是否有非import/require的代码行且包含目标API
        has_target_api = False
        has_actual_code = False

        for line in code_lines:
            stripped = line.strip()
            if stripped.startswith('>>>'):
                code_content = stripped[3:].strip()
                if code_content and not code_content.startswith('import') and not code_content.startswith('require'):
                    has_actual_code = True
                    if re.search(rf'\.{target_api}\s*\(', code_content) or target_api in code_content:
                        has_target_api = True
            elif stripped.startswith('...'):
                code_content = stripped[3:].strip()
                if code_content:
                    has_actual_code = True
                    if re.search(rf'\.{target_api}\s*\(', code_content) or target_api in code_content:
                        has_target_api = True
            elif stripped and not stripped.startswith('//'):
                if re.search(r'_\.|function|\w+\s*=|console\.|return', stripped):
                    has_actual_code = True
                    if re.search(rf'\.{target_api}\s*\(', stripped) or target_api in stripped:
                        has_target_api = True

        return has_actual_code and has_target_api

    def _format_code(self, code_lines: List[str], has_lodash_import: bool) -> str:
        """格式化代码行，去除>>>和...前缀，为每个示例添加完整的require语句"""
        formatted_lines = []

        if has_lodash_import:
            has_require = any('require' in line and ('lodash' in line or '_' in line) for line in code_lines)
            has_import = any('import' in line and ('lodash' in line or '_' in line) for line in code_lines)

            if not (has_require or has_import):
                formatted_lines.append("const _ = require('lodash');")

        for line in code_lines:
            stripped = line.strip()
            if stripped.startswith('>>>'):
                code_part = stripped[3:].lstrip()
                if not code_part.startswith('require') and not code_part.startswith('import'):
                    formatted_lines.append(code_part)
            elif stripped.startswith('...'):
                code_part = stripped[3:].lstrip()
                formatted_lines.append(code_part)
            else:
                formatted_lines.append(line)

        return '\n'.join(formatted_lines)

    def process_single_source(self, source_info: Dict[str, str]) -> Dict[str, Any]:
        """处理单个source，使用GPT智能匹配API与示例"""
        url = source_info['url']
        target_api = source_info.get('api', '')
        print(f"正在处理: {url} (目标API: {target_api})")

        # 爬取页面
        html_content = self.crawl_page(url)
        if not html_content:
            return {
                'source_url': url,
                'api': target_api,
                'package': source_info.get('package', ''),
                'change_type': source_info.get('change_type', ''),
                'reason': source_info.get('reason', ''),
                'has_examples': False,
                'examples': [],
                'examples_count': 0,
                'extraction_method': 'Crawl Failed'
            }

        # 提取所有代码块
        all_code_blocks = self.extract_all_code_blocks(html_content)
        if not all_code_blocks:
            return {
                'source_url': url,
                'api': target_api,
                'package': source_info.get('package', ''),
                'change_type': source_info.get('change_type', ''),
                'reason': source_info.get('reason', ''),
                'has_examples': False,
                'examples': [],
                'examples_count': 0,
                'extraction_method': 'No Code Blocks'
            }

        print(f"页面中共找到 {len(all_code_blocks)} 个代码块")

        # 使用GPT智能识别相关示例
        relevant_blocks = self.filter_examples_with_gpt(all_code_blocks, target_api, url)
        if not relevant_blocks:
            return {
                'source_url': url,
                'api': target_api,
                'package': source_info.get('package', ''),
                'change_type': source_info.get('change_type', ''),
                'reason': source_info.get('reason', ''),
                'has_examples': False,
                'examples': [],
                'examples_count': 0,
                'extraction_method': 'No Relevant Examples'
            }

        print(f"GPT识别出 {len(relevant_blocks)} 个相关代码块")

        # 分离代码示例
        separated_examples = self.extract_and_separate_examples(relevant_blocks, target_api)
        method = "GPT-4o Enhanced" if self.use_gpt else "Manual Enhanced"

        return {
            'source_url': url,
            'api': target_api,
            'package': source_info.get('package', ''),
            'change_type': source_info.get('change_type', ''),
            'reason': source_info.get('reason', ''),
            'has_examples': len(separated_examples) > 0,
            'examples': separated_examples,
            'examples_count': len(separated_examples),
            'extraction_method': method,
            'total_blocks_found': len(all_code_blocks),
            'relevant_blocks_found': len(relevant_blocks)
        }

    def process_sources(self, csv_file: str, output_file: str = 'enhanced_lodash_examples.json', limit: int = None):
        """处理所有source并生成智能匹配的示例"""
        sources = self.read_csv_sources(csv_file)
        print(f"找到 {len(sources)} 个source URL")

        if limit:
            sources = sources[:limit]
            print(f"限制处理前 {limit} 个source")

        all_results = []
        stats = {
            'total_sources': len(sources),
            'with_examples': 0,
            'without_examples': 0,
            'total_examples_extracted': 0,
            'total_blocks_found': 0,
            'relevant_blocks_found': 0,
            'method_used': []
        }

        for i, source in enumerate(sources):
            print(f"处理进度: {i+1}/{len(sources)}")
            result = self.process_single_source(source)
            all_results.append(result)

            # 更新统计信息
            if result['has_examples']:
                stats['with_examples'] += 1
                stats['total_examples_extracted'] += result['examples_count']
                stats['method_used'].append({
                    'api': result.get('api', ''),
                    'method': result.get('extraction_method', ''),
                    'examples_count': result['examples_count']
                })
            else:
                stats['without_examples'] += 1

            stats['total_blocks_found'] += result.get('total_blocks_found', 0)
            stats['relevant_blocks_found'] += result.get('relevant_blocks_found', 0)

            # 显示处理结果
            if i < 3:  # 显示前3个结果
                print(f"\n{'='*60}")
                print(f"处理结果 {i+1} (使用{result.get('extraction_method', '')})")
                print(f"API: {result.get('api', '')}")
                print(f"总代码块: {result.get('total_blocks_found', 0)}")
                print(f"相关代码块: {result.get('relevant_blocks_found', 0)}")
                print(f"提取的示例数量: {result['examples_count']}")
                if result['has_examples'] and result['examples']:
                    example = result['examples'][0]
                    print(f"\n示例预览:")
                    print(f"代码长度: {len(example['code'])} 字符")
                    print(f"代码预览: {example['code'][:150]}...")
                print(f"{'='*60}")

            # API调用间隔
            if self.use_gpt:
                time.sleep(0.5)
            time.sleep(1)

        # 保存结果
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(all_results, f, ensure_ascii=False, indent=2)

        # 生成报告
        self.generate_report(stats, all_results)

        print(f"\n{'='*60}")
        print(f" 处理完成！")
        print(f" 统计信息:")
        print(f"  总source数: {stats['total_sources']}")
        print(f"  有Examples: {stats['with_examples']}")
        print(f"  无Examples: {stats['without_examples']}")
        print(f"  总代码块数: {stats['total_blocks_found']}")
        print(f"  相关代码块数: {stats['relevant_blocks_found']}")
        print(f"  提取的示例总数: {stats['total_examples_extracted']}")
        if self.use_gpt:
            print(f"  使用GPT-4o智能匹配: {len(stats['method_used'])}")
        print(f" 结果已保存到: {output_file}")
        print(f" 详细报告已保存到: enhanced_lodash_processing_report.json")
        print(f"{'='*60}")

        return all_results

    def generate_report(self, stats: Dict, results: List[Dict]):
        """生成处理报告"""
        report = {
            'statistics': stats,
            'sample_results': [],
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
        }

        # 添加前几个结果示例
        for result in results[:5]:
            if result['has_examples']:
                sample_info = {
                    'source_url': result.get('source_url', ''),
                    'api': result.get('api', ''),
                    'examples_count': result.get('examples_count', 0),
                    'extraction_method': result.get('extraction_method', ''),
                    'total_blocks_found': result.get('total_blocks_found', 0),
                    'relevant_blocks_found': result.get('relevant_blocks_found', 0),
                    'examples': result.get('examples', [])[:2]
                }
                report['sample_results'].append(sample_info)

        # 保存报告
        with open('enhanced_lodash_processing_report.json', 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)


def main():
    # 配置参数
    csv_file = 'input.csv'
    output_file = 'output.json'
    limit = None  # 处理所有数据，取消限制

    # Azure OpenAI配置
    azure_endpoint = "https://test-openai-startup.openai.azure.com/"
    azure_deployment = "gpt-4o"
    azure_api_key = "xx"

    # 创建增强版处理器实例
    processor = EnhancedLodashDocProcessor(
        azure_endpoint=azure_endpoint,
        azure_deployment=azure_deployment,
        azure_api_key=azure_api_key,
        use_gpt=True  # 默认启用GPT智能匹配
    )

    # 开始处理
    processor.process_sources(csv_file, output_file, limit=limit)


if __name__ == "__main__":
    main()