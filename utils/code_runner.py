"""
Python代码执行库 - 安全的Python代码执行器
支持代码执行、错误处理、安全限制和结果返回

作者: Assistant
版本: 1.0.0
"""

import sys
import io
import traceback
import time
import signal
import types
import ast
import builtins
from contextlib import contextmanager
from typing import Dict, Any, Optional, Tuple, List
import threading
import queue
import re

class CodeExecutionError(Exception):
    """代码执行相关异常"""
    pass


class SecurityError(CodeExecutionError):
    """安全相关异常"""
    pass


class TimeoutError(CodeExecutionError):
    """超时异常"""
    pass


class CodeExecutor:
    """
    安全的Python代码执行器
    
    特性:
    - 安全的代码执行环境
    - 超时控制
    - 内存和资源限制
    - 详细的错误报告
    - 支持多种输出格式
    """
    
    def __init__(self, 
                 timeout: float = 60.0,
                 max_output_length: int = 10000,
                 allowed_modules: Optional[List[str]] = None,
                 forbidden_functions: Optional[List[str]] = None,
                 security_level: str = 'medium',
                 enable_persistence: bool = True):
        """
        初始化代码执行器
        
        Args:
            timeout: 执行超时时间（秒）
            max_output_length: 最大输出长度
            allowed_modules: 允许导入的模块列表
            forbidden_functions: 禁止使用的函数列表
            security_level: 安全级别 ('strict', 'medium', 'permissive')
            enable_persistence: 是否启用持久化上下文功能
        """
        self.timeout = timeout
        self.max_output_length = max_output_length
        self.security_level = security_level
        self.enable_persistence = enable_persistence
        
        # 【持久化上下文】初始化持久化执行上下文
        self.persistent_context = {} if enable_persistence else None
        
        # 根据安全级别设置模块和函数限制
        if security_level == 'strict':
            # 严格模式：只允许基本的标准库
            default_allowed = [
                'math', 'random', 'datetime', 'json', 'collections',
                'itertools', 'functools', 'operator', 'string',
                'decimal', 'fractions', 'statistics', 're'
            ]
        elif security_level == 'medium':
            # 中等模式：允许常用的科学计算库
            default_allowed = [
                # 标准库
                'math', 'random', 'datetime', 'json', 'collections',
                'itertools', 'functools', 'operator', 'string',
                'decimal', 'fractions', 'statistics', 're', 'copy',
                'heapq', 'bisect', 'array', 'struct', 'time',
                'calendar', 'hashlib', 'base64', 'binascii',
                'textwrap', 'unicodedata', 'stringprep',
                # 科学计算库
                'numpy', 'pandas', 'scipy', 'matplotlib', 'seaborn',
                'sklearn', 'statsmodels', 'sympy', 'plotly',
                # 数据处理库
                'requests', 'urllib', 'http', 'csv', 'xml',
                'html', 'email', 'mimetypes',
                # 文件操作库
                'os', 'shutil', 'pathlib', 'glob',
                'open', 'file', 'input', 'raw_input',
                # 其他常用库
                'PIL', 'cv2', 'tqdm', 'joblib', 'pickle',
                'gzip', 'zipfile', 'tarfile', 'io', 
                 'tempfile', 'logging'
            ]
        else:  # permissive
            # 宽松模式：允许大部分库，只禁止明确危险的
            default_allowed = None  # None表示允许所有非危险模块
        
        self.allowed_modules = allowed_modules or default_allowed
        
        # 默认禁止的危险函数（更加精确）
        self.forbidden_functions = forbidden_functions or [
            'exec', 'eval', 'compile', '__import__',
            'input', 'raw_input',
            'exit', 'quit', 'help', 'copyright', 'credits', 'license',
            # 系统相关的危险函数
            'system', 'popen', 'spawn', 'fork', 'kill',
            # 网络相关的危险函数（但允许requests等库的使用）
            'socket', 'connect', 'bind', 'listen'
        ]
        
        # 创建安全的执行环境
        self._setup_safe_environment()
    
    def _setup_safe_environment(self):
        """设置安全的执行环境"""
        # 创建受限的内置函数字典
        safe_builtins = {}
        
        # 添加安全的内置函数
        safe_builtin_names = [
            'abs', 'all', 'any', 'bin', 'bool', 'bytearray', 'bytes',
            'callable', 'chr', 'classmethod', 'complex', 'dict', 'dir',
            'divmod', 'enumerate', 'filter', 'float', 'format', 'frozenset',
            'getattr', 'globals', 'hasattr', 'hash', 'hex', 'id', 'int',
            'isinstance', 'issubclass', 'iter', 'len', 'list', 'locals',
            'map', 'max', 'min', 'next', 'object', 'oct', 'ord', 'pow',
            'print', 'property', 'range', 'repr', 'reversed', 'round',
            'set', 'setattr', 'slice', 'sorted', 'staticmethod', 'str',
            'sum', 'super', 'tuple', 'type', 'vars', 'zip'
        ]
        
        # 添加安全的内置函数
        for name in safe_builtin_names:
            if hasattr(builtins, name):
                safe_builtins[name] = getattr(builtins, name)

        # ✅ 添加受限的 __import__ 函数（仅允许 allowed_modules）
        def safe_import(name, globals=None, locals=None, fromlist=(), level=0):
            top_level_name = name.split('.')[0]
            if not self._is_module_allowed(top_level_name):
                raise SecurityError(f"尝试导入未被允许的模块: {top_level_name}")
            return __import__(name, globals, locals, fromlist, level)

        safe_builtins['__import__'] = safe_import

        self.safe_builtins = safe_builtins
    
    def reset_context(self):
        """
        【持久化上下文】重置持久化执行上下文
        清除所有已保存的变量和状态
        """
        if self.enable_persistence:
            self.persistent_context = {}
    
    def get_context_variables(self) -> Dict[str, Any]:
        """
        【持久化上下文】获取当前持久化上下文中的所有变量
        
        Returns:
            包含所有变量的字典，不包含内置函数和模块
        """
        if not self.enable_persistence or not self.persistent_context:
            return {}
        
        # 过滤掉内置函数和模块，只返回用户定义的变量
        user_vars = {}
        for key, value in self.persistent_context.items():
            if (not key.startswith('__') and 
                not isinstance(value, types.ModuleType) and 
                key != '__builtins__'):
                user_vars[key] = value
        
        return user_vars
    
    def set_context_variable(self, name: str, value: Any):
        """
        【持久化上下文】在持久化上下文中设置变量
        
        Args:
            name: 变量名
            value: 变量值
        """
        if self.enable_persistence:
            if self.persistent_context is None:
                self.persistent_context = {}
            self.persistent_context[name] = value
    
    def remove_context_variable(self, name: str) -> bool:
        """
        【持久化上下文】从持久化上下文中删除变量
        
        Args:
            name: 要删除的变量名
            
        Returns:
            是否成功删除
        """
        if self.enable_persistence and self.persistent_context and name in self.persistent_context:
            del self.persistent_context[name]
            return True
        return False
    
    def _update_persistent_context(self, global_vars: Dict[str, Any]):
        """
        【持久化上下文】更新持久化上下文
        从执行后的全局变量中提取用户定义的变量并保存到持久化上下文
        
        Args:
            global_vars: 执行后的全局变量字典
        """
        if not self.enable_persistence:
            return
        
        # 初始化持久化上下文如果还没有
        if self.persistent_context is None:
            self.persistent_context = {}
        
        # 更新持久化上下文，只保存用户定义的变量
        for key, value in global_vars.items():
            # 跳过内置函数和模块，只保存用户定义的变量
            if (not key.startswith('__') and 
                not isinstance(value, types.ModuleType) and 
                key != '__builtins__'):
                self.persistent_context[key] = value
    
    def _is_module_allowed(self, module_name: str) -> bool:
        """
        检查模块是否被允许导入
        
        Args:
            module_name: 模块名
            
        Returns:
            是否允许导入
        """
        # 明确的危险模块，在任何安全级别下都不允许
        dangerous_modules = ['subprocess', 'socket', 'threading', 'multiprocessing']
        if module_name in dangerous_modules:
            return False
        
        # 如果允许列表为None（宽松模式），则允许所有非危险模块
        if self.allowed_modules is None:
            return True
        
        # 检查是否在允许列表中
        return module_name in self.allowed_modules
    
    def _check_security(self, code: str) -> None:
        """
        检查代码安全性
        
        Args:
            code: 要检查的代码字符串
            
        Raises:
            SecurityError: 如果代码包含不安全内容
        """
        try:
            # 解析代码为AST
            tree = ast.parse(code)
        except SyntaxError as e:
            raise CodeExecutionError(f"语法错误: {e}")
        
        # 检查AST节点
        for node in ast.walk(tree):
            # 检查导入语句
            if isinstance(node, ast.Import):
                for alias in node.names:
                    module_name = alias.name.split('.')[0]  # 获取顶级模块名
                    if not self._is_module_allowed(module_name):
                        raise SecurityError(f"不允许导入模块: {module_name}")
            
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    module_name = node.module.split('.')[0]  # 获取顶级模块名
                    if not self._is_module_allowed(module_name):
                        raise SecurityError(f"不允许导入模块: {module_name}")
            
            # 检查函数调用
            elif isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    if node.func.id in self.forbidden_functions:
                        raise SecurityError(f"不允许使用函数: {node.func.id}")
            
            # 检查属性访问
            elif isinstance(node, ast.Attribute):
                # 禁止访问某些危险属性
                dangerous_attrs = ['__import__', '__builtins__', '__globals__', '__locals__']
                if node.attr in dangerous_attrs:
                    raise SecurityError(f"不允许访问属性: {node.attr}")
    
    @contextmanager
    def _capture_output(self):
        """捕获标准输出和错误输出"""
        old_stdout = sys.stdout
        old_stderr = sys.stderr
        
        stdout_capture = io.StringIO()
        stderr_capture = io.StringIO()
        
        try:
            sys.stdout = stdout_capture
            sys.stderr = stderr_capture
            yield stdout_capture, stderr_capture
        finally:
            sys.stdout = old_stdout
            sys.stderr = old_stderr
    
    def _execute_with_timeout(self, code: str, global_vars: Dict[str, Any]) -> Tuple[Any, str, str]:
        """
        在超时限制下执行代码
        
        Args:
            code: 要执行的代码
            global_vars: 全局变量字典
            
        Returns:
            元组 (执行结果, 标准输出, 错误输出)
        """
        result_queue = queue.Queue()
        exception_queue = queue.Queue()
        
        def target():
            try:
                with self._capture_output() as (stdout_capture, stderr_capture):
                    # 编译代码
                    compiled_code = compile(code, '<string>', 'exec')
                    
                    # 执行代码
                    exec(compiled_code, global_vars)
                    
                    # 获取输出
                    stdout_output = stdout_capture.getvalue()
                    stderr_output = stderr_capture.getvalue()
                    
                    # 尝试获取最后一个表达式的结果
                    result = None
                    try:
                        # 如果代码是单个表达式，尝试评估它
                        lines = code.strip().split('\n')
                        last_line = lines[-1].strip()
                        if last_line and not last_line.startswith(('print', 'import', 'from', 'def', 'class', 'if', 'for', 'while', 'try', 'with')):
                            try:
                                result = eval(last_line, global_vars)
                            except:
                                pass
                    except:
                        pass
                    
                    result_queue.put((result, stdout_output, stderr_output))
            
            except Exception as e:
                exception_queue.put(e)
        
        # 创建并启动线程
        thread = threading.Thread(target=target)
        thread.daemon = True
        thread.start()
        
        # 等待执行完成或超时
        thread.join(timeout=self.timeout)
        
        if thread.is_alive():
            raise TimeoutError(f"代码执行超时 ({self.timeout}秒)")
        
        # 检查是否有异常
        if not exception_queue.empty():
            raise exception_queue.get()
        
        # 获取结果
        if not result_queue.empty():
            return result_queue.get()
        else:
            raise CodeExecutionError("代码执行失败，无法获取结果")
    
    def execute(self, code: str, context: Optional[Dict[str, Any]] = None, use_persistent: bool = True) -> Dict[str, Any]:
        """
        执行Python代码
        
        Args:
            code: 要执行的Python代码字符串
            context: 执行上下文（全局变量），如果为None且启用持久化，则使用持久化上下文
            use_persistent: 是否使用持久化上下文（仅在context为None时生效）
            
        Returns:
            包含执行结果的字典，包括:
            - success: 是否成功执行
            - result: 执行结果（如果有）
            - stdout: 标准输出
            - stderr: 错误输出
            - error: 错误信息（如果有）
            - execution_time: 执行时间
            - code_lines: 代码行号信息
            - context_variables: 当前上下文中的用户变量（仅在启用持久化时）
        """
        start_time = time.time()
        
        # 验证输入
        if not isinstance(code, str):
            return {
                'success': False,
                'result': None,
                'stdout': '',
                'stderr': '',
                'error': 'TypeError: 代码必须是字符串类型',
                'execution_time': 0,
                'code_lines': []
            }
        
        if not code.strip():
            return {
                'success': False,
                'result': None,
                'stdout': '',
                'stderr': '',
                'error': 'ValueError: 代码不能为空',
                'execution_time': 0,
                'code_lines': []
            }
        
        # 准备代码行信息
        code_lines = [f"{i+1}: {line}" for i, line in enumerate(code.split('\n'))]
        
        try:
            # 安全检查
            self._check_security(code)
            
            # 【持久化上下文】准备执行环境
            global_vars = {'__builtins__': self.safe_builtins}
            
            # 决定使用哪个上下文
            if context is not None:
                # 使用显式传入的上下文
                global_vars.update(context)
            elif self.enable_persistence and use_persistent and self.persistent_context:
                # 使用持久化上下文
                global_vars.update(self.persistent_context)
            
            # 执行代码
            result, stdout_output, stderr_output = self._execute_with_timeout(code, global_vars)
            
            # 【持久化上下文】如果启用持久化且没有显式传入上下文，更新持久化上下文
            if (self.enable_persistence and context is None and use_persistent):
                self._update_persistent_context(global_vars)
            
            # 限制输出长度
            if len(stdout_output) > self.max_output_length:
                stdout_output = stdout_output[:self.max_output_length] + "\n... (输出已截断)"
            
            if len(stderr_output) > self.max_output_length:
                stderr_output = stderr_output[:self.max_output_length] + "\n... (输出已截断)"
            
            execution_time = time.time() - start_time
            
            # 【持久化上下文】准备返回结果
            result_dict = {
                'success': True,
                'result': result,
                'stdout': stdout_output,
                'stderr': stderr_output,
                'error': None,
                'execution_time': execution_time,
                'code_lines': code_lines
            }
            
            # 如果启用持久化，添加上下文变量信息
            if self.enable_persistence:
                result_dict['context_variables'] = self.get_context_variables()
            
            return result_dict
        
        except (SecurityError, TimeoutError, CodeExecutionError) as e:
            execution_time = time.time() - start_time
            result_dict = {
                'success': False,
                'result': None,
                'stdout': '',
                'stderr': '',
                'error': f"{type(e).__name__}: {str(e)}",
                'execution_time': execution_time,
                'code_lines': code_lines
            }
            
            # 如果启用持久化，添加上下文变量信息
            if self.enable_persistence:
                result_dict['context_variables'] = self.get_context_variables()
            
            return result_dict
        
        except Exception as e:
            execution_time = time.time() - start_time
            error_info = traceback.format_exc()
            
            result_dict = {
                'success': False,
                'result': None,
                'stdout': '',
                'stderr': '',
                'error': f"{type(e).__name__}: {str(e)}\n\n详细错误信息:\n{error_info}",
                'execution_time': execution_time,
                'code_lines': code_lines
            }
            
            # 如果启用持久化，添加上下文变量信息
            if self.enable_persistence:
                result_dict['context_variables'] = self.get_context_variables()
            
            return result_dict
    
    def execute_multiple(self, code_blocks: List[str], shared_context: bool = False) -> List[Dict[str, Any]]:
        """
        执行多个代码块
        
        Args:
            code_blocks: 代码块列表
            shared_context: 是否在代码块之间共享上下文
            
        Returns:
            每个代码块的执行结果列表
        """
        results = []
        context = {} if shared_context else None
        
        for i, code in enumerate(code_blocks):
            result = self.execute(code, context)
            results.append(result)
            
            # 如果共享上下文且执行成功，更新上下文
            if shared_context and result['success']:
                # 这里可以添加更复杂的上下文更新逻辑
                pass
        
        return results
    
    def format_result(self, result: Dict[str, Any], verbose: bool = True) -> str:
        """
        格式化执行结果为可读字符串
        
        Args:
            result: execute方法返回的结果字典
            verbose: 是否显示详细信息
            
        Returns:
            格式化的结果字符串
        """
        lines = []
        
        if result['success']:
            lines.append("✅ 执行成功")
            
            if result['result'] is not None:
                lines.append(f"📊 结果: {repr(result['result'])}")
            
            if result['stdout']:
                lines.append(f"📝 输出:\n{result['stdout']}")
            
            if result['stderr']:
                lines.append(f"⚠️  警告:\n{result['stderr']}")
        
        else:
            lines.append("❌ 执行失败")
            lines.append(f"🚫 错误: {result['error']}")
        
        if verbose:
            lines.append(f"⏱️  执行时间: {result['execution_time']:.4f}秒")
            
            # 【持久化上下文】显示上下文变量信息
            if 'context_variables' in result and result['context_variables']:
                lines.append(f"🔄 持久化变量 ({len(result['context_variables'])} 个):")
                for var_name, var_value in result['context_variables'].items():
                    try:
                        # 限制显示长度，避免输出过长
                        value_str = repr(var_value)
                        if len(value_str) > 100:
                            value_str = value_str[:97] + "..."
                        lines.append(f"    {var_name}: {value_str}")
                    except:
                        lines.append(f"    {var_name}: <无法显示>")
            
            if result['code_lines']:
                lines.append(f"📋 代码 ({len(result['code_lines'])} 行):")
                for line in result['code_lines'][:10]:  # 只显示前10行
                    lines.append(f"    {line}")
                if len(result['code_lines']) > 10:
                    lines.append(f"    ... (还有 {len(result['code_lines']) - 10} 行)")
        
        return '\n'.join(lines)


# tool: 提取Python代码
def extract_python_code(text):
    # 定义用于匹配Python代码块的正则表达式
    pattern = re.compile(r'```python(.*?)```', re.DOTALL)
    # 使用findall()方法找到所有匹配的Python代码块
    pycode_list = pattern.findall(text)
    # 合并所有Python代码为一个字符串
    pycode = "\n".join(pycode_list)
    return pycode

# 便捷函数
def execute_code(code: str, **kwargs) -> Dict[str, Any]:
    """
    便捷函数：执行Python代码
    
    Args:
        code: 要执行的代码
        **kwargs: 传递给CodeExecutor的参数
        
    Returns:
        执行结果字典
    """
    executor = CodeExecutor(**kwargs)
    return executor.execute(code)


def quick_run(code: str, print_result: bool = True) -> Any:
    """
    快速运行代码并打印结果
    
    Args:
        code: 要执行的代码
        print_result: 是否打印结果
        
    Returns:
        执行结果中的result字段
    """
    executor = CodeExecutor()
    result = executor.execute(code)
    
    if print_result:
        print(executor.format_result(result))
    
    return result.get('result')


if __name__ == "__main__":
    # 【持久化上下文】演示持久化功能
    print("=" * 50)
    print("演示持久化功能")
    print("=" * 50)
    
    executor = CodeExecutor(enable_persistence=True)
    
    # 第一次执行：定义变量
    print("\n🔸 第一次执行：定义变量")
    code1 = """
import pandas as pd
df = pd.DataFrame({'A': [1, 2, 3], 'B': [4, 5, 6]})
x = 100
print("定义了df和x变量")
print(f"df形状: {df.shape}")
print(f"x的值: {x}")
"""
    
    result1 = executor.execute(code1)
    print(executor.format_result(result1))
    
    # 第二次执行：使用之前定义的变量
    print("\n🔸 第二次执行：使用之前定义的变量")
    code2 = """
# 使用之前定义的df和x
df['C'] = df['A'] + df['B'] + x
print("使用之前定义的变量df和x")
print("新增了C列")
print(df)
df
"""
    
    result2 = executor.execute(code2)
    print(executor.format_result(result2))
    
    # 第三次执行：进一步操作
    print("\n🔸 第三次执行：进一步操作")
    code3 = """
# 计算统计信息
total = df['C'].sum()
print(f"C列总和: {total}")
total
"""
    
    result3 = executor.execute(code3)
    print(executor.format_result(result3))
    
    # 演示上下文管理
    print("\n🔸 当前持久化变量:")
    context_vars = executor.get_context_variables()
    for name, value in context_vars.items():
        print(f"  {name}: {type(value).__name__}")
    
    print("\n🔸 演示重置上下文:")
    executor.reset_context()
    print("上下文已重置")
    
    # 尝试使用之前的变量（应该失败）
    print("\n🔸 重置后尝试使用之前的变量:")
    code4 = "print(f'x的值: {x}')"  # 这应该会失败
    result4 = executor.execute(code4)
    print(executor.format_result(result4, verbose=False))