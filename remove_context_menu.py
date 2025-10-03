# -*- coding: utf-8 -*-
import ctypes
import sys
import winreg as reg
import os

def is_admin():
    """检查当前脚本是否以管理员权限运行"""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

def run_as_admin():
    """以管理员权限重新运行当前脚本"""
    try:
        ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, " ".join(sys.argv), None, 1)
    except Exception as e:
        print(f"提权失败: {e}")
        os.system("pause")

def delete_reg_tree_robust(hive, key_path):
    """
    健壮的注册表键树删除函数。
    它会先递归删除所有子键，然后再删除自身。
    """
    print(f"--- 正在处理键树: {key_path}")
    try:
        # 打开要删除的键，以便枚举其子键
        with reg.OpenKey(hive, key_path) as key:
            sub_key_names = []
            i = 0
            while True:
                try:
                    sub_key_names.append(reg.EnumKey(key, i))
                    i += 1
                except OSError:
                    # 没有更多子键了
                    break
            
            # 对所有子键进行递归删除
            for name in sub_key_names:
                sub_key_full_path = f"{key_path}\\{name}"
                delete_reg_tree_robust(hive, sub_key_full_path)
        
        # 当所有子键都被删除后，现在可以删除这个键本身了
        # 这需要打开它的父键
        parent_path, child_name = key_path.rsplit('\\', 1)
        with reg.OpenKey(hive, parent_path, 0, reg.KEY_ALL_ACCESS) as parent_key:
            reg.DeleteKey(parent_key, child_name)
            print(f"[SUCCESS] 已成功删除键: {key_path}")

    except FileNotFoundError:
        print(f"[INFO] 键不存在，无需操作: {key_path}")
    except PermissionError:
        print(f"[ERROR] 权限不足，无法删除: {key_path}")
    except Exception as e:
        print(f"[ERROR] 删除键 {key_path} 时发生未知错误: {e}")

def main():
    if not is_admin():
        print("需要管理员权限来修改注册表，正在尝试提权...")
        run_as_admin()
        sys.exit()

    print("--- 开始清理 Fast Transfer 右键菜单项 ---")

    # 1. 定义要删除的主菜单项
    main_keys_to_delete = [
        (reg.HKEY_CLASSES_ROOT, r"Directory\shell\fast_transfer"),
        (reg.HKEY_CLASSES_ROOT, r"Directory\Background\shell\fast_transfer"),
        (reg.HKEY_CLASSES_ROOT, r"Drive\shell\fast_transfer")
    ]
    for hive, path in main_keys_to_delete:
        delete_reg_tree_robust(hive, path)

    # 2. 定义要删除的命令定义项
    cmd_keys_to_delete = [
        (reg.HKEY_LOCAL_MACHINE, r"Software\Classes\fast_transfer_move"),
        (reg.HKEY_LOCAL_MACHINE, r"Software\Classes\fast_transfer_symlink"),
        (reg.HKEY_LOCAL_MACHINE, r"Software\Classes\fast_transfer_copy")
    ]
    for hive, path in cmd_keys_to_delete:
        delete_reg_tree_robust(hive, path)

    print("\n--- 清理完成 ---")
    print("所有相关的右键菜单注册表项均已处理完毕。")
    os.system("pause")

if __name__ == "__main__":
    main()
