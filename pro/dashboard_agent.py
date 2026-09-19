"""
Agent 2: Business Insight Generator
Takes the output of the SQL Agent and generates a high-level business insight.
"""

import os
from typing import TypedDict
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, START, END

                            
load_dotenv(dotenv_path=os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".env"))

           
llm = ChatOpenAI(
    model="gpt-5-mini",
    temperature=0.7,
    api_key=os.environ.get("OPENAI_API_KEY")
)

                             
class InsightState(TypedDict):
    question: str
    answer: str
    insight: str

                          
def generate_insight(state: InsightState):
    prompt = f"""You are a top-tier business analyst. The user asked a question about our database, and here is the data returned.

Question: {state["question"]}
Data/Answer: {state["answer"]}

Write a 1-2 sentence business insight or quick takeaway from this data that a CEO would find useful. 
Keep it brief, professional, and impactful. Avoid technical jargon.
"""
    response = llm.invoke(prompt)
    return {"insight": response.content.strip()}

                 
workflow = StateGraph(InsightState)
workflow.add_node("generate_insight", generate_insight)
workflow.add_edge(START, "generate_insight")
workflow.add_edge("generate_insight", END)

                                           
insight_graph = workflow.compile()
