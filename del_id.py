#!/usr/bin/env python3
import json
import sys
import os

def remove_ids_from_jsonl(file_path, ids_to_remove):
    """
    从JSON Lines文件中删除指定ID的记录并写回原文件
    
    Args:
        file_path: JSONL文件路径
        ids_to_remove: 要删除的ID列表
    """
    # 备份原始文件
    backup_path = file_path + '.backup'
    try:
        os.replace(file_path, backup_path)
        print(f"已创建备份文件: {backup_path}")
    except Exception as e:
        print(f"创建备份失败: {e}")
        return False
    
    kept_records = []
    removed_count = 0
    
    # 读取备份文件并过滤记录
    with open(backup_path, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            
            try:
                record = json.loads(line)
                record_id = record.get('id')
                
                # 如果ID不在删除列表中，保留该记录
                if record_id not in ids_to_remove:
                    kept_records.append(record)
                else:
                    removed_count += 1
                    print(f"已删除ID为 {record_id} 的记录 (行号: {line_num})")
                    
            except json.JSONDecodeError as e:
                print(f"警告: 第{line_num}行JSON格式错误，已跳过: {e}")
                continue
            except Exception as e:
                print(f"警告: 处理第{line_num}行时出错，已跳过: {e}")
                continue
    
    # 将保留的记录写回原文件
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            for record in kept_records:
                f.write(json.dumps(record, ensure_ascii=False) + '\n')
        
        print(f"\n处理完成！")
        print(f"删除了 {removed_count} 条记录")
        print(f"保留了 {len(kept_records)} 条记录")
        print(f"原文件已更新: {file_path}")
        print(f"备份文件保留为: {backup_path}")
        return True
        
    except Exception as e:
        print(f"写入文件时出错: {e}")
        print(f"原始文件已备份在: {backup_path}")
        return False

# 要删除的ID列表（根据之前的统计结果）
IDS_TO_REMOVE = {
    30010161, 30010163, 30010164, 30010165, 30010166,
    30010181, 30010184, 30010188, 30010189, 30010190,
    30010191, 30010194, 30010203, 30010205, 30010210,
    30010216, 30010218
}

def main():
    # 文件路径（请根据实际情况修改）
    FILE_PATH = '买购网_知识百科_铜业知识大讲堂_79.json'
    
    # 检查文件是否存在
    if not os.path.exists(FILE_PATH):
        print(f"错误: 文件 '{FILE_PATH}' 不存在")
        print("请修改脚本中的 FILE_PATH 变量为正确的文件路径")
        sys.exit(1)
    
    # 确认操作
    print(f"准备从 {FILE_PATH} 中删除 {len(IDS_TO_REMOVE)} 个指定ID的记录")
    print("此操作将修改原文件并创建备份，是否继续? (yes/no)")
    
    response = input().strip().lower()
    if response not in ['yes', 'y']:
        print("操作已取消")
        sys.exit(0)
    
    # 执行删除操作
    success = remove_ids_from_jsonl(FILE_PATH, IDS_TO_REMOVE)
    
    if success:
        print("\n操作建议:")
        print("1. 请检查原文件内容是否正确")
        print("2. 如果没问题，可以删除备份文件以节省空间")
        print("3. 如果发现问题，可以将备份文件重命名为原文件名来恢复")
    else:
        print("\n操作失败，请检查备份文件")
        sys.exit(1)

if __name__ == '__main__':
    main()