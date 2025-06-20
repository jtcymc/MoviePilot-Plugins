import os
import shutil

from app.log import logger


def clear_temp_folder(folder_path: str):
    """
    清空指定的文件夹
    :param folder_path: 要清空的文件夹路径
    """
    try:
        if os.path.exists(folder_path):
            # 删除整个目录及其内容
            shutil.rmtree(folder_path)

        # 重新创建空目录
        os.makedirs(folder_path)
        return True
    except Exception as e:
        logger.error(f"清空文件夹失败：{str(e)}")
        return False


def delete_folder(folder_path: str):
    """
    删除指定的文件夹
    :param folder_path: 要删除的文件夹路径
    """
    try:
        if os.path.exists(folder_path):
            # 删除整个目录及其内容
            shutil.rmtree(folder_path)
        return True
    except Exception as e:
        logger.error(f"删除文件夹失败：{str(e)}")
        return False


def creat_folder(folder_path: str):
    """
    创建指定的文件夹
    :param folder_path: 要创建的文件夹路径
    """
    try:
        if not os.path.exists(folder_path):
            os.makedirs(folder_path)
        return True
    except Exception as e:
        logger.error(f"创建文件夹失败：{str(e)}")
        return False
