"""Chat API - ask questions and retrieve conversation history from a notebook."""

import json
import urllib.parse
from .rpc.types import QUERY_URL, RPCMethod
from .core import SyncClientCore


class ChatAPI:
    def __init__(self, core: SyncClientCore):
        self._core = core

    def ask(self, notebook_id: str, question: str, source_ids: list = None) -> str:
        """
        Ask a question in a notebook and get the AI answer.

        Args:
            notebook_id: The notebook to query
            question: Your question
            source_ids: Optional list of specific source IDs to scope the answer.
                        Defaults to all sources in the notebook.

        Returns:
            The answer text as a string.
        """
        if source_ids is None:
            source_ids = self._core.get_source_ids(notebook_id)

        sources_array = [[[sid]] for sid in source_ids]
        params = [
            sources_array,
            question,
            None,
            [2, None, [1], [1]],
            None,
            None,
            None,
            notebook_id,
            1,
        ]

        params_json = json.dumps(params, separators=(",", ":"))
        f_req_json = json.dumps([None, params_json], separators=(",", ":"))
        encoded_req = urllib.parse.quote(f_req_json, safe="")
        encoded_at = urllib.parse.quote(self._core.csrf_token, safe="")
        body = f"f.req={encoded_req}&at={encoded_at}&"

        self._core._reqid_counter += 100000
        url_params = {
            "bl": "boq_labs-tailwind-frontend_20260301.03_p0",
            "hl": "en",
            "_reqid": str(self._core._reqid_counter),
            "rt": "c",
            "f.sid": self._core.session_id,
        }

        url = f"{QUERY_URL}?{urllib.parse.urlencode(url_params)}"
        headers = {"Content-Type": "application/x-www-form-urlencoded;charset=UTF-8"}

        res = self._core.session.post(url, data=body, headers=headers)
        res.raise_for_status()

        # Parse the streamed response — pick the longest wrb.fr answer
        text = res.text
        if text.startswith(")]}'"):
            text = text[4:]

        best_answer = ""
        for line in text.split("\n"):
            if "wrb.fr" in line:
                try:
                    data = json.loads(line)
                    for item in data:
                        if isinstance(item, list) and len(item) > 2 and item[0] == "wrb.fr":
                            inner = json.loads(item[2])
                            answer_text = inner[0][0]
                            if answer_text and len(answer_text) > len(best_answer):
                                best_answer = answer_text
                except Exception:
                    continue

        return best_answer

    def get_last_conversation_id(self, notebook_id: str) -> str | None:
        """Get the ID of the most recent conversation in this notebook."""
        params = [notebook_id, [2]]
        result = self._core.rpc_call(RPCMethod.GET_LAST_CONVERSATION_ID, params, f"/notebook/{notebook_id}")
        try:
            return result[0] if isinstance(result, list) else result
        except (IndexError, TypeError):
            return None

    def get_conversation_turns(self, notebook_id: str, conversation_id: str) -> list[dict]:
        """
        Retrieve the full Q&A history for a specific conversation.

        Returns:
            List of dicts with keys: "question" and "answer"
        """
        params = [notebook_id, conversation_id, [2]]
        result = self._core.rpc_call(RPCMethod.GET_CONVERSATION_TURNS, params, f"/notebook/{notebook_id}")

        turns = []
        try:
            for turn in result[0]:
                q = turn[0][0] if turn[0] else ""
                a = turn[1][0] if len(turn) > 1 and turn[1] else ""
                turns.append({"question": q, "answer": a})
        except (IndexError, TypeError):
            pass
        return turns

    def get_history(self, notebook_id: str) -> list[dict]:
        """
        Convenience method — get the full conversation history for the most recent conversation.

        Returns:
            List of dicts with keys: "question" and "answer"
        """
        conversation_id = self.get_last_conversation_id(notebook_id)
        if not conversation_id:
            return []
        return self.get_conversation_turns(notebook_id, conversation_id)