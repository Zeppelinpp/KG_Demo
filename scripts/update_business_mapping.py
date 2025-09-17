#!/usr/bin/env python3
"""
更新BUSINESS_MAPPING脚本

从Excel文件中读取财务分析场景数据，自动更新config/constants.py中的BUSINESS_MAPPING字典。
Excel文件的"问题描述"字段作为key，"数据源"+"期望结果"拼接作为value。

使用方法:
    python scripts/update_business_mapping.py [excel_file_path] [constants_file_path]

参数:
    excel_file_path: Excel文件路径，默认为 config/财务分析智能体分析场景评测.xlsx
    constants_file_path: constants.py文件路径，默认为 config/constants.py
"""

import pandas as pd
import argparse
import os
import sys
from pathlib import Path


def read_excel_data(excel_path):
    """读取Excel文件数据"""
    try:
        df = pd.read_excel(excel_path)
        print(f"✅ 成功读取Excel文件: {excel_path}")
        print(f"   - 总行数: {len(df)}")
        print(f"   - 列名: {list(df.columns)}")
        return df
    except Exception as e:
        print(f"❌ 读取Excel文件失败: {e}")
        sys.exit(1)


def generate_business_mapping(df):
    """从DataFrame生成BUSINESS_MAPPING字典内容"""
    mapping_lines = []
    mapping_lines.append("BUSSINESS_MAPPING = {")
    
    for index, row in df.iterrows():
        question = row.get('问题描述', '')
        data_source = row.get('数据源', '')
        expected_result = row.get('期望结果', '')
        
        # 只处理有问题描述的行
        if pd.notna(question) and question.strip():
            # 拼接数据源和期望结果
            value = str("相关节点:" + data_source) if pd.notna(data_source) else ''
            if pd.notna(expected_result) and expected_result.strip():
                if value:
                    value += '\\n' + str(expected_result)
                else:
                    value = str(expected_result)
            
            # 转义引号和换行符
            question_escaped = str(question).replace('"', '\\"').replace("'", "\\'")
            value_escaped = value.replace('"', '\\"').replace("'", "\\'").replace('\n', '\\n')
            
            mapping_lines.append(f'    "{question_escaped}": "{value_escaped}",')
    
    mapping_lines.append("}")
    
    return mapping_lines


def update_constants_file(constants_path, new_mapping_lines):
    """更新constants.py文件中的BUSINESS_MAPPING"""
    try:
        # 读取原文件内容
        with open(constants_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 备份原文件
        backup_path = constants_path + '.backup'
        with open(backup_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"✅ 已备份原文件到: {backup_path}")
        
        # 找到BUSINESS_MAPPING的开始和结束位置
        start_marker = "BUSSINESS_MAPPING = {"
        start_pos = content.find(start_marker)
        
        if start_pos == -1:
            print("❌ 未找到BUSINESS_MAPPING定义")
            sys.exit(1)
        
        # 找到对应的结束大括号
        brace_count = 0
        end_pos = start_pos
        for i, char in enumerate(content[start_pos:], start_pos):
            if char == '{':
                brace_count += 1
            elif char == '}':
                brace_count -= 1
                if brace_count == 0:
                    end_pos = i + 1
                    break
        
        # 构建新内容
        before_mapping = content[:start_pos]
        after_mapping = content[end_pos:]
        
        # 添加注释说明
        new_mapping_content = '\n'.join(new_mapping_lines)
        
        new_content = before_mapping + new_mapping_content + after_mapping
        
        # 写入新内容
        with open(constants_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        
        print(f"✅ 成功更新文件: {constants_path}")
        return True
        
    except Exception as e:
        print(f"❌ 更新文件失败: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description='更新BUSINESS_MAPPING脚本')
    parser.add_argument('excel_path', nargs='?', 
                       default='config/财务分析智能体分析场景评测.xlsx',
                       help='Excel文件路径')
    parser.add_argument('constants_path', nargs='?',
                       default='config/constants.py', 
                       help='constants.py文件路径')
    parser.add_argument('--dry-run', action='store_true',
                       help='仅显示生成的映射内容，不更新文件')
    
    args = parser.parse_args()
    
    # 检查文件是否存在
    if not os.path.exists(args.excel_path):
        print(f"❌ Excel文件不存在: {args.excel_path}")
        sys.exit(1)
    
    if not args.dry_run and not os.path.exists(args.constants_path):
        print(f"❌ Constants文件不存在: {args.constants_path}")
        sys.exit(1)
    
    print("🚀 开始更新BUSINESS_MAPPING...")
    print(f"   Excel文件: {args.excel_path}")
    print(f"   Constants文件: {args.constants_path}")
    print(f"   Dry run: {args.dry_run}")
    print()
    
    # 读取Excel数据
    df = read_excel_data(args.excel_path)
    
    # 生成映射内容
    mapping_lines = generate_business_mapping(df)
    
    if args.dry_run:
        print("\n📋 生成的BUSINESS_MAPPING内容:")
        print("=" * 50)
        for line in mapping_lines:
            print(line)
        print("=" * 50)
    else:
        # 更新文件
        if update_constants_file(args.constants_path, mapping_lines):
            print(f"\n🎉 成功完成更新！共处理了 {len(df)} 行数据")
        else:
            print("\n💥 更新失败")
            sys.exit(1)


if __name__ == "__main__":
    main()
