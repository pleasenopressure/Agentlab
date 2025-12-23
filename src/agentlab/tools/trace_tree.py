#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
trace_tree.py
从 OpenTelemetry JSONL（每行一个 span）里抽取某个 trace_id，
并以树状结构打印（带耗时ms、step/tool聚合信息）。

用法示例：
  python tools/trace_tree.py --trace-id de0c8dbe3bfd5f5c9e96fb56df6d328d
  python tools/trace_tree.py --trace-id ... --file logs/traces.jsonl
"""

from __future__ import annotations

import argparse
import json
import os
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class Span:
    name: str
    trace_id: str
    span_id: str
    parent_span_id: Optional[str]
    start_ns: int
    end_ns: int
    status: str
    attributes: Dict[str, Any] = field(default_factory=dict)

    @property
    def dur_ms(self) -> float:
        if self.end_ns and self.start_ns and self.end_ns >= self.start_ns:
            return (self.end_ns - self.start_ns) / 1_000_000.0
        return 0.0


def _safe_int(v: Any, default: int = 0) -> int:
    try:
        return int(v)
    except Exception:
        return default


def load_spans(jsonl_path: str, trace_id: str) -> List[Span]:
    spans: List[Span] = []
    with open(jsonl_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except Exception:
                continue

            if obj.get("trace_id") != trace_id:
                continue

            spans.append(
                Span(
                    name=str(obj.get("name", "")),
                    trace_id=str(obj.get("trace_id", "")),
                    span_id=str(obj.get("span_id", "")),
                    parent_span_id=obj.get("parent_span_id"),
                    start_ns=_safe_int(obj.get("start_time_ns", 0)),
                    end_ns=_safe_int(obj.get("end_time_ns", 0)),
                    status=str(obj.get("status", "")),
                    attributes=obj.get("attributes") or {},
                )
            )
    return spans


def build_tree(spans: List[Span]) -> Tuple[List[Span], Dict[str, List[Span]]]:
    by_id: Dict[str, Span] = {s.span_id: s for s in spans if s.span_id}
    children: Dict[str, List[Span]] = {}

    roots: List[Span] = []
    for s in spans:
        pid = s.parent_span_id
        if pid and pid in by_id:
            children.setdefault(pid, []).append(s)
        else:
            roots.append(s)

    # sort children by start_time
    for pid, ch in children.items():
        ch.sort(key=lambda x: (x.start_ns, x.end_ns))

    # also sort roots by start_time
    roots.sort(key=lambda x: (x.start_ns, x.end_ns))
    return roots, children


def pretty_label(s: Span) -> str:
    attrs = s.attributes or {}

    # 1) react.step -> 显示 step #
    if s.name == "react.step":
        step = attrs.get("step")
        if step is not None:
            return f"react.step#{step}"
        return "react.step"

    # 2) tool.run -> 显示 tool 名称
    if s.name == "tool.run":
        tool = attrs.get("tool.name") or attrs.get("tool") or attrs.get("name")
        if tool:
            return f"tool.run {tool}"
        return "tool.run"

    # 3) HTTP spans（有些库会写成 "POST /.../react_chat"）
    # 你的 trace 里有 "POST /session/{session_id}/react_chat"
    m = re.match(r"^(GET|POST|PUT|PATCH|DELETE)\s+(.+)$", s.name)
    if m:
        method, rest = m.group(1), m.group(2)
        route = attrs.get("http.route") or attrs.get("http.target") or ""
        if route:
            return f"HTTP {method} {route}"
        return f"HTTP {method} {rest}"

    # 4) agent.run -> 带 kind
    if s.name == "agent.run":
        kind = attrs.get("kind")
        if kind:
            return f"agent.run ({kind})"
        return "agent.run"

    return s.name


def format_status(s: Span) -> str:
    st = s.status or ""
    if "ERROR" in st:
        return " [ERROR]"
    return ""


def print_tree(roots: List[Span], children: Dict[str, List[Span]], show_ids: bool = False) -> None:
    def _walk(node: Span, indent: str = "") -> None:
        label = pretty_label(node)
        ids = f"  (span={node.span_id}, parent={node.parent_span_id})" if show_ids else ""
        print(f"{indent}- {label} ({node.dur_ms:.1f} ms){format_status(node)}{ids}")

        for ch in children.get(node.span_id, []):
            _walk(ch, indent + "  ")

    for r in roots:
        _walk(r, "")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--trace-id", required=True, help="要查看的 trace_id（从 SSE 输出里复制）")
    ap.add_argument("--file", default=os.path.join("logs", "traces.jsonl"), help="traces.jsonl 路径")
    ap.add_argument("--show-ids", action="store_true", help="显示 span_id/parent_span_id 方便精确对照")
    args = ap.parse_args()

    spans = load_spans(args.file, args.trace_id)
    if not spans:
        print(f"未找到 trace_id={args.trace_id} 的 spans。请确认文件路径和 trace_id 是否正确。")
        return

    roots, children = build_tree(spans)
    print(f"trace_id={args.trace_id}  spans={len(spans)}  roots={len(roots)}")
    print_tree(roots, children, show_ids=args.show_ids)


if __name__ == "__main__":
    main()
