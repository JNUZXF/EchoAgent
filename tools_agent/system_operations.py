import requests
import os
import shutil
import json
import datetime
from .text2word import text_to_word
from .text2jupyter import text_to_jupyter
import pandas as pd
import pickle
import sys

# 添加日志函数
def log_system_message(level, message):
    """系统操作相关的日志记录器"""
    print(f"[{level}] [system_operations] {message}", file=sys.stderr)

class SystemOperations:
    @staticmethod
    def get_current_date():
        """
        获取当前日期
        """
        return datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    
    @staticmethod
    def text2word(text, filename):
        """
        文本转word，文件名需要加后缀
        """
        log_system_message("INFO", f"开始生成Word文档: {filename}")
        
        try:
            # 确保输入参数有效
            if not text or not text.strip():
                raise ValueError("输入文本为空")
            
            if not filename:
                raise ValueError("文件名为空")
            
            # 确保文件名有正确的扩展名
            if not filename.lower().endswith('.docx'):
                log_system_message("WARNING", f"文件名没有.docx后缀，自动添加: {filename}")
                filename = filename + '.docx'
            
            log_system_message("INFO", f"调用text_to_word函数，参数: 文本长度={len(text)}, 文件名={filename}")
            
            # 调用实际的转换函数
            text_to_word(text, filename)
            
            # 验证文件是否成功创建
            if os.path.exists(filename):
                file_size = os.path.getsize(filename)
                log_system_message("INFO", f"Word文档创建成功: {filename} (大小: {file_size} 字节)")
            else:
                log_system_message("ERROR", f"Word文档创建后文件不存在: {filename}")
                raise FileNotFoundError(f"生成的Word文档不存在: {filename}")
                
        except Exception as e:
            log_system_message("ERROR", f"生成Word文档时发生错误: {str(e)}")
            log_system_message("ERROR", f"错误类型: {type(e).__name__}")
            
            # 添加更详细的错误信息
            import traceback
            error_traceback = traceback.format_exc()
            log_system_message("ERROR", f"详细错误堆栈:\n{error_traceback}")
            
            # 重新抛出异常，让调用者能够处理
            raise e
    
    @staticmethod
    def text2jupyter(text, filename):
        """
        文本转jupyter，文件名需要加后缀
        """
        log_system_message("INFO", f"开始生成Jupyter文件: {filename}")
        
        try:
            text_to_jupyter(text, filename)
            log_system_message("INFO", f"Jupyter文件创建成功: {filename}")
        except Exception as e:
            log_system_message("ERROR", f"生成Jupyter文件时发生错误: {str(e)}")
            raise e
        
    @staticmethod
    def download_pdf(url, filename):
        """下载PDF文件

        Args:
            url (str): PDF文件的URL
            filename (str): 保存的文件名
        """
        try:
            response = requests.get(url)
            response.raise_for_status()
            with open(filename, 'wb') as file:
                file.write(response.content)
            print(f"PDF文件已下载并保存为 '{filename}'")
        except requests.HTTPError as http_err:
            print(f"HTTP错误: {http_err}")
        except Exception as err:
            print(f"下载PDF时发生错误: {err}")

    @staticmethod
    def create_folder(folder_name):
        try:
            if not os.path.exists(folder_name):
                os.makedirs(folder_name)
            #     print(f"文件夹 '{folder_name}' 创建成功")
            # else:
            #     print(f"文件夹 '{folder_name}' 已存在")
        except Exception as err:
            print(f"创建文件夹时发生错误: {err}")

    @staticmethod
    def move_file(file_name, to_path="files/already_read"):
        """
        移动文件到指定路径
        """
        try:
            if os.path.exists(file_name):
                shutil.move(file_name, to_path)
                print(f"文件 '{file_name}' 已移动到 '{to_path}'")
            else:
                print(f"文件 '{file_name}' 不存在")
        except Exception as err:
            print(f"移动文件时发生错误: {err}")

    # 提取某个文件夹下面的所有类型文件
    @staticmethod
    def extract_all_files_from_folder(path):
        """
        列出指定文件夹中的所有文件，包括子文件夹中的文件。
        
        参数:
        directory: 需要提取文件的文件夹路径。
        
        返回:
        文件的完整路径列表。
        """
        all_files = []
        
        # 遍历目录中的所有内容，包括子目录
        for root, dirs, files in os.walk(path):
            # 遍历文件
            for file in files:
                # 获取完整路径
                file_path = os.path.join(root, file)
                all_files.append(file_path)
        all_files = [file.replace("\\", "/") for file in all_files]
        return all_files

    @staticmethod
    def extract_file_path_from_folder(path, file_type=".pdf"):
        """
        提取某个路径下面所有的PDF文件路径
        """
        pdf_files = []
        for root, dirs, files in os.walk(path):
            for file in files:
                if file.endswith(file_type):
                    pdf_files.append("{}/{}".format(root, file))
        return pdf_files
    
    @staticmethod
    def save_text_to_file(text, filename):
        """
        将文本保存到文件
        """
        with open(filename, 'w', encoding='utf-8') as file:
            file.write(text)
        print(f"文本已保存到 '{filename}'")
    
    @staticmethod
    def read_file(file_path):
        _, file_extension = os.path.splitext(file_path)
        
        try:
            if file_extension.lower() in ['.csv', '.txt']:
                # 尝试使用pandas读取CSV文件
                return pd.read_csv(file_path)
            elif file_extension.lower() in ['.xlsx', '.xls']:
                # 读取Excel文件
                return pd.read_excel(file_path)
            elif file_extension.lower() == '.pkl':
                # 读取pickle文件
                with open(file_path, 'rb') as f:
                    return pickle.load(f)
            elif file_extension.lower() == '.json':
                # 读取JSON文件
                with open(file_path, "r") as f:
                    data = f.readlines()
                data = [json.loads(i) for i in data]
                df = pd.DataFrame(data)
                return df
            else:
                # 对于未知类型，尝试以文本方式读取
                with open(file_path, 'r') as f:
                    return f.read()
        except Exception as e:
            return f"无法读取文件: {str(e)}"
        
    @staticmethod
    def read_json(file_name):
        """
        读取文件内容
        """
        with open(file_name, 'r') as f:
            data = json.load(f)
        return data

    @staticmethod
    def save_json_data(data, file_path):
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)  # 关键是 ensure_ascii=False
        return file_path

    @staticmethod
    def list2json(data, file_path):
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)

    @staticmethod
    def get_file_name(file_path):
        if '/' in file_path:
            file_name = file_path.split('/')[-1].split('.')[-2]
        else:
            file_name = file_path.rsplit('.', 1)[0]
        return file_name
    
    @staticmethod
    def describe_dataframe(df):
        description = {}
        
        # 获取每列的数据类型
        description['Data Types'] = df.dtypes.to_dict()
        
        # 获取每列的缺失值信息
        description['Missing Values'] = df.isnull().sum().to_dict()
        
        # 获取每列的唯一值数量，添加数据类型检查
        unique_values = {}
        for col in df.columns:
            try:
                # 检查列中是否有无法哈希的数据类型，如字典等
                unique_values[col] = df[col].apply(lambda x: tuple(x) if isinstance(x, dict) else x).nunique()
            except TypeError:
                unique_values[col] = 'Cannot compute unique values for this column type'
        description['Unique Values'] = unique_values
        
        # 针对数值型列的基本统计信息
        numeric_desc = df.describe(include=[float, int]).to_dict()
        description['Numeric Summary'] = numeric_desc
        
        # 针对文本型列，获取字符长度分布和常见值，添加对不可哈希类型的处理
        text_columns = df.select_dtypes(include=[object]).columns
        text_summary = {}
        for col in text_columns:
            try:
                # 过滤掉无法哈希的复杂类型（如字典、列表等）
                hashable_values = df[col].apply(lambda x: tuple(x) if isinstance(x, dict) else x)
                text_summary[col] = {
                    'Most Frequent Values': hashable_values.value_counts().head(5).to_dict(),
                    'Length Distribution': df[col].dropna().apply(lambda x: len(str(x))).describe().to_dict()
                }
            except TypeError:
                text_summary[col] = 'Cannot compute frequent values for this column type'
        
        description['Text Columns Summary'] = text_summary
        
        return description


