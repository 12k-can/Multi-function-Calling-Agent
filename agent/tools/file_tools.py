"""
📄 文件生成工具

提供文件创建、内容生成等能力。
支持多种格式：文本、JSON、HTML、Markdown、CSV 等。
"""

import os
import json
import csv
import io
from datetime import datetime
from pathlib import Path


def register_file_tools(registry, workspace_dir: str = ".") -> None:
    """
    注册文件操作工具。
    
    Args:
        registry: ToolRegistry 实例。
        workspace_dir: 文件生成的工作目录。
    """

    @registry.register(
        name="create_text_file",
        description="创建一个文本文件，支持 .txt, .md, .json, .html, .csv, .py, .yaml, .xml 等格式",
        metadata={"category": "file", "version": "1.0"},
    )
    def create_text_file(
        filename: str,
        content: str,
        directory: str = "",
        overwrite: bool = False,
    ) -> str:
        """
        创建文本文件。
        
        :param filename: 文件名（含扩展名）。
        :param content: 文件内容。
        :param directory: 子目录（可选，相对于工作目录）。
        :param overwrite: 是否覆盖已存在的文件，默认 False。
        :returns: 文件创建结果。
        """
        # 安全检查：防止路径穿越
        safe_name = Path(filename).name
        if directory:
            safe_dir = Path(directory).resolve()
            base_dir = Path(workspace_dir).resolve()
            # 确保目录在 work_dir 下
            full_dir = base_dir / safe_dir.relative_to(safe_dir.anchor) if safe_dir.is_absolute() else base_dir / safe_dir
            full_dir.mkdir(parents=True, exist_ok=True)
        else:
            full_dir = Path(workspace_dir)

        file_path = full_dir / safe_name

        if file_path.exists() and not overwrite:
            return (
                f"⚠️ 文件已存在: {file_path}\n"
                f"如需覆盖，请设置 overwrite=True。"
            )

        file_path.write_text(content, encoding="utf-8")

        return (
            f"✅ 文件创建成功\n"
            f"━━━━━━━━━━━━━━━\n"
            f"📁 路径: {file_path}\n"
            f"📝 大小: {len(content)} 字符\n"
            f"🕐 时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )

    @registry.register(
        name="generate_report",
        description="生成结构化的数据报告（Markdown 格式），支持表格、列表等",
        metadata={"category": "file", "version": "1.0"},
    )
    def generate_report(
        title: str,
        data_json: str,
        description: str = "",
        filename: str = "",
    ) -> str:
        """
        生成结构化报告。
        
        :param title: 报告标题。
        :param data_json: 数据的 JSON 字符串，将自动格式化为表格。
        :param description: 报告描述（可选）。
        :param filename: 输出文件名（可选，默认自动生成）。
        :returns: 报告文件路径和摘要。
        """
        try:
            data = json.loads(data_json)
        except json.JSONDecodeError:
            # 尝试修复常见问题：如果是以 { 开头但不是数组，尝试加 []
            try:
                data = json.loads("[" + data_json + "]")
            except json.JSONDecodeError as e:
                raise ValueError(
                    f"数据格式错误（需要有效 JSON）: {e}\n"
                    f"请使用 JSON 数组格式，如："
                    f'[{{"name": "张三", "dept": "技术部"}}]'
                )

        if not filename:
            safe_title = "".join(c for c in title if c.isalnum() or c in " _-")
            filename = f"report_{safe_title}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"

        file_path = Path(workspace_dir) / filename

        # 构建 Markdown 报告
        lines = [
            f"# {title}",
            "",
            f"> 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
        ]
        if description:
            lines.append(f"{description}")
            lines.append("")

        # 处理不同数据结构
        if isinstance(data, list) and all(isinstance(item, dict) for item in data):
            # 列表字典 → 表格
            if data:
                headers = list(data[0].keys())
                lines.append("## 数据表格")
                lines.append("")
                # 表头
                header_row = "| " + " | ".join(headers) + " |"
                sep_row = "| " + " | ".join(["---"] * len(headers)) + " |"
                lines.append(header_row)
                lines.append(sep_row)
                # 每行
                for item in data:
                    row = "| " + " | ".join(str(item.get(h, "")) for h in headers) + " |"
                    lines.append(row)
                lines.append("")
        elif isinstance(data, dict):
            lines.append("## 数据摘要")
            lines.append("")
            for key, value in data.items():
                if isinstance(value, (list, dict)):
                    val_str = json.dumps(value, ensure_ascii=False, indent=2)
                    lines.append(f"- **{key}**:\n```\n{val_str}\n```")
                else:
                    lines.append(f"- **{key}**: {value}")
            lines.append("")
        else:
            lines.append(f"```json\n{json.dumps(data, ensure_ascii=False, indent=2)}\n```")
            lines.append("")

        lines.append("---")
        lines.append(f"*由 AI Agent 自动生成*")

        content = "\n".join(lines)
        file_path.write_text(content, encoding="utf-8")

        return (
            f"📊 报告生成成功\n"
            f"━━━━━━━━━━━━━━━\n"
            f"📁 文件: {file_path}\n"
            f"📝 标题: {title}\n"
            f"📄 格式: Markdown\n"
            f"📏 大小: {len(content)} 字符\n"
            f"━━━━━━━━━━━━━━━\n"
            f"内容预览:\n{content[:500]}{'...' if len(content) > 500 else ''}"
        )

    @registry.register(
        name="generate_csv",
        description="根据 JSON 数据生成 CSV 文件",
        metadata={"category": "file", "version": "1.0"},
    )
    def generate_csv(
        data_json: str,
        filename: str = "",
        delimiter: str = ",",
    ) -> str:
        """
        生成 CSV 文件。
        
        :param data_json: JSON 数组字符串，每个元素为一行数据。
        :param filename: 输出文件名（可选）。
        :param delimiter: 分隔符，默认为逗号。
        :returns: CSV 文件路径和摘要。
        """
        try:
            data = json.loads(data_json)
        except json.JSONDecodeError as e:
            raise ValueError(f"数据格式错误: {e}")

        if not isinstance(data, list) or not data:
            raise ValueError("数据必须是非空 JSON 数组。")

        if not filename:
            filename = f"data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

        file_path = Path(workspace_dir) / filename

        # 确定列名
        if isinstance(data[0], dict):
            fieldnames = list(data[0].keys())
        else:
            fieldnames = [f"col_{i}" for i in range(len(data[0]))] if isinstance(data[0], (list, tuple)) else ["value"]

        with open(file_path, "w", newline="", encoding="utf-8") as f:
            if isinstance(data[0], dict):
                writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=delimiter)
                writer.writeheader()
                writer.writerows(data)
            else:
                writer = csv.writer(f, delimiter=delimiter)
                for row in data:
                    if isinstance(row, (list, tuple)):
                        writer.writerow(row)
                    else:
                        writer.writerow([row])

        return (
            f"📊 CSV 文件生成成功\n"
            f"━━━━━━━━━━━━━━━\n"
            f"📁 文件: {file_path}\n"
            f"📏 {len(data)} 行 × {len(fieldnames)} 列\n"
            f"🔧 分隔符: '{delimiter}'"
        )
