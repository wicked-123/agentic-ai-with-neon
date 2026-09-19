"""
Router Agent: Top-Level Intent Classifier
Classifies the user's question as either:
  - "chart"      → user wants a visualization (send to chart chain)
  - "data_query" → user wants data/facts (send to SQL + insight chain)

This is the entry point orchestrator before any SQL or chart work happens.
"""

import os
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

                                                                                

class RouterState(TypedDict):
    question: str
    route: str                          

                                                                                 

def classify_intent(state: RouterState) -> RouterState:
    """
    Uses the LLM to decide whether the user wants a chart/visualization
    or just a data answer. Returns 'chart' or 'data_query'.
    """
    prompt = f"""You are an intent classifier for a data analytics assistant.

A user has sent the following question:
\"{state['question']}\"

Your job: decide whether the user's PRIMARY intent is to:
  A) See a CHART / GRAPH / VISUALIZATION (bar chart, line chart, pie chart, trend plot, etc.)
  B) Get a DATA ANSWER / FACT / TABLE (count, list, top N, who, what, when, how many, etc.)

Rules:
- If the question uses words like: chart, graph, plot, visualize, visualization, trend, bar, line, pie, doughnut, show me a chart, draw, display a graph → classify as CHART
- If the question asks for facts, numbers, names, lists, or comparisons WITHOUT mentioning a visual format → classify as DATA_QUERY
- When in doubt (e.g. "show me orders by month") lean toward CHART if any visual word is present, otherwise DATA_QUERY

Respond with ONLY one word — either:
  chart
  data_query

No punctuation, no explanation."""

    response = llm.invoke(prompt)
    raw = response.content.strip().lower()

                                                     
    if "chart" in raw:
        route = "chart"
    else:
        route = "data_query"

    print(f"[RouterAgent] Question: '{state['question']}' -> Route: '{route}'")
    return {"route": route}

                                                                                 

workflow = StateGraph(RouterState)
workflow.add_node("classify_intent", classify_intent)
workflow.add_edge(START, "classify_intent")
workflow.add_edge("classify_intent", END)

                                            
router_graph = workflow.compile()
