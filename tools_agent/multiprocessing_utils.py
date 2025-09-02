"""
文件：tools_agent/multiprocessing_utils.py
功能：提供多进程处理的工具函数，特别针对Windows系统的优化
路径：/tools_agent/multiprocessing_utils.py
"""

import os
import sys
import platform
import multiprocessing
import subprocess
import tempfile
import logging
from typing import List, Callable, Any, Tuple, Optional
from multiprocessing import Pool, cpu_count
from functools import partial

# 检测是否在打包环境中运行
def is_packaged() -> bool:
    """检测程序是否在PyInstaller打包的环境中运行"""
    return getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS')

# 检测是否在Windows系统
def is_windows() -> bool:
    """检测是否在Windows系统上运行"""
    return platform.system() == "Windows"

def get_ideal_process_count(min_docs_per_process: int = 1) -> int:
    """
    根据CPU核心数获取理想的进程数
    
    Args:
        min_docs_per_process: 每个进程至少处理的文档数，用于优化小数据集的处理
        
    Returns:
        推荐的进程数
    """
    cpu_cores = cpu_count()
    # 保留一个核心给主进程和系统
    return max(1, cpu_cores - 1)

def create_no_window_process_windows(cmd: List[str], **kwargs) -> subprocess.Popen:
    """
    在Windows系统上创建一个无窗口的进程
    
    Args:
        cmd: 命令列表
        **kwargs: 传递给subprocess.Popen的其他参数
        
    Returns:
        subprocess.Popen对象
    """
    if "stdout" not in kwargs:
        kwargs["stdout"] = subprocess.PIPE
    if "stderr" not in kwargs:
        kwargs["stderr"] = subprocess.PIPE
        
    # 使用CREATE_NO_WINDOW标志创建进程，避免窗口弹出
    CREATE_NO_WINDOW = 0x08000000
    kwargs["creationflags"] = CREATE_NO_WINDOW
    
    return subprocess.Popen(cmd, **kwargs)

def determine_processing_strategy(data_count: int, threshold: int = 5) -> Tuple[bool, int]:
    """
    根据数据量和运行环境确定处理策略
    
    Args:
        data_count: 需要处理的数据项数量
        threshold: 单线程处理的阈值，默认为5条数据
        
    Returns:
        (use_multiprocessing, num_processes)元组
    """
    # 默认使用多进程
    use_multiprocessing = True
    # 获取建议的进程数
    num_processes = min(get_ideal_process_count(), data_count)
    
    # 在以下情况下使用单线程处理:
    # 1. 数据量小于阈值
    # 2. 在打包环境中运行且是Windows系统(为避免打包后的窗口弹出问题)
    if data_count <= threshold or (is_packaged() and is_windows()):
        use_multiprocessing = False
        num_processes = 1
        
    return use_multiprocessing, num_processes

def setup_windows_multiprocessing() -> None:
    """设置Windows系统下的多进程环境，避免窗口弹出问题"""
    if is_windows():
        # 在Windows上，使用spawn方法替代默认的fork方法
        # 这样可以避免一些与fork相关的问题
        multiprocessing.set_start_method('spawn', force=True)
        
        # 如果是在打包环境中运行，可以做进一步的优化
        if is_packaged():
            # 在打包环境下，可以考虑其他优化策略
            # 比如重定向标准输出到临时文件或空设备
            sys.stdout = open(os.devnull, 'w')
            sys.stderr = open(os.devnull, 'w')

def process_parallel(items: List[Any], 
                    process_func: Callable, 
                    process_args: Optional[Tuple] = None,
                    process_kwargs: Optional[dict] = None,
                    use_tqdm: bool = False,
                    desc: str = "Processing",
                    force_single_process: bool = False,
                    logging_callback: Optional[Callable] = None) -> List[Any]:
    """
    通用的并行处理函数，自动处理多进程/单进程选择，包含错误处理和进度显示
    
    Args:
        items: 需要处理的项目列表
        process_func: 处理单个项目的函数
        process_args: 传递给处理函数的位置参数
        process_kwargs: 传递给处理函数的关键字参数
        use_tqdm: 是否使用tqdm显示进度条
        desc: 进度条描述
        force_single_process: 强制使用单进程处理
        logging_callback: 日志回调函数
        
    Returns:
        处理结果列表
    """
    if process_args is None:
        process_args = ()
    if process_kwargs is None:
        process_kwargs = {}
        
    # 确定处理策略
    if force_single_process:
        use_multiprocessing = False
        num_processes = 1
    else:
        use_multiprocessing, num_processes = determine_processing_strategy(len(items))
    
    # 日志记录
    log_msg = f"处理策略: {'多进程' if use_multiprocessing else '单进程'}, 进程数: {num_processes}, 数据量: {len(items)}"
    if logging_callback:
        logging_callback(log_msg)
    else:
        print(log_msg)
    
    # 准备工作函数
    worker_func = partial(process_func, *process_args, **process_kwargs)
    
    results = []
    
    try:
        if use_multiprocessing:
            # Windows系统下设置多进程环境
            if is_windows():
                setup_windows_multiprocessing()
                
            # 使用进程池并行处理
            with Pool(processes=num_processes) as pool:
                # 如果使用tqdm，需要额外导入
                if use_tqdm:
                    try:
                        from tqdm import tqdm
                        results = list(tqdm(pool.imap(worker_func, items), total=len(items), desc=desc))
                    except ImportError:
                        results = list(pool.map(worker_func, items))
                else:
                    results = pool.map(worker_func, items)
        else:
            # 单进程顺序处理
            if use_tqdm:
                try:
                    from tqdm import tqdm
                    results = [worker_func(item) for item in tqdm(items, desc=desc)]
                except ImportError:
                    results = [worker_func(item) for item in items]
            else:
                results = [worker_func(item) for item in items]
                
    except Exception as e:
        error_msg = f"并行处理时发生错误: {str(e)}"
        if logging_callback:
            logging_callback(error_msg, level="ERROR")
        else:
            print(f"错误: {error_msg}", file=sys.stderr)
        # 返回空列表或部分结果
        return results
    
    return results 