# Get_data 项目文档

## 项目概述

Get_data 是一个用于收集、处理和分析编程语言包API变更信息的自动化流程。该项目通过爬虫技术收集API变更的URL，经过多轮处理和智能分析，最终生成结构化的API变更数据和代码示例。
本项目提供部分用于测试的数据集


## 🏗️ 项目结构

```
Get_data/
├── WebAgent/                     # WebAgent框架（核心爬虫工具）
│   ├── api_crawler.py           # 第一阶段：基础爬虫
│   ├── api_crawler_gpt.py       # 第二阶段：GPT增强爬虫
│   ├── visit_gpt4o_fixed.py     # GPT-4o页面访问工具
│   ├── pre_process/             # 预处理模块
│   │   ├── preprocess_data.py   # 数据过滤脚本
│   │   └── preprocess_data/     # 增强处理工具
│   │       ├── enhanced_api_crawler.py  # 智能API识别爬虫
│   │       ├── enhanced_lodash_processor.py  # Lodash示例提取器
│   │       └── enhanced_processor.py        # 通用示例提取器
│   ├── api_crawl_results_*.csv  # 第一阶段爬取结果（原始数据）
│   ├── api_crawl_temp_*.csv     # 临时爬取文件
│   └── preprocess_*.csv         # 预处理后的数据
└── WebAgent/                    # WebAgent核心框架
    └── WebAgent/                # WebAgent源代码
```

## 🔄 工作流程

### 第一阶段：数据收集

#### 1.1 准备URL输入文件
创建 `input.csv` 文件，包含需要爬取的URL：
```csv
url
https://example.com/api/doc1
https://example.com/api/doc2
```

#### 1.2 运行基础爬虫 (`api_crawler.py`)

**功能**：
- 批量爬取URL列表
- 提取基础的API信息
- 支持断点续爬
- 多线程并发处理

**使用方法**：
```bash
cd Get_data/WebAgent
python api_crawler.py
```

**输出**：
- `api_crawl_results_[package].csv` - 爬取结果
- `api_crawl_temp.csv` - 临时文件（支持断点续爬）

**字段说明**：
- `original_row_num` - 原始行号
- `url` - 源URL
- `api` - API名称
- `package` - 包/库名称
- `language` - 编程语言
- `deprecated_in` - 弃用版本
- `removed_in` - 移除版本
- `replaced_by` - 替代方案
- `change_type` - 变更类型
- `reason` - 变更原因
- `source` - 来源链接

#### 1.3 运行GPT增强爬虫 (`api_crawler_gpt.py`)

**功能**：
- 使用GPT模型对第一阶段结果进行深度分析
- 提取更准确的API变更信息
- 补充缺失的字段信息

**使用方法**：
```bash
cd Get_data/WebAgent
python api_crawler_gpt.py
```

**配置**：
- 需要配置OpenAI API密钥
- 支持自定义GPT模型选择

### 第二阶段：数据预处理

#### 2.1 数据过滤 (`preprocess_data.py`)

**功能**：
- 过滤没有实际变更的API记录
- 如果 `deprecated_in`、`removed_in` 和 `replaced_by` 三列同时为空，则删除该行

**使用方法**：
```bash
cd Get_data/WebAgent/pre_process
# 修改 preprocess_data.py 中的文件名
python preprocess_data.py
```

**配置**：
需要修改脚本中的输入输出文件名：
```python
input_file = 'api_crawl_results_[package].csv'
output_file = 'preprocess_[package].csv'
```

### 第三阶段：增强处理

#### 3.1 智能API识别 (`enhanced_api_crawler.py`)

**功能**：
- 使用GPT-4o智能识别URL对应的API
- 解决URL与API不匹配的问题
- 提取更准确的API变更信息

**特性**：
- 多层API识别策略（URL Fragment、路径、查询参数）
- GPT-4o智能分析与回退机制
- 支持React、Lodash等框架的特殊处理

**使用方法**：
```bash
cd Get_data/WebAgent/pre_process/preprocess_data
# 修改配置
INPUT_CSV = "preprocess_[package].csv"
OUTPUT_CSV = "enhanced_api_crawl_results.csv"
python enhanced_api_crawler.py
```

**配置**：
```python
# Azure OpenAI配置
AZURE_ENDPOINT = "https://your-endpoint.openai.azure.com/"
AZURE_DEPLOYMENT = "gpt-4o"
AZURE_API_KEY = "your-api-key"
```

#### 3.2 代码示例提取

对于需要提取代码示例的API（如React和Lodash），运行相应的处理器：

##### Lodash示例提取 (`enhanced_lodash_processor.py`)

**功能**：
- 从Lodash文档页面提取与特定API相关的代码示例
- 智能识别和分离代码块
- 生成包含代码和输出的结构化示例

**使用方法**：
```bash
cd Get_data/WebAgent/pre_process/preprocess_data
# 修改配置
csv_file = 'preprocess_Lodash.csv'
output_file = 'enhanced_lodash_examples.json'
python enhanced_lodash_processor.py
```

##### 通用示例提取 (`enhanced_processor.py`)

**功能**：
- 通用框架的代码示例提取
- 支持多种文档格式
- GPT智能匹配API与示例

## 📊 数据流程图

```
URL列表 → api_crawler.py → api_crawler_results.csv
                    ↓
           api_crawler_gpt.py → 增强的爬取结果
                    ↓
            preprocess_data.py → preprocess_[package].csv
                    ↓
        enhanced_api_crawler.py → 完善的API分析结果
                    ↓
        enhanced_processor.py → API代码示例（可选）
```

## 🔧 配置说明

### 环境要求

- Python 3.7+
- pandas
- requests
- beautifulsoup4
- openai
- azure-openai

### API密钥配置

1. **OpenAI API**（用于 api_crawler_gpt.py）：
```python
OPENAI_API_KEY = "your-openai-api-key"
```

2. **Azure OpenAI API**（用于 enhanced_* 脚本）：
```python
AZURE_ENDPOINT = "https://your-endpoint.openai.azure.com/"
AZURE_DEPLOYMENT = "gpt-4o"
AZURE_API_KEY = "your-azure-api-key"
```

## 📋 支持的编程语言和包

### Python生态
- **NumPy** - 数值计算库
- **Pandas** - 数据分析库
- **Django** - Web框架
- **Flask** - Web微框架
- **PyTorch** - 深度学习框架
- **TensorFlow** - 机器学习框架
- **scikit-learn** - 机器学习库
- **OpenCV** - 计算机视觉库
- **SQLAlchemy** - SQL工具包
- **Requests** - HTTP库

### Java生态
- **Spring Framework** - 应用框架
- **Hibernate** - ORM框架
- **Java SE** - 标准版API

### JavaScript生态
- **React** - UI库
- **Lodash** - 实用工具库
- **Angular** - 应用框架
- **Vue.js** - 渐进式框架
- **TypeScript** - 类型系统

### 其他语言
- **Go** - 编程语言标准库
- **Ruby** - 编程语言核心库
- **Scala** - 函数式编程语言
- **C++** - 标准库
- **Boost** - C++库集合

## 📈 输出数据格式

### 最终JSON示例

```json
{
  "source_url": "https://numpy.org/doc/.../ndarray.shape.html",
  "api": "numpy.ndarray.shape",
  "package": "NumPy",
  "change_type": "API Usage Discouraged",
  "reason": "Setting `arr.shape` is discouraged...",
  "has_examples": true,
  "examples": [
    {
      "code": "import numpy as np\nx = np.array([1, 2, 3])\nx.shape",
      "output": "(3,)"
    }
  ],
  "examples_count": 1,
  "extraction_method": "GPT-4o Enhanced"
}
```

## ⚡ 性能优化建议

1. **并发设置**：
   - 调整 `MAX_WORKERS` 以适应你的网络和CPU能力
   - 推荐 8-16 个线程

2. **批量处理**：
   - 使用 `BATCH_SIZE` 控制内存使用
   - 推荐 50-100 的批量大小

3. **断点续爬**：
   - 利用临时文件支持中断恢复
   - 避免重复爬取已完成的URL

## 🐛 常见问题

### 1. 爬虫被限制访问
**解决方案**：
- 降低并发数
- 增加重试间隔
- 使用代理

### 2. GPT API调用失败
**解决方案**：
- 检查API密钥配置
- 确认账户余额
- 使用回退机制

### 3. CSV文件编码问题
**解决方案**：
- 确保使用 UTF-8 编码
- 检查特殊字符处理

## 📝 使用示例

### 完整流程示例（以NumPy为例）

```bash
# 1. 准备URL列表
echo "url" > input.csv
echo "https://numpy.org/doc/stable/reference/generated/numpy.ndarray.shape.html" >> input.csv

# 2. 运行基础爬虫
cd Get_data/WebAgent
python api_crawler.py

# 3. 运行GPT增强
python api_crawler_gpt.py

# 4. 数据预处理
cd pre_process
# 修改 preprocess_data.py 的文件名为 NumPy
python preprocess_data.py

# 5. 增强处理
cd preprocess_data
# 配置 enhanced_api_crawler.py 的输入为 preprocess_NumPy.csv
python enhanced_api_crawler.py
```
