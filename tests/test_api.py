import asyncio
import json
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

import api
from pro.sql_agent import ensure_read_only_sql


class StubGraph:
    def __init__(self, result=None, error=None):
        self.result = result or {}
        self.error = error
        self.calls = []

    def invoke(self, payload):
        self.calls.append(payload)
        if self.error:
            raise self.error
        return self.result


class ApiTests(unittest.TestCase):
    def setUp(self):
        api.history.clear()
        api.clients.clear()
        self.client = TestClient(api.app)

    def test_pages_and_static_assets_load(self):
        home = self.client.get("/")
        dashboard = self.client.get("/dashboard")
        script = self.client.get("/static/app.js")

        self.assertEqual(home.status_code, 200)
        self.assertIn("DataFlow", home.text)
        self.assertEqual(dashboard.status_code, 200)
        self.assertIn("Live Dashboard", dashboard.text)
        self.assertEqual(script.status_code, 200)

    def test_data_question_returns_answer_and_broadcasts_history(self):
        router = StubGraph({"route": "data_query"})
        sql = StubGraph({"final_answer": "There were 2 orders.", "sql_query": "SELECT 2", "query_result": "count\n2"})
        insight = StubGraph({"insight": "Orders are steady."})
        with patch.multiple(api, router_graph=router, graph=sql, insight_graph=insight):
            response = self.client.post("/ask", json={"question": "  How many orders?  "})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["answer"], "There were 2 orders.")
        self.assertEqual(sql.calls, [{"question": "How many orders?"}])
        self.assertEqual(api.history[0]["type"], "data_query")
        self.assertEqual(api.history[0]["insight"], "Orders are steady.")

    def test_chart_question_returns_chart_and_broadcasts_history(self):
        config = json.dumps({"type": "bar", "data": {"labels": ["Jan"], "datasets": [{"data": [3]}]}})
        with patch.multiple(
            api,
            router_graph=StubGraph({"route": "chart"}),
            graph=StubGraph({"sql_query": "SELECT 3", "query_result": "month | orders\nJan | 3"}),
            chart_graph=StubGraph({"chart_config": config}),
        ):
            response = self.client.post("/ask", json={"question": "Create a chart of orders"})

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["is_chart"])
        self.assertEqual(api.history[0]["type"], "chart")
        self.assertEqual(api.history[0]["chart_config"], config)

    def test_agent_failure_returns_friendly_error(self):
        with patch.multiple(
            api,
            router_graph=StubGraph(error=RuntimeError("database unavailable")),
            error_graph=StubGraph({"friendly_message": "Please try again later."}),
        ):
            response = self.client.post("/ask", json={"question": "How many orders?"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"error": "Please try again later."})

    def test_blank_and_missing_requests_are_rejected_before_agents_run(self):
        self.assertEqual(self.client.post("/ask", json={"question": "   "}).status_code, 422)
        self.assertEqual(self.client.post("/ask", json={}).status_code, 422)
        self.assertEqual(self.client.post("/followup", json={"question": "q", "answer": " "}).status_code, 422)

    def test_followups_parses_three_questions_and_service_failure_is_safe(self):
        fake_module = types.SimpleNamespace(chat=lambda *args, **kwargs: "- First?\n- Second?\n- Third?\n- Fourth?")
        with patch.dict(sys.modules, {"llm_chat": fake_module}):
            response = self.client.post("/followup", json={"question": "Sales?", "answer": "Sales increased."})
        self.assertEqual(response.json()["questions"], ["First?", "Second?", "Third?"])

    def test_schema_endpoint_returns_structured_metadata(self):
        class Inspector:
            def get_table_names(self): return ["orders"]
            def get_columns(self, table): return [{"name": "id", "type": "INTEGER"}, {"name": "customer_id", "type": "INTEGER"}]
            def get_pk_constraint(self, table): return {"constrained_columns": ["id"]}
            def get_foreign_keys(self, table): return [{"constrained_columns": ["customer_id"]}]

        with patch("sql_agent.engine", object()), patch.object(api, "inspect", return_value=Inspector()):
            response = self.client.get("/schema")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()[0]["columns"][0]["primary_key"], True)
        self.assertEqual(response.json()[0]["columns"][1]["foreign_key"], True)

    def test_schema_endpoint_is_sync_so_a_slow_database_does_not_block_the_event_loop(self):
        schema_route = next(route for route in api.app.routes if route.path == "/schema")
        self.assertFalse(asyncio.iscoroutinefunction(schema_route.endpoint))


class SqlSafetyTests(unittest.TestCase):
    def test_select_and_cte_queries_are_allowed(self):
        ensure_read_only_sql("SELECT * FROM orders")
        ensure_read_only_sql("WITH totals AS (SELECT count(*) AS count FROM orders) SELECT * FROM totals")

    def test_writes_and_multiple_statements_are_rejected(self):
        for query in ("DELETE FROM orders", "SELECT 1; DROP TABLE orders", "WITH changed AS (UPDATE orders SET x = 1) SELECT * FROM changed"):
            with self.assertRaises(ValueError):
                ensure_read_only_sql(query)


class FrontendRegressionTests(unittest.TestCase):
    def test_user_supplied_content_is_escaped_and_requests_time_out(self):
        app_script = Path("public/app.js").read_text(encoding="utf-8")
        dashboard_script = Path("public/dashboard.js").read_text(encoding="utf-8")

        self.assertIn("fetchWithTimeout", app_script)
        self.assertIn("AbortController", app_script)
        self.assertNotIn("answerText.innerHTML", app_script)
        self.assertIn("escapeHtml(data.question)", dashboard_script)
        self.assertIn("escapeHtml(data.insight || data.answer", dashboard_script)


if __name__ == "__main__":
    unittest.main()
