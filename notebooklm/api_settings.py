"""User Settings API - get and set NotebookLM account-level preferences."""

from .rpc.types import RPCMethod
from .core import SyncClientCore


class UserSettingsAPI:
    def __init__(self, core: SyncClientCore):
        self._core = core

    def get(self) -> dict:
        """
        Get current user settings (including preferred output language).

        Returns:
            dict with keys:
              - output_language: str (e.g. "en", "si", "ja")
              - raw: the full raw API result
        """
        params = [[2]]
        result = self._core.rpc_call(RPCMethod.GET_USER_SETTINGS, params)

        output_language = None
        try:
            output_language = result[0][0]
        except (IndexError, TypeError):
            pass

        return {
            "output_language": output_language,
            "raw": result,
        }

    def set_output_language(self, language: str) -> bool:
        """
        Set the preferred output language for NotebookLM responses.

        Args:
            language: BCP-47 language code, e.g.:
                      "en"       → English
                      "si"       → Sinhala
                      "ja"       → Japanese
                      "zh_Hans"  → Chinese (Simplified)
                      "fr"       → French
                      "de"       → German
                      "es"       → Spanish
                      "ko"       → Korean
                      "pt"       → Portuguese
                      "ar"       → Arabic

        Returns:
            True on success.
        """
        params = [[2], language]
        self._core.rpc_call(RPCMethod.SET_USER_SETTINGS, params)
        return True
