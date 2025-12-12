import sys
import os
import json
import csv
import time
import threading
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from visit_gpt4o_fixed import VisitGPT4o  

# -------------------------- 核心配置 --------------------------
INPUT_CSV = "input.csv"       # URL的输入文件
OUTPUT_CSV = "output.csv"  # 最终结果输出文件 - 修改文件名
TEMP_CSV = "api_crawl_temp_gpt5.csv"       # 临时文件（用于断点续爬，避免数据丢失） - 修改文件名
# 爬取策略配置（针对大数量URL优化）
MAX_RETRIES = 2                       # 每个URL最多重试2次（减少API调用次数）
RETRY_DELAY = 2                       # 重试间隔2秒（给API更多时间）
MAX_WORKERS = 3                       # 线程数：减少到3（避免API限制）
BATCH_SIZE = 10                       # 每爬取10条URL，同步一次临时文件（更频繁保存）

# 全局锁（避免多线程写入CSV冲突）
csv_lock = threading.Lock()


# -------------------------- 1. 基础工具函数 --------------------------
def load_urls_from_csv(csv_file, temp_file=TEMP_CSV):
    """
    加载URL列表，支持断点续爬：
    - 跳过已爬取成功的URL
    - 记录未爬取/爬取失败的URL，继续处理
    """
    # 第一步：读取已爬取成功的URL（从临时文件）
    completed_urls = set()
    if os.path.exists(temp_file):
        with open(temp_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            if "url" in reader.fieldnames and "crawl_status" in reader.fieldnames:
                for row in reader:
                    if row["crawl_status"] == "success":
                        completed_urls.add(row["url"].strip())
        print(f"🔍 发现临时文件，已爬取成功 {len(completed_urls)} 条URL，将跳过这些URL")

    # 第二步：读取输入CSV的所有URL，过滤已完成的
    all_urls = []
    try:
        with open(csv_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            if "url" not in reader.fieldnames:
                raise ValueError("输入CSV必须包含'url'表头")

            for row_num, row in enumerate(reader, 2):  # 行号从2开始（表头为1）
                url = row["url"].strip()
                if url and url not in completed_urls:  # 跳过空URL和已完成的URL
                    all_urls.append({
                        "url": url,
                        "original_row_num": row_num  # 记录原始行号，便于核对
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
    """初始化临时CSV文件（用于断点续爬）"""
    if not os.path.exists(temp_file):
        with open(temp_file, "w", newline="", encoding="utf-8") as f:
            csv_columns = get_csv_columns()
            writer = csv.DictWriter(f, fieldnames=csv_columns, restval="")
            writer.writeheader()
    return temp_file


def get_csv_columns():
    """定义CSV输出字段（固定字段顺序，避免错乱）"""
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


# -------------------------- 2. 爬取核心函数（支持多线程） --------------------------
def crawl_single_api(url, original_row_num):
    """单URL爬取函数（线程安全，返回爬取结果字典） - 使用GPT-5"""
    result = {
        "original_row_num": original_row_num,
        "url": url,
        "crawl_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "crawl_status": "failed",
        "error_msg": ""
    }

    for retry in range(MAX_RETRIES):
        try:
            visit_tool = VisitGPT4o()  # 使用VisitGPT4o替代Visit
            crawl_params = json.dumps({
                "url": url,
                "goal": "只提取页面中明确存在的API变更信息。如果页面没有明确的变更说明，change_type和reason必须为空。严禁编造或推断任何信息。"
            })
            result_str = visit_tool.call(crawl_params)

            if not result_str.strip():
                raise ValueError("爬取结果为空字符串")

            # 合并爬取到的API信息
            api_data = json.loads(result_str)
            result.update(api_data)
            result["crawl_status"] = "success"
            result["error_msg"] = ""
            return result  # 爬取成功，直接返回

        except Exception as e:
            error_msg = f"第{retry+1}次重试失败：{str(e)}"
            result["error_msg"] = error_msg
            if retry < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY)  # 未到最大重试次数，等待后重试

    # 所有重试失败，返回失败结果
    result["error_msg"] = f"超过{MAX_RETRIES}次重试：{result['error_msg']}"
    return result


def write_result_to_csv(result, csv_file, lock):
    """线程安全的CSV写入函数（通过锁避免多线程写入冲突）"""
    with lock:
        with open(csv_file, "a", newline="", encoding="utf-8") as f:
            csv_columns = get_csv_columns()
            writer = csv.DictWriter(f, fieldnames=csv_columns, restval="")
            # 过滤掉不在字段列表中的键（避免多余字段导致报错）
            filtered_result = {k: result.get(k, "") for k in csv_columns}
            writer.writerow(filtered_result)


# -------------------------- 3. 批量爬取主逻辑（针对482条URL优化） --------------------------
def batch_crawl_large_scale(input_csv, output_csv, temp_csv):
    # 1. 初始化：加载待爬URL、初始化临时文件
    all_urls = load_urls_from_csv(input_csv, temp_csv)
    if not all_urls:
        print("🎉 所有URL已爬取完成，无需继续执行")
        # 将临时文件重命名为最终输出文件（如果需要）
        if os.path.exists(temp_csv) and not os.path.exists(output_csv):
            os.rename(temp_csv, output_csv)
        sys.exit(0)

    init_temp_csv(temp_csv)  # 确保临时文件存在且表头正确

    # 2. 初始化进度统计
    total_to_crawl = len(all_urls)
    completed_count = 0
    success_count = 0
    fail_count = 0
    start_time = datetime.now()

    print(f"\n🚀 开始批量爬取（使用GPT-5）：{start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"📊 配置：线程数={MAX_WORKERS}，重试次数={MAX_RETRIES}，每{MAX_WORKERS}条同步临时文件")
    print(f"⏳ 预计耗时：{total_to_crawl / MAX_WORKERS * 2:.1f} 秒（估算）\n")

    # 3. 多线程批量爬取（分批次处理，避免一次性创建过多线程）
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        # 提交所有爬取任务到线程池
        future_tasks = {
            executor.submit(crawl_single_api, url_info["url"], url_info["original_row_num"]):
            url_info for url_info in all_urls
        }

        # 实时处理完成的任务，更新进度
        for future in as_completed(future_tasks):
            url_info = future_tasks[future]
            url = url_info["url"]
            completed_count += 1

            try:
                # 获取爬取结果
                result = future.result(timeout=60)  # 超时时间60秒（避免线程挂起）
                # 写入临时文件
                write_result_to_csv(result, temp_csv, csv_lock)
                # 更新统计
                if result["crawl_status"] == "success":
                    success_count += 1
                    print(f"✅ [{completed_count}/{total_to_crawl}] 成功：{url}")
                else:
                    fail_count += 1
                    print(f"❌ [{completed_count}/{total_to_crawl}] 失败：{url}（{result['error_msg'][:50]}...）")

                # 每爬取BATCH_SIZE条，打印一次进度汇总
                if completed_count % BATCH_SIZE == 0 or completed_count == total_to_crawl:
                    elapsed_time = (datetime.now() - start_time).total_seconds()
                    avg_time_per_url = elapsed_time / completed_count if completed_count > 0 else 0
                    remaining_time = avg_time_per_url * (total_to_crawl - completed_count)
                    print(f"\n📈 进度汇总：已完成{completed_count}/{total_to_crawl}（成功{success_count}，失败{fail_count}）")
                    print(f"⏱️  已耗时：{elapsed_time:.1f}秒，预计剩余：{remaining_time:.1f}秒\n")

            except Exception as e:
                # 捕获线程执行中的异常（如超时、未知错误）
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

    # 4. 爬取完成：生成最终报告 + 合并临时文件到输出文件
    end_time = datetime.now()
    total_elapsed = (end_time - start_time).total_seconds()

    # 将临时文件重命名为最终输出文件（覆盖已存在的输出文件）
    if os.path.exists(temp_csv):
        if os.path.exists(output_csv):
            os.remove(output_csv)  # 删除旧的输出文件
        os.rename(temp_csv, output_csv)
        print(f"📁 临时文件已合并为最终结果：{os.path.abspath(output_csv)}")

    # 打印最终汇总报告
    print("\n" + "=" * 60)
    print("🎉 批量爬取任务完成（使用GPT-5）")
    print("=" * 60)
    print(f"📊 总统计：")
    print(f"   - 输入URL总数：{len(all_urls) + success_count + fail_count}")
    print(f"   - 待爬URL数：{total_to_crawl}")
    print(f"   - 成功数：{success_count}")
    print(f"   - 失败数：{fail_count}")
    print(f"   - 成功率：{success_count / total_to_crawl * 100:.1f}%" if total_to_crawl > 0 else "0%")
    print(f"⏱️  耗时：{total_elapsed // 60:.0f}分{total_elapsed % 60:.1f}秒")
    print(f"📄 结果文件：{os.path.abspath(output_csv)}")
    print("=" * 60)


# -------------------------- 4. 执行入口 --------------------------
if __name__ == "__main__":
    # 1. 添加项目路径（确保能导入VisitGPT5类）
    current_dir = os.path.dirname(os.path.abspath(__file__))
    sys.path.append(current_dir)

    # 2. 检查依赖文件
    if not os.path.exists(INPUT_CSV):
        print(f"❌ 输入CSV文件不存在：{INPUT_CSV}")
        sys.exit(1)

    # 3. 启动大规模批量爬取（使用GPT-5）
    print("🤖 使用GPT-5进行API信息提取")
    batch_crawl_large_scale(
        input_csv=INPUT_CSV,
        output_csv=OUTPUT_CSV,
        temp_csv=TEMP_CSV
    )