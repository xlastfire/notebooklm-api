"""Notebooks API - full CRUD + configuration for NotebookLM notebooks."""

from .rpc.types import (
    RPCMethod,
    ChatGoal,
    ChatResponseLength,
    SharePermission,
    ShareAccess,
    ShareViewLevel,
)
from .core import SyncClientCore


class NotebooksAPI:
    def __init__(self, core: SyncClientCore):
        self._core = core

    def list(self) -> list[dict]:
        """List all notebooks in the account."""
        params = [None, 1, None, [2]]
        result = self._core.rpc_call(RPCMethod.LIST_NOTEBOOKS, params)

        notebooks = []
        if result and isinstance(result, list) and len(result) > 0:
            raw_nbs = result[0] if isinstance(result[0], list) else result
            for nb in raw_nbs:
                if len(nb) > 2:
                    title = nb[0].replace("thought\n", "").strip() if isinstance(nb[0], str) else ""
                    notebooks.append({"id": nb[2], "title": title})
        return notebooks

    def create(self, title: str) -> dict:
        """Create a new notebook and return its ID and title."""
        params = [title, None, None, [2], [1]]
        result = self._core.rpc_call(RPCMethod.CREATE_NOTEBOOK, params)
        nb_id = result[2] if len(result) > 2 else ""
        return {"id": nb_id, "title": title}

    def get(self, notebook_id: str) -> dict:
        """Get full details for a notebook including its sources."""
        params = [notebook_id, None, [2], None, 0]
        result = self._core.rpc_call(RPCMethod.GET_NOTEBOOK, params, f"/notebook/{notebook_id}")

        sources = []
        try:
            for s in result[0][1]:
                source_id = s[0][0]
                source_title = s[1][0] if s[1] else ""
                source_status = s[3][1] if len(s) > 3 and s[3] else None
                sources.append({"id": source_id, "title": source_title, "status": source_status})
        except (IndexError, TypeError):
            pass

        title = ""
        try:
            title = result[0][0]
        except (IndexError, TypeError):
            pass

        return {"id": notebook_id, "title": title, "sources": sources}

    def rename(self, notebook_id: str, new_title: str) -> bool:
        """Rename a notebook."""
        params = [notebook_id, new_title, None, [2]]
        self._core.rpc_call(RPCMethod.RENAME_NOTEBOOK, params, f"/notebook/{notebook_id}")
        return True

    def delete(self, notebook_id: str) -> bool:
        """Permanently delete a notebook."""
        params = [[notebook_id], [2]]
        self._core.rpc_call(RPCMethod.DELETE_NOTEBOOK, params)
        return True

    def get_description(self, notebook_id: str) -> str:
        """Get the AI-generated description/summary of the notebook."""
        params = [notebook_id, [2]]
        result = self._core.rpc_call(RPCMethod.SUMMARIZE, params, f"/notebook/{notebook_id}")
        try:
            return result[0][0][0]
        except Exception:
            return ""

    def configure_chat(
        self,
        notebook_id: str,
        goal: ChatGoal = ChatGoal.DEFAULT,
        response_length: ChatResponseLength = ChatResponseLength.DEFAULT,
        custom_prompt: str = None,
    ) -> bool:
        """
        Configure the chat behavior and persona for a notebook.

        Args:
            goal: ChatGoal.DEFAULT | CUSTOM | LEARNING_GUIDE
            response_length: ChatResponseLength.DEFAULT | LONGER | SHORTER
            custom_prompt: Custom system prompt (only used when goal=CUSTOM, max 10,000 chars)
        """
        prompt = custom_prompt if goal == ChatGoal.CUSTOM else None
        params = [
            notebook_id,
            None,
            [2],
            None,
            None,
            None,
            goal.value,
            prompt,
            response_length.value,
        ]
        self._core.rpc_call(RPCMethod.RENAME_NOTEBOOK, params, f"/notebook/{notebook_id}")
        return True

    def get_suggested_reports(self, notebook_id: str) -> list:
        """Get AI-suggested report formats for this notebook."""
        source_ids = self._core.get_source_ids(notebook_id)
        source_ids_triple = [[[sid]] for sid in source_ids]
        params = [source_ids_triple, notebook_id, [2]]
        result = self._core.rpc_call(RPCMethod.GET_SUGGESTED_REPORTS, params, f"/notebook/{notebook_id}")
        return result if isinstance(result, list) else []

    def get_share_status(self, notebook_id: str) -> dict:
        """Get the sharing settings for this notebook."""
        params = [notebook_id, [2]]
        result = self._core.rpc_call(RPCMethod.GET_SHARE_STATUS, params, f"/notebook/{notebook_id}")
        return result if result else {}

    def share(
        self,
        notebook_id: str,
        access_level: int = 1,   # 0=restricted, 1=anyone with link
        view_level: int = 0,     # 0=full notebook, 1=chat only
    ) -> dict:
        """
        Set notebook sharing visibility.

        Args:
            access_level: 0 = restricted, 1 = anyone with link
            view_level: 0 = full notebook (chat + sources), 1 = chat only
        """
        params = [notebook_id, [2], access_level, view_level]
        result = self._core.rpc_call(RPCMethod.SHARE_NOTEBOOK, params, f"/notebook/{notebook_id}")
        return result if result else {}

    def remove_recently_viewed(self, notebook_id: str) -> bool:
        """Remove this notebook from the recently viewed list."""
        params = [notebook_id]
        self._core.rpc_call(RPCMethod.REMOVE_RECENTLY_VIEWED, params)
        return True

    # ──────────────────────────────────────────
    # PER-USER SHARING (SET_SHARE_ACCESS)
    # ──────────────────────────────────────────
    # The API reuses RENAME_NOTEBOOK (s0tc2d) with a different parameter
    # structure to manage per-user access — discovered from network analysis.

    def set_share_access(
        self,
        notebook_id: str,
        email: str,
        permission: SharePermission,
    ) -> bool:
        """
        Grant or update a specific user's access to this notebook.

        Args:
            email: Google account email of the person to share with.
            permission: SharePermission.EDITOR | VIEWER
                        (SharePermission.OWNER cannot be assigned)

        Returns:
            True on success.

        Example:
            client.notebooks.set_share_access(nb_id, "user@gmail.com", SharePermission.EDITOR)
        """
        params = [
            notebook_id,
            None,       # title unchanged
            [2],
            None,
            None,
            [[email, permission.value]],  # per-user access entry
        ]
        self._core.rpc_call(RPCMethod.RENAME_NOTEBOOK, params, f"/notebook/{notebook_id}")
        return True

    def add_editor(self, notebook_id: str, email: str) -> bool:
        """Share this notebook with a user as an Editor (can edit)."""
        return self.set_share_access(notebook_id, email, SharePermission.EDITOR)

    def add_viewer(self, notebook_id: str, email: str) -> bool:
        """Share this notebook with a user as a Viewer (read-only)."""
        return self.set_share_access(notebook_id, email, SharePermission.VIEWER)

    def remove_user(self, notebook_id: str, email: str) -> bool:
        """
        Revoke a specific user's access to this notebook.

        Uses SharePermission._REMOVE (code 4) internally.
        """
        params = [
            notebook_id,
            None,
            [2],
            None,
            None,
            [[email, SharePermission._REMOVE.value]],
        ]
        self._core.rpc_call(RPCMethod.RENAME_NOTEBOOK, params, f"/notebook/{notebook_id}")
        return True