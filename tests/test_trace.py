from __future__ import annotations

import json
import sqlite3
import tempfile
from pathlib import Path

import pytest

from app import trace


@pytest.fixture(autouse=True)
def tmp_db(tmp_path):
    """Point trace module at a temporary database for every test."""
    db_path = str(tmp_path / "test.db")
    trace.init_db(db_path)
    yield db_path


class TestInitDb:
    def test_creates_database_file(self, tmp_path):
        db_path = str(tmp_path / "new.db")
        trace.init_db(db_path)
        assert Path(db_path).exists()

    def test_creates_parent_directories(self, tmp_path):
        db_path = str(tmp_path / "sub" / "dir" / "test.db")
        trace.init_db(db_path)
        assert Path(db_path).exists()

    def test_runs_table_exists(self, tmp_db):
        conn = sqlite3.connect(tmp_db)
        cols = [r[1] for r in conn.execute("PRAGMA table_info(runs)")]
        conn.close()
        assert "run_id" in cols
        assert "goal" in cols
        assert "status" in cols
        assert "final_result" in cols
        assert "final_screenshot_path" in cols
        assert "created_at" in cols

    def test_steps_table_exists(self, tmp_db):
        conn = sqlite3.connect(tmp_db)
        cols = [r[1] for r in conn.execute("PRAGMA table_info(steps)")]
        conn.close()
        assert "run_id" in cols
        assert "step_number" in cols
        assert "action_type" in cols
        assert "action_target" in cols
        assert "status" in cols
        assert "error" in cols
        assert "latency_ms" in cols
        assert "screenshot_path" in cols
        assert "page_url" in cols
        assert "page_title" in cols
        assert "evaluation" in cols
        assert "memory_snapshot" in cols
        assert "next_goal" in cols

    def test_idempotent(self, tmp_db):
        trace.init_db(tmp_db)
        trace.init_db(tmp_db)


class TestInsertRun:
    def test_insert_and_get_run(self, tmp_db):
        trace.insert_run("r1", "find the top post", "completed")
        run = trace.get_run("r1")
        assert run is not None
        assert run["run_id"] == "r1"
        assert run["goal"] == "find the top post"
        assert run["status"] == "completed"
        assert run["final_result"] is None
        assert run["final_screenshot_path"] is None
        assert run["created_at"] is not None

    def test_insert_run_with_final_result(self, tmp_db):
        result = {"summary": "done", "url": "https://example.com", "title": "Example", "screenshot_path": "f.png"}
        trace.insert_run("r2", "test", "completed", final_result=result, final_screenshot_path="f.png")
        run = trace.get_run("r2")
        assert json.loads(run["final_result"]) == result
        assert run["final_screenshot_path"] == "f.png"

    def test_get_nonexistent_run(self, tmp_db):
        assert trace.get_run("nope") is None

    def test_update_run_status(self, tmp_db):
        trace.insert_run("r3", "test", "completed")
        trace.update_run_status("r3", "max_steps")
        run = trace.get_run("r3")
        assert run["status"] == "max_steps"

    def test_update_run_final_fields(self, tmp_db):
        trace.insert_run("r4", "test", "completed")
        result = {"summary": "all done"}
        trace.update_run_status("r4", "completed", final_result=result, final_screenshot_path="s.png")
        run = trace.get_run("r4")
        assert json.loads(run["final_result"]) == result
        assert run["final_screenshot_path"] == "s.png"


class TestInsertStep:
    def test_insert_and_get_steps(self, tmp_db):
        trace.insert_run("r1", "test", "completed")
        trace.insert_step("r1", 0, "goto", "https://example.com", "success", None, 150.5, None, "https://example.com", "Example", "navigated", "on example.com", "find link")
        steps = trace.get_steps("r1")
        assert len(steps) == 1
        s = steps[0]
        assert s["run_id"] == "r1"
        assert s["step_number"] == 0
        assert s["action_type"] == "goto"
        assert s["action_target"] == "https://example.com"
        assert s["status"] == "success"
        assert s["error"] is None
        assert s["latency_ms"] == 150.5
        assert s["page_url"] == "https://example.com"
        assert s["page_title"] == "Example"
        assert s["evaluation"] == "navigated"
        assert s["memory_snapshot"] == "on example.com"
        assert s["next_goal"] == "find link"

    def test_multiple_steps_ordered(self, tmp_db):
        trace.insert_run("r1", "test", "completed")
        trace.insert_step("r1", 0, "goto", "https://a.com", "success", None, 100.0, None, "https://a.com", "A", "ok", "", "next")
        trace.insert_step("r1", 1, "click", "#btn", "success", None, 50.0, None, "https://a.com", "A", "clicked", "", "done")
        trace.insert_step("r1", 2, "type", "#input", "success", None, 80.0, None, "https://a.com", "A", "typed", "", "submit")
        steps = trace.get_steps("r1")
        assert len(steps) == 3
        assert [s["step_number"] for s in steps] == [0, 1, 2]

    def test_steps_for_nonexistent_run(self, tmp_db):
        steps = trace.get_steps("nope")
        assert steps == []

    def test_failed_step_records_error(self, tmp_db):
        trace.insert_run("r1", "test", "completed")
        trace.insert_step("r1", 0, "click", "#missing", "failed", "Element not found", 30.0, None, "https://example.com", "Example", "failed", "", "retry")
        steps = trace.get_steps("r1")
        assert steps[0]["status"] == "failed"
        assert steps[0]["error"] == "Element not found"
