"""Research API - start, poll, and import NotebookLM deep/fast research sessions."""

import time
from .rpc.types import RPCMethod
from .core import SyncClientCore


class ResearchAPI:
    def __init__(self, core: SyncClientCore):
        self._core = core

    # ──────────────────────────────────────────
    # FAST RESEARCH
    # ──────────────────────────────────────────

    def start_fast(self, notebook_id: str, query: str, source_ids: list = None) -> str | None:
        """
        Start a Fast Research session.

        Fast Research quickly finds and summarises relevant information
        from the web and/or notebook sources.

        Args:
            query: Research question or topic
            source_ids: Optional list of source IDs to scope research.
                        Defaults to all sources in the notebook.

        Returns:
            research_id (str) to track progress, or None on failure.
        """
        if source_ids is None:
            source_ids = self._core.get_source_ids(notebook_id)

        source_ids_triple = [[[sid]] for sid in source_ids]
        params = [source_ids_triple, query, notebook_id, [2]]
        result = self._core.rpc_call(RPCMethod.START_FAST_RESEARCH, params, f"/notebook/{notebook_id}")

        try:
            return result[0] if isinstance(result, list) else result
        except (IndexError, TypeError):
            return None

    # ──────────────────────────────────────────
    # DEEP RESEARCH
    # ──────────────────────────────────────────

    def start_deep(self, notebook_id: str, query: str, source_ids: list = None) -> str | None:
        """
        Start a Deep Research session.

        Deep Research performs a thorough multi-step investigation of a topic,
        browsing the web and synthesising findings into a comprehensive report.

        Args:
            query: Research question or topic
            source_ids: Optional list of source IDs to scope research.

        Returns:
            research_id (str) to track progress, or None on failure.
        """
        if source_ids is None:
            source_ids = self._core.get_source_ids(notebook_id)

        source_ids_triple = [[[sid]] for sid in source_ids]
        params = [source_ids_triple, query, notebook_id, [2]]
        result = self._core.rpc_call(RPCMethod.START_DEEP_RESEARCH, params, f"/notebook/{notebook_id}")

        try:
            return result[0] if isinstance(result, list) else result
        except (IndexError, TypeError):
            return None

    # ──────────────────────────────────────────
    # POLL STATUS
    # ──────────────────────────────────────────

    def poll(self, notebook_id: str, research_id: str) -> dict:
        """
        Poll the status of an ongoing research session.

        Returns:
            dict with keys:
              - status: "in_progress" | "completed" | "failed" | "unknown"
              - result: raw API result data (available when completed)
        """
        params = [notebook_id, research_id, [2]]
        result = self._core.rpc_call(RPCMethod.POLL_RESEARCH, params, f"/notebook/{notebook_id}")

        status_code = None
        try:
            status_code = result[0][0]
        except (IndexError, TypeError):
            pass

        _STATUS_MAP = {1: "in_progress", 2: "completed", 3: "failed"}
        return {
            "status": _STATUS_MAP.get(status_code, "unknown"),
            "status_code": status_code,
            "result": result,
        }

    # ──────────────────────────────────────────
    # WAIT FOR COMPLETION
    # ──────────────────────────────────────────

    def wait_for_completion(
        self,
        notebook_id: str,
        research_id: str,
        poll_interval: int = 5,
        timeout: int = 600,
    ) -> dict:
        """
        Block and poll until the research session finishes.

        Args:
            poll_interval: Seconds between status checks (default 5)
            timeout: Maximum total wait time in seconds (default 600 = 10 min)

        Returns:
            Final poll result dict with "status" and "result" keys.
        """
        deadline = time.time() + timeout
        while time.time() < deadline:
            status_data = self.poll(notebook_id, research_id)
            if status_data["status"] in ("completed", "failed"):
                return status_data
            time.sleep(poll_interval)
        return {"status": "timeout", "status_code": None, "result": None}

    # ──────────────────────────────────────────
    # IMPORT FINDINGS
    # ──────────────────────────────────────────

    def import_findings(self, notebook_id: str, research_id: str) -> bool:
        """
        Import completed research findings as a new source in the notebook.

        Call this after `wait_for_completion()` returns status="completed".
        """
        params = [notebook_id, research_id, [2]]
        self._core.rpc_call(RPCMethod.IMPORT_RESEARCH, params, f"/notebook/{notebook_id}")
        return True

    # ──────────────────────────────────────────
    # CONVENIENCE: RUN AND IMPORT
    # ──────────────────────────────────────────

    def run_and_import(
        self,
        notebook_id: str,
        query: str,
        deep: bool = False,
        poll_interval: int = 5,
        timeout: int = 600,
        source_ids: list = None,
    ) -> dict:
        """
        One-shot helper: start research, wait, then import findings.

        Args:
            deep: True = Deep Research, False = Fast Research
            poll_interval: Seconds between polls
            timeout: Max wait in seconds

        Returns:
            dict with keys:
              - research_id: str
              - status: "completed" | "failed" | "timeout"
              - imported: bool (True if findings were imported)
        """
        if deep:
            research_id = self.start_deep(notebook_id, query, source_ids)
        else:
            research_id = self.start_fast(notebook_id, query, source_ids)

        if not research_id:
            return {"research_id": None, "status": "failed", "imported": False}

        result = self.wait_for_completion(notebook_id, research_id, poll_interval, timeout)
        imported = False
        if result["status"] == "completed":
            imported = self.import_findings(notebook_id, research_id)

        return {
            "research_id": research_id,
            "status": result["status"],
            "imported": imported,
        }
