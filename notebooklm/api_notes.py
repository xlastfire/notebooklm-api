"""Notes & Mind Map API - create, list, update, delete notes and generate mind maps."""

from .rpc.types import RPCMethod
from .core import SyncClientCore


class NotesAPI:
    def __init__(self, core: SyncClientCore):
        self._core = core

    def list(self, notebook_id: str) -> list:
        """
        List all notes and mind maps in a notebook.

        Returns raw API data. Each item is a list where:
          - item[0] = note/mindmap ID
          - item[1] = title
          - item[2] = content (for notes)
        """
        params = [notebook_id]
        result = self._core.rpc_call(
            RPCMethod.GET_NOTES_AND_MIND_MAPS, params, f"/notebook/{notebook_id}"
        )
        return result[0] if result and isinstance(result, list) and len(result) > 0 else []

    def list_clean(self, notebook_id: str) -> list[dict]:
        """
        List notes as structured dicts with id, title, and content.

        Returns:
            List of dicts: {"id": str, "title": str, "content": str}
        """
        raw = self.list(notebook_id)
        notes = []
        for item in raw:
            try:
                note_id = item[0]
                title = item[1] if len(item) > 1 else ""
                content = item[2] if len(item) > 2 else ""
                notes.append({"id": note_id, "title": title, "content": content})
            except (IndexError, TypeError):
                continue
        return notes

    def create(self, notebook_id: str, content: str, title: str = "New Note") -> str | None:
        """
        Create a new note in the notebook.

        Args:
            content: The body text of the note
            title: Display title (optional, defaults to "New Note")

        Returns:
            note_id (str) or None
        """
        params = [notebook_id, "", [1], None, title]
        result = self._core.rpc_call(RPCMethod.CREATE_NOTE, params, f"/notebook/{notebook_id}")

        note_id = None
        if result and isinstance(result, list) and len(result) > 0:
            note_id = result[0][0] if isinstance(result[0], list) else result[0]

        if note_id:
            self.update(notebook_id, note_id, content, title)

        return note_id

    def update(self, notebook_id: str, note_id: str, content: str, title: str = None) -> bool:
        """
        Update the content and/or title of an existing note.

        Args:
            content: New body text
            title: New title (pass None to keep existing)
        """
        if title is None:
            title = ""
        params = [notebook_id, note_id, [[[content, title, [], 0]]]]
        self._core.rpc_call(RPCMethod.UPDATE_NOTE, params, f"/notebook/{notebook_id}")
        return True

    def delete(self, notebook_id: str, note_id: str) -> bool:
        """Delete a note permanently from the notebook."""
        params = [notebook_id, None, [note_id]]
        self._core.rpc_call(RPCMethod.DELETE_NOTE, params, f"/notebook/{notebook_id}")
        return True

    def generate_mind_map(self, notebook_id: str, source_ids: list = None) -> str | None:
        """
        Generate a Mind Map from the notebook's sources.

        Args:
            source_ids: Optional list of source IDs to scope the mind map.
                        Defaults to all sources.

        Returns:
            mind_map_id (str) or None
        """
        if source_ids is None:
            source_ids = self._core.get_source_ids(notebook_id)

        source_ids_triple = [[[sid]] for sid in source_ids]
        params = [source_ids_triple, notebook_id, [2]]
        result = self._core.rpc_call(RPCMethod.GENERATE_MIND_MAP, params, f"/notebook/{notebook_id}")

        if result and isinstance(result, list) and len(result) > 0:
            return result[0][0] if isinstance(result[0], list) else result[0]
        return None