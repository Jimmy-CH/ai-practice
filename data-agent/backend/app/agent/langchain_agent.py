"""LangChain ReAct Agent 组装。"""
from typing import List
from pydantic import BaseModel
from langchain_openai import ChatOpenAI
from langchain.agents import AgentExecutor, create_react_agent
from langchain_core.prompts import PromptTemplate

from app.config import settings
from app.agent.tools import sql_query
from app.agent.prompt import REACT_PROMPT_TEMPLATE


class AgentStep(BaseModel):
    type: str      # "thought" | "action" | "observation"
    content: str


class AgentResult(BaseModel):
    answer: str
    steps: List[AgentStep]
    success: bool


def _build_llm() -> ChatOpenAI:
    return ChatOpenAI(
        api_key=settings.DEEPSEEK_API_KEY,
        base_url=settings.DEEPSEEK_BASE_URL,
        model="deepseek-chat",
        temperature=0,
    )


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


async def run_agent(question: str) -> AgentResult:
    """运行数据分析 Agent。"""
    llm = _build_llm()
    tools = [sql_query]

    prompt = PromptTemplate.from_template(REACT_PROMPT_TEMPLATE)

    agent = create_react_agent(llm, tools, prompt)
    executor = AgentExecutor(
        agent=agent,
        tools=tools,
        max_iterations=5,
        verbose=True,
        handle_parsing_errors=True,
    )

    try:
        result = await executor.ainvoke({"input": question})
        steps = _parse_intermediate_steps(result.get("intermediate_steps", []))

        # 添加最终 Thought
        if "output" in result:
            steps.append(AgentStep(type="thought", content="已得出最终答案"))

        return AgentResult(
            answer=result.get("output", "抱歉，我无法回答这个问题。"),
            steps=steps,
            success=True,
        )
    except Exception as e:
        return AgentResult(
            answer=f"Agent 执行出错: {str(e)}",
            steps=[],
            success=False,
        )
