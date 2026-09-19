"""
Agent 3: Chart Generator
Detects if the user wants a chart, determines the chart type,
and structures query results into Chart.js-compatible JSON.
"""

import os
import json
from typing import TypedDict
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, START, END

                            
load_dotenv(dotenv_path=os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".env"))

           
llm = ChatOpenAI(
    model="gpt-4o-mini",
    temperature=0,
    api_key=os.environ.get("OPENAI_API_KEY")
)


                           
class ChartState(TypedDict):
    question: str
    query_result: str
    chart_config: str                                                             


                               
def generate_chart(state: ChartState):
    prompt = f"""You are a data visualization expert. Analyze the user's question and the query result to determine if a chart should be generated.

User's Question: {state["question"]}

Query Result (table format):
{state["query_result"]}

Rules:
1. If the question mentions or implies a chart, graph, plot, trend, visualization, comparison, or "vs" — generate a chart config.
2. If the question is purely informational (e.g., "who had the most orders?") — return ONLY the word "none".
3. Pick the most appropriate chart type: "line", "bar", "pie", or "doughnut".
4. If the user explicitly mentions a chart type (e.g., "bar chart", "line chart"), use that type.

If a chart IS appropriate, respond with ONLY valid JSON in this exact format (no markdown, no explanation):
{{
  "type": "line",
  "data": {{
    "labels": ["Jan", "Feb", "Mar"],
    "datasets": [
      {{
        "label": "Orders",
        "data": [10, 20, 30]
      }}
    ]
  }}
}}

Important:
- labels should be the x-axis categories (strings)
- data should be numeric values
- You can have multiple datasets if the query has multiple series
- Parse the actual numbers from the query result, don't make up data
- If no chart is needed, respond with ONLY the word "none"
"""
    response = llm.invoke(prompt)
    content = response.content.strip()

                                 
    if content.lower() == "none":
        return {"chart_config": ""}

                                          
    try:
                                               
        if content.startswith("```"):
            content = content.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        parsed = json.loads(content)
        return {"chart_config": json.dumps(parsed)}
    except json.JSONDecodeError:
        print(f"Chart agent returned invalid JSON: {content}")
        return {"chart_config": ""}


                 
workflow = StateGraph(ChartState)
workflow.add_node("generate_chart", generate_chart)
workflow.add_edge(START, "generate_chart")
workflow.add_edge("generate_chart", END)

                                           
chart_graph = workflow.compile()
