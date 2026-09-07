"""LangChain ReAct Agent 组装。"""
import json
import logging
from typing import List, Dict
from pydantic import BaseModel
from langchain_openai import ChatOpenAI
from langchain.agents import AgentExecutor, create_react_agent
from langchain_core.prompts import PromptTemplate

from app.config import settings
from app.agent.tools import sql_query, generate_chart
from app.agent.prompt import REACT_PROMPT_TEMPLATE, BUILTIN_SCHEMA

logger = logging.getLogger(__name__)


class AgentStep(BaseModel):
    type: str      # "thought" | "action" | "observation"
    content: str


class AgentResult(BaseModel):
    answer: str
    steps: List[AgentStep]
    success: bool
    chart_data: dict | None = None
    suggestions: List[str] = []


def _build_llm() -> ChatOpenAI:
    return ChatOpenAI(
        api_key=settings.DEEPSEEK_API_KEY,
        base_url=settings.DEEPSEEK_BASE_URL,
        model="deepseek-chat",
        temperature=0,
    )


def _format_history(history: List[Dict[str, str]]) -> str:
    """将对话历史格式化为 prompt 文本。"""
    if not history:
        return ""
    lines = ["以下是之前的对话历史，你可以参考上下文来理解用户的追问："]
    for msg in history[-10:]:  # 最多 10 条（5 轮）
        role = "用户" if msg["role"] == "user" else "助手"
        lines.append(f"{role}: {msg['content'][:200]}")
    lines.append("---")
    return "\n".join(lines)


def _build_schema(user_tables: List[Dict] = None) -> str:
    """构建完整的表结构描述（内置 + 用户上传）。"""
    parts = [BUILTIN_SCHEMA]
    if user_tables:
        for tbl in user_tables:
            table_name = tbl["table_name"]
            desc = tbl.get("description", "")
            cols = tbl.get("columns", [])
            col_strs = []
            for c in cols:
                col_desc = c.get("description", "")
                col_str = f"{c['column_name']}({c['column_type']})"
                if col_desc:
                    col_str += f" - {col_desc}"
                col_strs.append(col_str)
            line = f"- {table_name}: {', '.join(col_strs)}"
            if desc:
                line += f"  -- {desc}"
            parts.append(line)
    return "\n".join(parts)


def _parse_suggestions(answer: str) -> tuple:
    """从 answer 中提取追问建议，返回 (清理后的 answer, suggestions)。"""
    suggestions = []
    for marker in ["建议追问：", "建议追问:"]:
        if marker in answer:
            idx = answer.index(marker)
            suggestion_text = answer[idx + len(marker):].strip()
            answer = answer[:idx].strip()
            suggestions = [s.strip() for s in suggestion_text.split("｜") if s.strip()]
            if not suggestions:
                suggestions = [s.strip() for s in suggestion_text.split("|") if s.strip()]
            break
    return answer, suggestions


def _parse_intermediate_steps(steps) -> List[AgentStep]:
    """将 LangChain 的 intermediate_steps 解析为前端友好的步骤列表。"""
    result_steps = []
    for action, observation in steps:
        # Thought 部分在 action.log 中
        if action.log and action.log.strip():
            for line in action.log.strip().split("\n"):
                line = line.strip()
                if line.startswith("Thought:"):
                    result_steps.append(AgentStep(
                        type="thought",
                        content=line.replace("Thought:", "").strip()
                    ))
                elif line.startswith("Action:"):
                    result_steps.append(AgentStep(
                        type="action",
                        content=line.replace("Action:", "").strip()
                    ))

        # Action Input
        if action.tool_input:
            result_steps.append(AgentStep(
                type="action",
                content=f"SQL: {action.tool_input}"
            ))

        # Observation
        result_steps.append(AgentStep(
            type="observation",
            content=str(observation)
        ))

    return result_steps


async def run_agent(question: str, history: List[Dict[str, str]] = None, user_tables: List[Dict] = None) -> AgentResult:
    """运行数据分析 Agent。"""
    logger.info(f"Agent 开始处理问题: {question[:100]}{'...' if len(question) > 100 else ''}")
    llm = _build_llm()
    tools = [sql_query, generate_chart]

    prompt = PromptTemplate.from_template(REACT_PROMPT_TEMPLATE)
    history_text = _format_history(history or [])
    schema_text = _build_schema(user_tables)

    agent = create_react_agent(llm, tools, prompt)
    executor = AgentExecutor(
        agent=agent,
        tools=tools,
        max_iterations=5,
        verbose=True,
        handle_parsing_errors=True,
    )

    try:
        result = await executor.ainvoke({"input": question, "history": history_text, "schema": schema_text})
        steps = _parse_intermediate_steps(result.get("intermediate_steps", []))

        # 检测图表数据
        chart_data = None
        for action, observation in result.get("intermediate_steps", []):
            if hasattr(action, 'tool') and action.tool == 'generate_chart':
                try:
                    chart_data = json.loads(observation)
                except (json.JSONDecodeError, TypeError):
                    pass

        raw_answer = result.get("output", "抱歉，我无法回答这个问题。")
        answer, suggestions = _parse_suggestions(raw_answer)

        if "output" in result:
            steps.append(AgentStep(type="thought", content="已得出最终答案"))

        logger.info(f"Agent 处理完成，共执行 {len(steps)} 个步骤")
        return AgentResult(
            answer=answer,
            steps=steps,
            success=True,
            chart_data=chart_data,
            suggestions=suggestions,
        )
    except Exception as e:
        logger.error(f"Agent 执行出错: {e}", exc_info=True)
        return AgentResult(
            answer=f"Agent 执行出错: {str(e)}",
            steps=[],
            success=False,
        )


async def stream_agent(question: str, request, history: List[Dict[str, str]] = None, user_tables: List[Dict] = None):
    """流式运行 Agent，yield SSE 事件。"""
    llm = _build_llm()
    tools = [sql_query, generate_chart]
    prompt = PromptTemplate.from_template(REACT_PROMPT_TEMPLATE)
    history_text = _format_history(history or [])
    schema_text = _build_schema(user_tables)
    agent = create_react_agent(llm, tools, prompt)
    executor = AgentExecutor(
        agent=agent, tools=tools, max_iterations=5,
        verbose=True, handle_parsing_errors=True,
    )

    try:
        async for event in executor.astream_events({"input": question, "history": history_text, "schema": schema_text}, version="v2"):
            if await request.is_disconnected():
                return

            kind = event.get("event", "")
            if kind == "on_chat_model_stream":
                content = event["data"]["chunk"].content
                if content:
                    yield f"event: thought\ndata: {json.dumps({'content': content}, ensure_ascii=False)}\n\n"
            elif kind == "on_tool_start":
                tool_name = event.get("name", "")
                tool_input = event["data"].get("input", {})
                yield f"event: action\ndata: {json.dumps({'content': tool_name, 'input': str(tool_input)}, ensure_ascii=False)}\n\n"
            elif kind == "on_tool_end":
                output = event["data"].get("output", "")
                yield f"event: observation\ndata: {json.dumps({'content': str(output)}, ensure_ascii=False)}\n\n"

        result = await executor.ainvoke({"input": question, "history": history_text, "schema": schema_text})
        raw_answer = result.get("output", "")
        answer, suggestions = _parse_suggestions(raw_answer)
        yield f"event: answer\ndata: {json.dumps({'content': answer, 'suggestions': suggestions}, ensure_ascii=False)}\n\n"
        yield f"event: done\ndata: {json.dumps({'success': True})}\n\n"
    except Exception as e:
        yield f"event: error\ndata: {json.dumps({'content': str(e)})}\n\n"
