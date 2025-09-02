import io
import sys
import traceback
import contextlib
import threading
import _thread
import re

# 定义全局变量字典
global_vars = {'__name__': '__main__'}

class TimeoutException(Exception):
    pass

def timeout_handler():
    _thread.interrupt_main()

@contextlib.contextmanager
def time_limit(seconds):
    timer = threading.Timer(seconds, timeout_handler)
    timer.start()
    try:
        yield
    finally:
        timer.cancel()

def format_exception(e, code):
    exc_type, exc_value, exc_traceback = sys.exc_info()
    formatted_lines = traceback.format_exception(exc_type, exc_value, exc_traceback)
    
    # 过滤掉不相关的堆栈信息
    relevant_lines = [line for line in formatted_lines if '<string>' in line]
    
    # 添加出错的代码行
    if relevant_lines:
        line_no = int(relevant_lines[-1].split(', line ')[1].split(',')[0])
        code_lines = code.split('\n')
        if 1 <= line_no <= len(code_lines):
            error_line = code_lines[line_no - 1]
            relevant_lines.append(f"Error in code:\n    {error_line}\n")
    
    return ''.join(relevant_lines)

def run_code(code, timeout=5*60*60, keep_state=True, restrict_modules=False, allowed_modules=None):
    """
    运行多行代码，带有超时控制和可选的模块限制
    
    参数:
    - code: 要执行的代码字符串
    - timeout: 执行超时时间（秒）
    - keep_state: 是否保持变量状态
    - restrict_modules: 是否限制模块导入
    - allowed_modules: 允许导入的模块列表（仅在restrict_modules=True时有效）
    """
    global global_vars
    if not keep_state:
        global_vars = {'__name__': '__main__'}
    
    if restrict_modules and allowed_modules is None:
        allowed_modules = ['math', 'random']
    
    output = io.StringIO()
    error_output = io.StringIO()

    with contextlib.redirect_stdout(output), contextlib.redirect_stderr(error_output):
        try:
            with time_limit(timeout):
                if restrict_modules:
                    # 保存原始模块状态
                    original_modules = sys.modules.copy()
                    # 限制模块导入
                    for module in sys.modules:
                        if module not in allowed_modules: # type: ignore
                            sys.modules[module] = type(sys)(module)
                
                compiled_code = compile(code, '<string>', 'exec')
                exec(compiled_code, global_vars, global_vars)
        except TimeoutException:
            print(f"执行超时（{timeout}秒）")
        except Exception as e:
            print(format_exception(e, code))
        else:
            print("执行完毕。代码执行成功。")
        finally:
            if restrict_modules:
                # 恢复原始模块状态
                sys.modules.clear()
                sys.modules.update(original_modules)

    result = output.getvalue()
    errors = error_output.getvalue()
    
    return result, errors, global_vars


# tool: 提取Python代码
def extract_python_code(text):
    # 定义用于匹配Python代码块的正则表达式
    pattern = re.compile(r'```python(.*?)```', re.DOTALL)
    # 使用findall()方法找到所有匹配的Python代码块
    pycode_list = pattern.findall(text)
    # 合并所有Python代码为一个字符串
    pycode = "\n".join(pycode_list)
    return pycode

if __name__ == "__main__":
    # 示例使用
    code1 = """
    import math
    a = 5
    b = math.sqrt(a)
    print(f"Square root of {a} is {b}")
    """

    code2 = """
    import random
    c = random.randint(1, 10)
    print(f"Random number: {c}")
    print(f"Previous result: {b}")
    """

    code3 = """
    import os
    print(os.getcwd())
    """

    print("执行代码1 (无限制):")
    result1, errors1, _ = run_code(code1, restrict_modules=False)
    print(result1)
    print(errors1)

    print("\n执行代码2 (无限制):")
    result2, errors2, _ = run_code(code2, restrict_modules=False)
    print(result2)
    print(errors2)

    print("\n执行代码3 (无限制):")
    result3, errors3, _ = run_code(code3, restrict_modules=False)
    print(result3)
    print(errors3)

    print("\n执行代码3 (有限制):")
    result4, errors4, _ = run_code(code3, restrict_modules=True, allowed_modules=['math', 'random'])
    print(result4)
    print(errors4)

