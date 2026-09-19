import os
import sys
import json
import asyncio
import re

# Set dummy API key to prevent ChatOpenAI from crashing on import if missing
os.environ.setdefault("OPENAI_API_KEY", "dummy_key_to_prevent_crash")

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import inspect

# Add pro folder to path
sys.path.append(os.path.join(os.path.dirname(__file__), "pro"))
from sql_agent import graph
from dashboard_agent import insight_graph
from chart_agent import chart_graph
from router_agent import router_graph
from error_agent import error_graph

app = FastAPI(title="viggy's data retrieval AI")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
public_dir = os.path.join(BASE_DIR, "public")
if os.path.exists(public_dir):
    app.mount("/static", StaticFiles(directory=public_dir), name="static")

class QueryRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2_000)

    @field_validator("question")
    @classmethod
    def question_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Question must contain non-whitespace characters.")
        return value

class FollowupRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2_000)
    answer: str = Field(min_length=1, max_length=10_000)

    @field_validator("question", "answer")
    @classmethod
    def text_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Text must contain non-whitespace characters.")
        return value

@app.post("/followup")
async def get_followups(req: FollowupRequest):
    try:
        question = req.question
        answer = req.answer
        from llm_chat import chat
        prompt = f"""Based on the user's question and the retrieved data answer, suggest 3 short, insightful follow-up questions the user could ask next to dig deeper.
        
Question: {question}
Answer: {answer}

Return exactly 3 questions, one per line, starting with a dash (-).
"""
        response_text = chat(prompt, system_prompt="You are a helpful data analyst.", temperature=0.7)
        content = response_text.strip().split('\n')
        questions = [q.strip('- ').strip() for q in content if q.strip('- ').strip() and len(q) > 5]
        return {"questions": questions[:3]}
    except Exception as e:
        return {"questions": []}

# Global list of connected dashboard clients
clients = []

# In-memory history of all broadcast messages so the dashboard can load past results
history = []

@app.get("/")
def read_index():
    return FileResponse(os.path.join(BASE_DIR, "public", "index.html"))

@app.get("/dashboard")
def read_dashboard():
    return FileResponse(os.path.join(BASE_DIR, "public", "dashboard.html"))

@app.post("/ask")
async def ask_question(req: QueryRequest):
    try:
        question = req.question
        # ── Step 1: Route classification ──────────────────────────────────────
        router_result = router_graph.invoke({"question": question})
        route = router_result.get("route", "data_query")

        # ── Step 2A: CHART chain ──────────────────────────────────────────────
        if route == "chart":
            # Run SQL to get data
            sql_result = graph.invoke({"question": question})
            query_result = sql_result.get("query_result", "")

            # Run Chart Agent to build Chart.js config
            chart_result = chart_graph.invoke({
                "question": question,
                "query_result": query_result
            })
            chart_config = chart_result.get("chart_config", "")

            # Broadcast chart to all connected dashboard clients via SSE
            payload = {
                "question": question,
                "answer": "",
                "insight": "",
                "chart_config": chart_config,
                "type": "chart"
            }
            message = json.dumps(payload)
            history.append(payload)
            for client_queue in clients:
                await client_queue.put(message)

            # Return minimal response — tell the frontend it's on the dashboard
            return {
                "answer": "📊 Chart is created on the dashboard!",
                "sql_query": sql_result.get("sql_query", ""),
                "raw_result": "",
                "chart_config": chart_config,
                "is_chart": True
            }

        # ── Step 2B: DATA QUERY chain ─────────────────────────────────────────
        else:
            # Run SQL Agent
            sql_result = graph.invoke({"question": question})
            answer = sql_result.get("final_answer", "")
            query_result = sql_result.get("query_result", "")

            # Run Insight Agent
            insight_result = insight_graph.invoke({
                "question": question,
                "answer": answer
            })
            insight = insight_result.get("insight", "")

            # Broadcast insight to dashboard
            payload = {
                "question": question,
                "answer": answer,
                "insight": insight,
                "chart_config": "",
                "raw_result": query_result,
                "type": "data_query"
            }
            message = json.dumps(payload)
            history.append(payload)
            for client_queue in clients:
                await client_queue.put(message)

            # Return full answer to main page
            return {
                "answer": answer,
                "sql_query": sql_result.get("sql_query", ""),
                "raw_result": query_result,
                "chart_config": "",
                "is_chart": False
            }

    except Exception as e:
        try:
            error_result = error_graph.invoke({"error_message": str(e)})
            friendly_msg = error_result.get("friendly_message", "An unexpected error occurred. Please try again later.")
            return {"error": friendly_msg}
        except Exception:
            return {"error": "We're experiencing technical difficulties and cannot process your request right now. Please try again later."}

@app.get("/history")
async def get_history():
    """Return all past broadcast messages so the dashboard can hydrate on load"""
    return history

_cached_schema = None

@app.get("/schema")
def get_schema():
    """Returns the database schema as a structured JSON object."""
    global _cached_schema
    if _cached_schema is not None:
        return _cached_schema
        
    try:
        from sql_agent import engine
        inspector = inspect(engine)
        schema_data = []
        for table_name in inspector.get_table_names():
            columns = []
            
            # Fetch constraints once per table
            pk_cols = inspector.get_pk_constraint(table_name).get("constrained_columns", [])
            fk_cols = []
            for fk in inspector.get_foreign_keys(table_name):
                fk_cols.extend(fk.get("constrained_columns", []))
                
            for col in inspector.get_columns(table_name):
                columns.append({
                    "name": col["name"],
                    "type": str(col["type"]),
                    "primary_key": col["name"] in pk_cols,
                    "foreign_key": col["name"] in fk_cols
                })
            schema_data.append({
                "table": table_name,
                "columns": columns
            })
            
        _cached_schema = schema_data
        return schema_data
    except Exception as e:
        try:
            error_result = error_graph.invoke({"error_message": str(e)})
            friendly_msg = error_result.get("friendly_message", "An unexpected error occurred. Please try again later.")
            return {"error": friendly_msg}
        except Exception:
            return {"error": "We're experiencing technical difficulties. Please try again later."}

@app.get("/stream")
async def stream_insights(request: Request):
    """SSE Endpoint for the live dashboard"""
    client_queue = asyncio.Queue()
    clients.append(client_queue)

    async def event_generator():
        try:
            while True:
                if await request.is_disconnected():
                    break
                message = await client_queue.get()
                yield f"data: {message}\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            if client_queue in clients:
                clients.remove(client_queue)

    return StreamingResponse(event_generator(), media_type="text/event-stream")
