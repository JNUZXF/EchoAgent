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
        # 获取参数模型
        _sig = inspect.signature(func)
        _params = _sig.parameters

        if not _params:
            raise ValueError("Tool function must have at least one Pydantic model argument.")

        first_param_name = next(iter(_params))
        # 解析注解, 兼容 from __future__ import annotations 带来的字符串注解
        if args_model is not None:
            model: Any = args_model
        else:
            try:
                hints = get_type_hints(func)
                model = hints.get(first_param_name, _params[first_param_name].annotation)
            except Exception:
                model = _params[first_param_name].annotation

        try:
            # pydantic v2 API
            parameters_schema: Dict[str, Any] = model.model_json_schema()  # type: ignore[attr-defined]
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
        self._name_to_model: Dict[str, Type[BaseModel]] = {}
        self._name_to_func: Dict[str, Callable] = {}
        self._schemas: List[Dict[str, Any]] = []

    def register(self, tool_func: Callable) -> None:
        """注册被 @tool 装饰过的函数"""
        if not hasattr(tool_func, "schema"):
            raise ValueError("Function must be decorated with @tool to be registered.")

        schema = getattr(tool_func, "schema")
        name = schema["function"]["name"]

        # 读取模型类型
        sig = inspect.signature(tool_func)
        first_param = next(iter(sig.parameters.values()))
        # 解析注解(兼容字符串注解)
        try:
            hints = get_type_hints(tool_func)
            model: Type[BaseModel] = hints.get(first_param.name, first_param.annotation)  # type: ignore[assignment]
        except Exception:
            model = first_param.annotation  # type: ignore[assignment]

        self._name_to_callable[name] = getattr(tool_func, "executable")
        self._name_to_model[name] = model
        self._name_to_func[name] = tool_func
        self._schemas.append(schema)

    def has(self, tool_name: str) -> bool:
        return tool_name in self._name_to_callable

    def execute(self, tool_name: str, arguments_json: str) -> Any:
        if tool_name not in self._name_to_callable:
            raise ValueError(f"工具 '{tool_name}' 未注册")

        func = self._name_to_callable[tool_name]
        model = self._name_to_model[tool_name]
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


