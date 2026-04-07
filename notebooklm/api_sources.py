"""Sources API - add, delete, refresh, and inspect sources in a notebook."""

import os
import json
from pathlib import Path

from .rpc.types import RPCMethod, UPLOAD_URL, DriveMimeType, SourceStatus, source_status_to_str
from .core import SyncClientCore


class SourcesAPI:
    def __init__(self, core: SyncClientCore):
        self._core = core

    def list(self, notebook_id: str) -> list[dict]:
        """
        List all sources in a notebook with their metadata.

        Returns a list of dicts with keys: id, title, status, status_str, type
        """
        params = [notebook_id, None, [2], None, 0]
        result = self._core.rpc_call(RPCMethod.GET_NOTEBOOK, params, f"/notebook/{notebook_id}")

        sources = []
        try:
            for s in result[0][1]:
                source_id = s[0][0]
                title = s[1][0] if s[1] else ""
                status_code = s[3][1] if len(s) > 3 and s[3] else None
                sources.append({
                    "id": source_id,
                    "title": title,
                    "status_code": status_code,
                    "status": source_status_to_str(status_code) if status_code else "unknown",
                })
        except (IndexError, TypeError):
            pass
        return sources

    def add_url(self, notebook_id: str, url: str) -> list:
        """Add a web URL or YouTube link as a source."""
        params = [
            [[None, None, [url], None, None, None, None, None]],
            notebook_id,
            [2],
            None,
            None,
        ]
        return self._core.rpc_call(RPCMethod.ADD_SOURCE, params, f"/notebook/{notebook_id}")

    def add_text(self, notebook_id: str, title: str, content: str) -> list:
        """Add a pasted text block as a source."""
        params = [
            [[None, [title, content], None, None, None, None, None, None]],
            notebook_id,
            [2],
            None,
            None,
        ]
        return self._core.rpc_call(RPCMethod.ADD_SOURCE, params, f"/notebook/{notebook_id}")

    def add_drive(
        self,
        notebook_id: str,
        file_id: str,
        title: str,
        mime_type: str = DriveMimeType.GOOGLE_DOC,
    ) -> list:
        """
        Add a Google Drive document as a source.

        Args:
            file_id: Google Drive file ID (from the URL)
            title: Display name for the source
            mime_type: MIME type — use DriveMimeType enum values
        """
        source_data = [[file_id, mime_type, 1, title], None, None, None, None, None, None, None, None, None, 1]
        params = [
            [source_data],
            notebook_id,
            [2],
            [1, None, None, None, None, None, None, None, None, None, [1]],
        ]
        return self._core.rpc_call(RPCMethod.ADD_SOURCE, params, f"/notebook/{notebook_id}")

    def add_file(self, notebook_id: str, file_path: str) -> dict:
        """
        Upload and add a local file (PDF, Markdown, DOCX, TXT) as a source.

        Performs a 3-step protocol:
        1. Register source to get an upload ID
        2. Initiate resumable upload and get upload URL
        3. Stream file bytes to the upload URL
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        filename = path.name
        file_size = path.stat().st_size

        # Step 1 — Register the file and get a source ID
        reg_params = [
            [[filename]],
            notebook_id,
            [2],
            [1, None, None, None, None, None, None, None, None, None, [1]],
        ]
        reg_res = self._core.rpc_call(RPCMethod.ADD_SOURCE_FILE, reg_params, f"/notebook/{notebook_id}")

        def _extract_id(data):
            if isinstance(data, str):
                return data
            if isinstance(data, list) and len(data) > 0:
                return _extract_id(data[0])
            return None

        source_id = _extract_id(reg_res)

        # Step 2 — Get a resumable upload URL
        upload_meta_url = f"{UPLOAD_URL}?authuser=0"
        headers = {
            "x-goog-upload-command": "start",
            "x-goog-upload-header-content-length": str(file_size),
            "x-goog-upload-protocol": "resumable",
            "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
        }
        body = json.dumps({
            "PROJECT_ID": notebook_id,
            "SOURCE_NAME": filename,
            "SOURCE_ID": source_id,
        })
        meta_res = self._core.session.post(upload_meta_url, headers=headers, data=body)
        meta_res.raise_for_status()
        upload_url = meta_res.headers.get("x-goog-upload-url")
        if not upload_url:
            raise RuntimeError("Failed to get upload URL from Google. The file may not be supported.")

        # Step 3 — Stream file bytes to the upload URL
        with open(path, "rb") as f:
            upload_headers = {
                "x-goog-upload-command": "upload, finalize",
                "x-goog-upload-offset": "0",
                "Content-Type": "application/octet-stream",
            }
            final_res = self._core.session.post(upload_url, headers=upload_headers, data=f)
            final_res.raise_for_status()

        return {"id": source_id, "title": filename, "status": "processing"}

    def delete(self, notebook_id: str, source_id: str) -> bool:
        """Permanently delete a source from a notebook."""
        params = [[[source_id]]]
        self._core.rpc_call(RPCMethod.DELETE_SOURCE, params, f"/notebook/{notebook_id}")
        return True

    def get(self, notebook_id: str, source_id: str) -> dict:
        """Get full details for a single source."""
        params = [notebook_id, source_id, [2]]
        result = self._core.rpc_call(RPCMethod.GET_SOURCE, params, f"/notebook/{notebook_id}")
        return result if result else {}

    def refresh(self, notebook_id: str, source_id: str) -> bool:
        """Re-fetch and re-index a URL-based source to get updated content."""
        params = [notebook_id, source_id, [2]]
        self._core.rpc_call(RPCMethod.REFRESH_SOURCE, params, f"/notebook/{notebook_id}")
        return True

    def check_freshness(self, notebook_id: str, source_id: str) -> dict:
        """Check whether a URL-based source has been updated since last import."""
        params = [notebook_id, source_id, [2]]
        result = self._core.rpc_call(RPCMethod.CHECK_SOURCE_FRESHNESS, params, f"/notebook/{notebook_id}")
        return result if result else {}

    def update_title(self, notebook_id: str, source_id: str, new_title: str) -> bool:
        """Rename a source's display title."""
        params = [notebook_id, source_id, new_title, [2]]
        self._core.rpc_call(RPCMethod.UPDATE_SOURCE, params, f"/notebook/{notebook_id}")
        return True

    def discover(self, notebook_id: str) -> list:
        """
        Ask NotebookLM to auto-discover additional related sources
        based on the content already in the notebook.
        """
        source_ids = self._core.get_source_ids(notebook_id)
        source_ids_triple = [[[sid]] for sid in source_ids]
        params = [source_ids_triple, notebook_id, [2]]
        result = self._core.rpc_call(RPCMethod.DISCOVER_SOURCES, params, f"/notebook/{notebook_id}")
        return result if isinstance(result, list) else []

    def get_guide(self, notebook_id: str, source_id: str) -> str:
        """Get the AI-generated source guide/summary for a specific source."""
        params = [notebook_id, source_id, [2]]
        result = self._core.rpc_call(RPCMethod.GET_SOURCE_GUIDE, params, f"/notebook/{notebook_id}")
        try:
            return result[0][0]
        except (IndexError, TypeError):
            return ""