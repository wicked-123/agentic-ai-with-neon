"""
Agent for handling and formatting error messages into customer-friendly text.
"""

import os
from typing import TypedDict
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, START, END

                            
load_dotenv(dotenv_path=os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".env"))

           
llm = ChatOpenAI(
    model="gpt-4o-mini",
    temperature=0.3,
    api_key=os.environ.get("OPENAI_API_KEY")
)

                           
class ErrorState(TypedDict):
    error_message: str
    friendly_message: str

                                  
def format_error(state: ErrorState):
    prompt = f"""You are a helpful customer support agent for a data retrieval application. A technical error has occurred. 
Please rewrite the following error message into a polite, user-friendly, and non-technical message that an end user can understand. 
Do not expose technical details, database names, SQL queries, or token rate limits. 
Provide a brief apology and suggest a simple next step if applicable (such as trying again later or simplifying the request).

Raw Error:
{state["error_message"]}
"""
    response = llm.invoke(prompt)
    return {"friendly_message": response.content.strip()}

                 
workflow = StateGraph(ErrorState)
workflow.add_node("format_error", format_error)
workflow.add_edge(START, "format_error")
workflow.add_edge("format_error", END)

                                           
error_graph = workflow.compile()
