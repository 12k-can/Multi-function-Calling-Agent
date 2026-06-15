"""
🔢 数学计算工具

提供基础的数学运算和高级数学计算能力。
使用 Python 标准库 + sympy 支持符号计算。
"""

import math
import json
from typing import Union, List


def register_math_tools(registry) -> None:
    """
    注册数学计算工具。
    
    Args:
        registry: ToolRegistry 实例。
    """

    @registry.register(
        name="calculate",
        description="执行基础数学运算（加、减、乘、除、幂、平方根、取模、百分比等）",
        metadata={"category": "math", "version": "1.0"},
    )
    def calculate(expression: str) -> str:
        """
        执行数学运算。
        
        :param expression: 数学表达式，如 "2 + 3 * 4", "sqrt(16)", "2 ** 10", "100 * 0.15"。
        :returns: 计算结果。
        """
        import ast
        import operator

        # 安全运算 — 只允许特定操作
        allowed_ops = {
            ast.Add: operator.add,
            ast.Sub: operator.sub,
            ast.Mult: operator.mul,
            ast.Div: operator.truediv,
            ast.Pow: operator.pow,
            ast.Mod: operator.mod,
            ast.FloorDiv: operator.floordiv,
            ast.UAdd: operator.pos,
            ast.USub: operator.neg,
        }

        allowed_funcs = {
            "abs": abs,
            "round": round,
            "min": min,
            "max": max,
            "sum": sum,
            "int": int,
            "float": float,
            "sqrt": math.sqrt,
            "sin": math.sin,
            "cos": math.cos,
            "tan": math.tan,
            "log": math.log,
            "log10": math.log10,
            "exp": math.exp,
            "pi": math.pi,
            "e": math.e,
            "ceil": math.ceil,
            "floor": math.floor,
            "pow": pow,
        }

        def _safe_eval(node):
            if isinstance(node, ast.Expression):
                return _safe_eval(node.body)
            if isinstance(node, ast.Constant):
                return node.value
            if isinstance(node, ast.Num):  # Python < 3.8
                return node.n
            if isinstance(node, ast.BinOp):
                op_type = type(node.op)
                if op_type not in allowed_ops:
                    raise ValueError(f"不支持的操作符: {op_type.__name__}")
                left = _safe_eval(node.left)
                right = _safe_eval(node.right)
                return allowed_ops[op_type](left, right)
            if isinstance(node, ast.UnaryOp):
                op_type = type(node.op)
                if op_type not in allowed_ops:
                    raise ValueError(f"不支持的一元操作: {op_type.__name__}")
                operand = _safe_eval(node.operand)
                return allowed_ops[op_type](operand)
            if isinstance(node, ast.Call):
                func_name = node.func.id if isinstance(node.func, ast.Name) else None
                if func_name not in allowed_funcs:
                    raise ValueError(f"不支持的函数: {func_name}")
                args = [_safe_eval(arg) for arg in node.args]
                return allowed_funcs[func_name](*args)
            if isinstance(node, ast.Name):
                if node.id in allowed_funcs:
                    return allowed_funcs[node.id]
                raise ValueError(f"未知的符号: {node.id}")
            raise ValueError(f"不支持的表达式: {type(node).__name__}")

        try:
            tree = ast.parse(expression.strip(), mode="eval")
            result = _safe_eval(tree.body)
            # 格式化结果
            if isinstance(result, float):
                if result == int(result):
                    result_str = str(int(result))
                else:
                    result_str = f"{result:.6f}".rstrip("0").rstrip(".")
            else:
                result_str = str(result)
            return f"= {result_str}"
        except Exception as e:
            raise ValueError(f"表达式错误: {e}")

    @registry.register(
        name="solve_equation",
        description="解数学方程（使用 sympy 符号计算），如一元二次方程、方程组等",
        metadata={"category": "math", "version": "1.0"},
    )
    def solve_equation(equation: str, variable: str = "x") -> str:
        """
        解数学方程。
        
        :param equation: 方程表达式，如 "x**2 - 4", "x**2 + 2*x + 1 = 0", "2*x + 3 = 7"。
        :param variable: 待求解的变量名，默认为 "x"。
        :returns: 方程的解。
        """
        try:
            from sympy import symbols, Eq, solve, sympify
            from sympy.parsing.sympy_parser import (
                parse_expr,
                standard_transformations,
                implicit_multiplication_application,
            )
        except ImportError:
            return "需要安装 sympy 库：pip install sympy"

        transformations = (
            standard_transformations + (implicit_multiplication_application,)
        )

        try:
            var = symbols(variable)
            eq_str = equation.strip()

            if "=" in eq_str:
                # 处理 "表达式 = 值" 格式
                left_str, right_str = eq_str.split("=", 1)
                left_expr = parse_expr(left_str.strip(), local_dict={variable: var},
                                        transformations=transformations)
                right_expr = parse_expr(right_str.strip(), local_dict={variable: var},
                                         transformations=transformations)
                eq = Eq(left_expr, right_expr)
            else:
                # 处理 "表达式 = 0" 格式
                expr = parse_expr(eq_str, local_dict={variable: var},
                                  transformations=transformations)
                eq = Eq(expr, 0)

            solutions = solve(eq, var, dict=True)

            if not solutions:
                return f"方程 {equation} 无解。"
            
            result_parts = []
            for sol in solutions:
                for v, val in sol.items():
                    result_parts.append(f"{v} = {val}")
            
            return (
                f"📐 方程: {equation}\n"
                f"解: {', '.join(result_parts) if result_parts else '无解'}"
            )
        except Exception as e:
            raise ValueError(f"求解方程失败: {e}")

    @registry.register(
        name="convert_units",
        description="单位换算，支持长度、重量、温度、体积等常见单位转换",
        metadata={"category": "math", "version": "1.0"},
    )
    def convert_units(value: float, from_unit: str, to_unit: str) -> str:
        """
        单位换算。
        
        :param value: 数值。
        :param from_unit: 源单位。
        :param to_unit: 目标单位。
        :returns: 换算结果。
        """
        # 长度单位（基准：米）
        length_units = {
            "m": 1, "meter": 1, "meters": 1, "米": 1,
            "km": 1000, "kilometer": 1000, "千米": 1000, "公里": 1000,
            "cm": 0.01, "centimeter": 0.01, "厘米": 0.01,
            "mm": 0.001, "毫米": 0.001,
            "inch": 0.0254, "in": 0.0254, "英寸": 0.0254,
            "ft": 0.3048, "foot": 0.3048, "feet": 0.3048, "英尺": 0.3048,
            "mile": 1609.344, "英里": 1609.344,
        }
        
        # 重量单位（基准：千克）
        weight_units = {
            "kg": 1, "kilogram": 1, "千克": 1, "公斤": 1,
            "g": 0.001, "gram": 0.001, "克": 0.001,
            "mg": 0.000001, "毫克": 0.000001,
            "lb": 0.453592, "lbs": 0.453592, "pound": 0.453592, "磅": 0.453592,
            "oz": 0.0283495, "ounce": 0.0283495, "盎司": 0.0283495,
            "ton": 1000, "吨": 1000,
        }

        # 温度单位（特殊处理）
        def convert_temperature(v, f, t):
            # 先转摄氏
            f_lower = f.lower()
            if f_lower in ("c", "celsius", "°c", "摄氏度"):
                celsius = v
            elif f_lower in ("f", "fahrenheit", "°f", "华氏度"):
                celsius = (v - 32) * 5 / 9
            elif f_lower in ("k", "kelvin", "开尔文", "开"):
                celsius = v - 273.15
            else:
                raise ValueError(f"不支持的温度单位: {f}")
            
            t_lower = t.lower()
            if t_lower in ("c", "celsius", "°c", "摄氏度"):
                return celsius
            elif t_lower in ("f", "fahrenheit", "°f", "华氏度"):
                return celsius * 9 / 5 + 32
            elif t_lower in ("k", "kelvin", "开尔文", "开"):
                return celsius + 273.15
            else:
                raise ValueError(f"不支持的温度单位: {t}")

        fu = from_unit.lower().strip()
        tu = to_unit.lower().strip()

        # 温度
        if fu in ("c", "f", "k", "celsius", "fahrenheit", "kelvin",
                   "°c", "°f", "摄氏度", "华氏度", "开尔文", "开"):
            result = convert_temperature(value, fu, tu)
            return f"{value} {from_unit} = {result:.2f} {to_unit}"

        # 长度
        if fu in length_units and tu in length_units:
            meters = value * length_units[fu]
            result = meters / length_units[tu]
            return f"{value} {from_unit} = {result:.4f} {to_unit}"

        # 重量
        if fu in weight_units and tu in weight_units:
            kgs = value * weight_units[fu]
            result = kgs / weight_units[tu]
            return f"{value} {from_unit} = {result:.4f} {to_unit}"

        raise ValueError(
            f"不支持的单位转换: {from_unit} → {to_unit}。"
            f"支持长度、重量、温度单位的转换。"
        )
