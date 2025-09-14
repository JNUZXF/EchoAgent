"""
工具装饰器与注册表
文件路径: tools_agent/toolkit.py
功能: 提供基于 Pydantic 的 @tool 装饰器与 ToolRegistry, 用于从函数签名自动生成工具的 JSON Schema, 并统一执行工具。
"""

import inspect
import json
from typing import Any, Callable, Dict, List, Optional, Type, get_type_hints

try:
    from pydantic import BaseModel
except Exception as _e:  # 延迟导入错误在运行时抛出更明确的提示
    BaseModel = object  # type: ignore


def tool(_func: Optional[Callable] = None, *, args_model: Optional[Type[BaseModel]] = None) -> Callable:
    """
    将一个函数标记为 AI Agent 的工具, 自动从函数的第一个参数(应为 Pydantic 模型)生成 JSON Schema。

    使用方式:
    - 直接装饰并从注解推断参数模型:
        @tool
        def my_tool(args: MyArgs): ...

    - 显式传入参数模型(用于动态绑定/包装):
        def handler(args: Any): ...
        wrapped = tool(handler, args_model=MyArgs)
    """

    def _decorate(func: Callable) -> Callable:
        # 获取函数签名
        _sig = inspect.signature(func)
        _params = list(_sig.parameters.values())

        # 情况一：零参数工具（无需 Pydantic 模型）
        if not _params:
            parameters_schema: Dict[str, Any] = {
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            }

            schema = {
                "type": "function",
                "function": {
                    "name": func.__name__,
                    "description": (func.__doc__ or "").strip(),
                    "parameters": parameters_schema,
                },
            }

            # 包装成兼容 execute(args_obj) 的可调用对象
            def _wrapper_noargs(_ignored: Any = None) -> Any:
                return func()

            setattr(func, "schema", schema)
            setattr(func, "executable", _wrapper_noargs)
            return func

        # 情况二：仅 **kwargs 的自由参数工具
        if len(_params) == 1 and _params[0].kind == inspect.Parameter.VAR_KEYWORD:
            parameters_schema = {
                "type": "object",
                "properties": {},
                "additionalProperties": True,
            }

            schema = {
                "type": "function",
                "function": {
                    "name": func.__name__,
                    "description": (func.__doc__ or "").strip(),
                    "parameters": parameters_schema,
                },
            }

            def _wrapper_kwargs(args: Any = None) -> Any:
                data: Dict[str, Any]
                if isinstance(args, dict):
                    data = args
                else:
                    data = {}
                return func(**data)

            setattr(func, "schema", schema)
            setattr(func, "executable", _wrapper_kwargs)
            return func

        # 情况三：有参数工具（首参应为 Pydantic 模型）
        first_param_name = _params[0].name
        # 解析注解, 兼容 from __future__ import annotations 带来的字符串注解
        if args_model is not None:
            model: Any = args_model
        else:
            try:
                hints = get_type_hints(func)
                model = hints.get(first_param_name, _params[0].annotation)
            except Exception:
                model = _params[0].annotation

        try:
            # pydantic v2 API
            parameters_schema = model.model_json_schema()  # type: ignore[attr-defined]
        except Exception as e:
            raise TypeError(
                "The first argument of a tool function must be a Pydantic BaseModel "
                f"or provide args_model explicitly. error={e}"
            )

        schema = {
            "type": "function",
            "function": {
                "name": func.__name__,
                "description": (func.__doc__ or "").strip(),
                "parameters": parameters_schema,
            },
        }

        # 附加元信息
        setattr(func, "schema", schema)
        setattr(func, "executable", func)

        return func

    if _func is not None:
        return _decorate(_func)

    return _decorate


class ToolRegistry:
    """
    工具注册表: 统一存储工具可调用对象与其 Schema, 并提供执行入口。
    """

    def __init__(self) -> None:
        self._name_to_callable: Dict[str, Callable] = {}
        self._name_to_model: Dict[str, Optional[Type[BaseModel]]] = {}
        self._name_to_func: Dict[str, Callable] = {}
        self._schemas: List[Dict[str, Any]] = []
        # 记录工具文档与顺序，便于在系统提示词中展示纯文本说明
        self._tool_docs_by_name: Dict[str, str] = {}
        self._registration_order: List[str] = []

    def register(self, tool_func: Callable) -> None:
        """注册被 @tool 装饰过的函数"""
        if not hasattr(tool_func, "schema"):
            raise ValueError("Function must be decorated with @tool to be registered.")

        schema = getattr(tool_func, "schema")
        name = schema["function"]["name"]

        # 读取模型类型（零参/kwargs 工具不需要模型）
        sig = inspect.signature(tool_func)
        params = list(sig.parameters.values())
        if not params:
            model = None
        elif len(params) == 1 and params[0].kind == inspect.Parameter.VAR_KEYWORD:
            model = None
        else:
            # 解析注解(兼容字符串注解)
            try:
                hints = get_type_hints(tool_func)
                model = hints.get(params[0].name, params[0].annotation)  # type: ignore[assignment]
            except Exception:
                model = params[0].annotation  # type: ignore[assignment]

        self._name_to_callable[name] = getattr(tool_func, "executable")
        self._name_to_model[name] = model
        self._name_to_func[name] = tool_func
        self._schemas.append(schema)
        # 记录注册顺序
        self._registration_order.append(name)
        # 收集 docstring 作为工具说明文本
        doc = (tool_func.__doc__ or "").strip()
        # 若 doc 为空，回退到 schema 中的描述
        if not doc:
            try:
                doc = str(schema.get("function", {}).get("description", "")).strip()
            except Exception:
                doc = ""
        self._tool_docs_by_name[name] = doc

    def has(self, tool_name: str) -> bool:
        return tool_name in self._name_to_callable

    def execute(self, tool_name: str, arguments_json: str) -> Any:
        if tool_name not in self._name_to_callable:
            raise ValueError(f"工具 '{tool_name}' 未注册")

        func = self._name_to_callable[tool_name]
        model = self._name_to_model[tool_name]
        
        # 零参数/kwargs 工具：直接调用包装的可执行对象（传入 dict）
        if model is None:
            try:
                data_obj = json.loads(arguments_json or "{}")
            except Exception:
                data_obj = {}
            if not isinstance(data_obj, dict):
                data_obj = {}
            return func(data_obj)
        # 若注册时存入的是字符串注解, 此处再次解析保证为类型
        if not hasattr(model, "model_json_schema"):
            try:
                func_obj = self._name_to_func[tool_name]
                hints = get_type_hints(func_obj)
                first_param = next(iter(inspect.signature(func_obj).parameters.values()))
                model = hints.get(first_param.name, model)  # type: ignore[assignment]
                self._name_to_model[tool_name] = model
            except Exception:
                pass

        # 容错: 空参数或空对象
        if not arguments_json or arguments_json.strip() in ("", "null"):
            arguments_json = "{}"

        # Pydantic v2: 验证 + 解析
        import json as _json
        try:
            args_obj = model.model_validate_json(arguments_json)  # type: ignore[attr-defined]
        except AttributeError:
            data = _json.loads(arguments_json or "{}")
            try:
                args_obj = model.model_validate(data)  # type: ignore[attr-defined]
            except AttributeError:
                # pydantic v1 兼容
                args_obj = model.parse_obj(data)  # type: ignore[attr-defined]
        return func(args_obj)

    def get_schemas(self) -> List[Dict[str, Any]]:
        return self._schemas

    def get_schemas_json(self) -> str:
        return json.dumps(self._schemas, ensure_ascii=False, indent=2)

    def get_all_tool_names(self) -> List[str]:
        return list(self._name_to_callable.keys())

    def get_tool_docs_text(self) -> str:
        """
        返回聚合后的工具文档纯文本，用于注入系统提示词。

        展示格式（示例）：
        - search_arxiv: 基于关键词与数量检索 arXiv 摘要...
        - CodeRunner: 执行你编写的 Python 代码...
        """
        lines: List[str] = []
        for name in self._registration_order:
            doc = self._tool_docs_by_name.get(name, "").strip()
            if doc:
                lines.append(f"- {name}: {doc}")
            else:
                lines.append(f"- {name}: (no docstring)")
        return "\n".join(lines)


