"""
🗄 数据库查询工具

提供 SQLite 数据库查询能力。演示用，可替换为真实数据库连接。
支持创建表、插入数据、查询数据等操作。
"""

import sqlite3
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional


def register_database_tools(registry, db_path: str = "") -> None:
    # 默认使用临时文件数据库
    if not db_path:
        import tempfile
        db_path = os.path.join(tempfile.gettempdir(), "agent_demo.db")
    """
    注册数据库操作工具。
    
    Args:
        registry: ToolRegistry 实例。
        db_path: SQLite 数据库文件路径，默认内存数据库。
    """

    @registry.register(
        name="execute_sql",
        description="执行 SQL 查询语句（SELECT），返回查询结果表格。数据库为 SQLite，包含示例表。注意：只允许 SELECT 查询",
        metadata={"category": "database", "version": "1.0"},
    )
    def execute_sql(query: str) -> str:
        """
        执行 SQL 查询。
        
        :param query: SQL SELECT 查询语句。
        :returns: 查询结果（表格形式）。
        """
        query_upper = query.strip().upper()
        if not query_upper.startswith("SELECT") and not query_upper.startswith("WITH"):
            raise ValueError("出于安全考虑，只允许执行 SELECT 查询。")

        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        try:
            cursor = conn.execute(query)
            rows = cursor.fetchall()
            description = cursor.description

            if not rows:
                return "查询完成，结果为空（0 行）。"

            columns = [desc[0] for desc in description]
            
            # 格式化为表格
            col_widths = [
                max(len(str(col)), max(len(str(row[col])) for row in rows))
                for col in columns
            ]

            lines = [
                f"📊 查询结果 ({len(rows)} 行)",
                "━" * (sum(col_widths) + len(columns) * 3 + 1),
            ]

            # 表头
            header = "│ " + " │ ".join(
                str(col).ljust(col_widths[i]) for i, col in enumerate(columns)
            ) + " │"
            lines.append(header)
            lines.append("├" + "┼".join("─" * (w + 2) for w in col_widths) + "┤")

            # 数据行
            for row in rows:
                line = "│ " + " │ ".join(
                    str(row[col]).ljust(col_widths[i]) for i, col in enumerate(columns)
                ) + " │"
                lines.append(line)

            lines.append("━" * (sum(col_widths) + len(columns) * 3 + 1))
            lines.append(f"共 {len(rows)} 行记录")

            return "\n".join(lines)

        except sqlite3.Error as e:
            raise ValueError(f"SQL 执行错误: {e}")
        finally:
            conn.close()

    @registry.register(
        name="show_tables",
        description="显示数据库中的所有表和表结构信息",
        metadata={"category": "database", "version": "1.0"},
    )
    def show_tables() -> str:
        """
        显示数据库中所有表及其结构。
        
        :returns: 数据库结构信息。
        """
        conn = sqlite3.connect(db_path)
        try:
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            )
            tables = [row[0] for row in cursor.fetchall()]

            if not tables:
                return "数据库为空，没有任何表。"

            lines = ["🗄 数据库结构", "=" * 40, ""]
            for table in tables:
                cursor = conn.execute(f"PRAGMA table_info('{table}')")
                columns = cursor.fetchall()
                lines.append(f"📋 表: {table}")
                lines.append(f"  列数: {len(columns)}")
                lines.append(f"  {'名称':<15} {'类型':<10} {'非空':<6} {'主键'}")
                lines.append(f"  {'─'*15} {'─'*10} {'─'*6} {'─'*4}")
                for col in columns:
                    cid, name, ctype, notnull, default, pk = col
                    lines.append(
                        f"  {name:<15} {ctype:<10} {'✅' if notnull else '❌':<6} {'🔑' if pk else ''}"
                    )
                lines.append("")

            # 行数统计
            lines.append("=" * 40)
            for table in tables:
                cursor = conn.execute(f"SELECT COUNT(*) FROM '{table}'")
                count = cursor.fetchone()[0]
                lines.append(f"  {table}: {count} 行")

            return "\n".join(lines)
        except sqlite3.Error as e:
            raise ValueError(f"获取表结构错误: {e}")
        finally:
            conn.close()

    @registry.register(
        name="create_sample_data",
        description="在数据库中创建示例表和数据（如员工表、产品表、订单表等）用于演示查询",
        metadata={"category": "database", "version": "1.0"},
    )
    def create_sample_data() -> str:
        """
        创建示例表和数据。
        
        :returns: 创建结果。
        """
        conn = sqlite3.connect(db_path)
        try:
            # 先清理旧数据，确保示例数据是最新的
            conn.executescript("""
                DROP TABLE IF EXISTS employees;
                DROP TABLE IF EXISTS products;

                CREATE TABLE employees (
                    id INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    department TEXT,
                    position TEXT,
                    salary REAL,
                    hire_date TEXT
                );

                INSERT INTO employees VALUES
                    (1, '张三', '技术部', '高级工程师', 25000, '2020-03-15'),
                    (2, '李四', '市场部', '市场总监', 30000, '2019-06-01'),
                    (3, '王五', '技术部', '架构师', 35000, '2018-01-10'),
                    (4, '赵六', '产品部', '产品经理', 22000, '2021-09-20'),
                    (5, '孙七', '人事部', 'HR经理', 18000, '2020-12-01'),
                    (6, '周八', '技术部', '前端工程师', 20000, '2022-04-15'),
                    (7, '吴九', '市场部', '市场专员', 15000, '2023-01-05'),
                    (8, '郑十', '财务部', '财务经理', 23000, '2019-08-20');

                CREATE TABLE products (
                    id INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    category TEXT,
                    price REAL,
                    stock INTEGER,
                    description TEXT
                );

                INSERT INTO products VALUES
                    (1, '智能笔记本', '电子产品', 5999, 120, '高性能轻薄本，16GB内存'),
                    (2, '无线耳机', '电子产品', 1299, 300, '主动降噪，续航30小时'),
                    (3, '机械键盘', '外设', 899, 200, 'Cherry轴，RGB背光'),
                    (4, '办公座椅', '家具', 2499, 50, '人体工学设计，透气网布'),
                    (5, '显示器', '电子产品', 3499, 80, '27寸4K，IPS面板'),
                    (6, '鼠标', '外设', 599, 500, '无线静音，人体工学');
            """)

            conn.commit()
            return (
                "✅ 示例数据创建成功\n"
                "━━━━━━━━━━━━━━━━━\n"
                "📋 employees（员工表）— 8 条记录\n"
                "  字段: id, name, department, position, salary, hire_date\n\n"
                "📋 products（产品表）— 6 条记录\n"
                "  字段: id, name, category, price, stock, description\n\n"
                "💡 试试查询：\n"
                "  SELECT * FROM employees;\n"
                "  SELECT department, COUNT(*) FROM employees GROUP BY department;\n"
                "  SELECT * FROM products WHERE price < 3000 ORDER BY price;"
            )
        except sqlite3.Error as e:
            raise ValueError(f"创建示例数据失败: {e}")
        finally:
            conn.close()
