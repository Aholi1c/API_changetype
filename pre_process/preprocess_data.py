#!/usr/bin/env python3
"""
预处理脚本：过滤api_crawl_results_pandas.csv文件
如果deprecated_in，removed_in和replaced_by列同时为空，则删除这一行
并将最终结果存入preprocess_xx.csv文件
"""

import pandas as pd
import os
from datetime import datetime


def preprocess_csv():
    """预处理CSV文件，过滤空值行"""
    print("🔧 开始预处理CSV文件...")

    # 输入文件路径
    input_file = 'api_crawl_results_Gin.csv'
    output_file = 'preprocess_Gin.csv'

    # 检查输入文件是否存在
    if not os.path.exists(input_file):
        print(f"❌ 输入文件不存在: {input_file}")
        return

    try:
        # 读取CSV文件
        print(f"📂 读取文件: {input_file}")
        df = pd.read_csv(input_file)

        # 显示原始数据统计
        original_count = len(df)
        print(f"📊 原始数据行数: {original_count}")

        # 检查列是否存在
        required_columns = ['deprecated_in', 'removed_in', 'replaced_by']
        missing_columns = [col for col in required_columns if col not in df.columns]

        if missing_columns:
            print(f"❌ 缺少必要的列: {missing_columns}")
            return

        # 过滤条件：deprecated_in，removed_in和replaced_by列同时为空
        # 空值包括：NaN
        mask = ~(
            df['deprecated_in'].isna() &
            df['removed_in'].isna() &
            df['replaced_by'].isna()
        )

        # 应用过滤
        filtered_df = df[mask]

        # 显示过滤结果统计
        filtered_count = len(filtered_df)
        removed_count = original_count - filtered_count

        print(f"📊 过滤后数据行数: {filtered_count}")
        print(f"🗑️ 删除的数据行数: {removed_count}")
        print(f"📈 保留率: {(filtered_count/original_count)*100:.1f}%")

        # 保存过滤后的数据
        filtered_df.to_csv(output_file, index=False, encoding='utf-8')
        print(f"💾 过滤后数据已保存到: {output_file}")

        # 显示一些被删除行的示例
        if removed_count > 0:
            print("\n📝 被删除行的示例（前5行）:")
            removed_rows = df[~mask].head()
            for idx, row in removed_rows.iterrows():
                print(f"  行 {row['original_row_num']}: {row['api']} - {row['package']}")

        # 显示过滤后数据的统计
        print(f"\n📊 过滤后数据统计:")
        print(f"  总行数: {filtered_count}")

        # 统计各个列的非空值数量
        for col in required_columns:
            non_empty_count = filtered_df[col].notna().sum()
            empty_count = filtered_df[col].isna().sum()
            print(f"  {col}: 非空值={non_empty_count}, 空值={empty_count}")

        print(f"\n✅ 预处理完成！")
        print(f"⏰ 处理时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        return filtered_df

    except Exception as e:
        print(f"❌ 处理过程中发生错误: {e}")
        return None


def main():
    """主函数"""
    print("🔧 CSV文件预处理工具")
    print("=" * 60)
    print("功能:")
    print("✅ 读取api_crawl_results_pandas.csv文件")
    print("✅ 过滤deprecated_in, removed_in, replaced_by同时为空的行")
    print("✅ 保存处理结果到preprocess_pandas.csv")
    print("✅ 提供详细的处理统计信息")
    print("=" * 60)

    # 执行预处理
    result = preprocess_csv()

    if result is not None:
        print(f"\n🎉 预处理任务完成！")
    else:
        print(f"\n❌ 预处理任务失败！")


if __name__ == "__main__":
    main()