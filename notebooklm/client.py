"""
NotebookLMClient — the main entry point for the NotebookLM API wrapper.

Usage:
    from client import NotebookLMClient

    client = NotebookLMClient(cookies_dict={...})
    notebooks = client.notebooks.list()
"""

from .core import SyncClientCore
from .api_notebooks import NotebooksAPI
from .api_sources import SourcesAPI
from .api_artifacts import ArtifactsAPI
from .api_chat import ChatAPI
from .api_notes import NotesAPI
from .api_research import ResearchAPI
from .api_settings import UserSettingsAPI


class NotebookLMClient:
    """
    Synchronous NotebookLM API client authenticated via browser cookies.

    Attributes:
        notebooks   — CRUD + sharing + chat config for notebooks
        sources     — Add/delete/refresh sources (URL, text, Drive, file)
        chat        — Ask questions and retrieve conversation history
        artifacts   — Generate audio, video, quiz, flashcards, infographic, slides, reports
        notes       — Create/update/delete notes and generate mind maps
        research    — Run Fast or Deep Research sessions
        settings    — Get/set account-level preferences (e.g. output language)
    """

    def __init__(self, cookies_dict: dict):
        """
        Initialize the client with a dict of Google authentication cookies.

        Args:
            cookies_dict: A dict of cookie name → value pairs extracted from
                          your browser after logging into notebooklm.google.com.
                          Required cookies include: SID, HSID, SSID, APISID,
                          SAPISID, __Secure-1PSID, __Secure-3PSID, etc.

        Raises:
            Exception: If CSRF token or Session ID cannot be extracted,
                       meaning the cookies are invalid or expired.
        """
        self._core = SyncClientCore(cookies_dict)

        self.notebooks = NotebooksAPI(self._core)
        self.sources   = SourcesAPI(self._core)
        self.chat      = ChatAPI(self._core)
        self.artifacts = ArtifactsAPI(self._core)
        self.notes     = NotesAPI(self._core)
        self.research  = ResearchAPI(self._core)
        self.settings  = UserSettingsAPI(self._core)

    @property
    def core(self) -> SyncClientCore:
        """Direct access to the underlying RPC core (advanced use only)."""
        return self._core

    def __repr__(self) -> str:
        return (
            f"<NotebookLMClient "
            f"session_id={self._core.session_id!r} "
            f"csrf={'set' if self._core.csrf_token else 'missing'}>"
        )