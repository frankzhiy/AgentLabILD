"""LangGraph 运行时状态定义

使用 TypedDict + Annotated reducers，与 LangGraph StateGraph 的标准模式一致。
"""

from __future__ import annotations

from typing import Annotated, Any

from typing_extensions import TypedDict

from src.schemas.trace import AgentTrace, MessageTrace


# ── Reducers ────────────────────────────────────────────────

def _merge_dict(existing: dict, update: dict) -> dict:
    """合并字典的 reducer：后来的更新覆盖同 key"""
    merged = {**existing}
    merged.update(update)
    return merged


def _append_list(existing: list, update: list) -> list:
    """追加列表的 reducer"""
    return existing + update


# ── Graph State ─────────────────────────────────────────────

class GraphState(TypedDict, total=False):
    """LangGraph StateGraph 的运行时状态

    各字段通过 Annotated reducer 定义合并策略，支持并行节点的状态更新。
    """

    # 原始病例文本（初始注入，后续只读）
    case_text: str

    # 病例 id（初始注入，后续只读）
    case_id: str

    # 各 agent 的输出：{agent_id: output_content}
    agent_outputs: Annotated[dict[str, Any], _merge_dict]

    # agent 执行追踪列表（追加）
    agent_traces: Annotated[list[AgentTrace], _append_list]

    # 消息传递记录（追加）
    message_traces: Annotated[list[MessageTrace], _append_list]

    # 冲突检测结果（由冲突检测节点写入）
    conflicts: list[dict[str, Any]]

    # 仲裁结果（由仲裁节点写入）
    arbitration_result: dict[str, Any]

    # 最终诊断输出
    final_output: str
