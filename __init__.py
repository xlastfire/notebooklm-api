"""
notebooklm — Unofficial synchronous Python wrapper for the NotebookLM API.

Quick start:
    from client import NotebookLMClient
    from rpc.types import AudioFormat, AudioLength

    client = NotebookLMClient(cookies_dict={...})

    nb = client.notebooks.create("My New Notebook")
    client.sources.add_url(nb["id"], "https://en.wikipedia.org/wiki/Python_(programming_language)")
    answer = client.chat.ask(nb["id"], "Give me a summary")
    print(answer)
"""

from notebooklm.client import NotebookLMClient
from notebooklm.exceptions import (
    NotebookLMError,
    NetworkError,
    RPCError,
    AuthError,
    RateLimitError,
    ServerError,
    ClientError,
    RPCTimeoutError,
)

__all__ = [
    # Main client
    "NotebookLMClient",

    # Exceptions
    "NotebookLMError",
    "NetworkError",
    "RPCError",
    "AuthError",
    "RateLimitError",
    "ServerError",
    "ClientError",
    "RPCTimeoutError",
]

__version__ = "1.0.0"
__author__ = "xlastfire"
