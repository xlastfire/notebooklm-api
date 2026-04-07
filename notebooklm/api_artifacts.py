"""Artifacts API - generate and manage all NotebookLM Studio content.

Covers: Audio Overview, Video Overview, Quiz, Flashcards, Infographic,
        Slide Deck, Report (Briefing Doc / Study Guide / Blog / Custom),
        and generic artifact management.
"""

import time
from .rpc.types import (
    RPCMethod,
    ArtifactTypeCode,
    ArtifactStatus,
    artifact_status_to_str,
    AudioFormat,
    AudioLength,
    VideoFormat,
    VideoStyle,
    QuizQuantity,
    QuizDifficulty,
    InfographicOrientation,
    InfographicDetail,
    InfographicStyle,
    SlideDeckFormat,
    SlideDeckLength,
    ExportType,
)
from .core import SyncClientCore


class ArtifactsAPI:
    def __init__(self, core: SyncClientCore):
        self._core = core

    # ──────────────────────────────────────────
    # LISTING & STATUS
    # ──────────────────────────────────────────

    def list(self, notebook_id: str) -> list:
        """List all artifacts in a notebook."""
        params = [
            [2],
            notebook_id,
            'NOT artifact.status = "ARTIFACT_STATUS_SUGGESTED"',
        ]
        result = self._core.rpc_call(RPCMethod.LIST_ARTIFACTS, params, f"/notebook/{notebook_id}")
        return result[0] if result and isinstance(result, list) and len(result) > 0 else []

    def poll_status(self, notebook_id: str, artifact_id: str) -> int | None:
        """
        Check the processing status of an artifact.

        Returns:
            ArtifactStatus int: 1=processing, 2=pending, 3=completed, 4=failed
        """
        for a in self.list(notebook_id):
            if a[0] == artifact_id:
                return a[4]
        return None

    def wait_for_completion(
        self,
        notebook_id: str,
        artifact_id: str,
        poll_interval: int = 5,
        timeout: int = 300,
    ) -> str:
        """
        Block and poll until the artifact is completed or failed.

        Args:
            poll_interval: Seconds between status checks (default 5)
            timeout: Maximum total wait time in seconds (default 300)

        Returns:
            str: "completed" | "failed" | "timeout"
        """
        deadline = time.time() + timeout
        while time.time() < deadline:
            status = self.poll_status(notebook_id, artifact_id)
            if status == ArtifactStatus.COMPLETED:
                return "completed"
            if status == ArtifactStatus.FAILED:
                return "failed"
            time.sleep(poll_interval)
        return "timeout"

    # ──────────────────────────────────────────
    # RAW DATA & DOWNLOAD
    # ──────────────────────────────────────────

    def get_raw(self, notebook_id: str, artifact_id: str) -> list | None:
        """
        Return the full raw artifact data array from the API for a single artifact.

        Useful for inspecting what fields the API returns (e.g. URLs, metadata).
        Returns None if the artifact_id is not found.
        """
        for a in self.list(notebook_id):
            if a[0] == artifact_id:
                return a
        return None

    def get_audio_url(self, notebook_id: str, artifact_id: str) -> str | None:
        """
        Extract the streaming/download URL from a completed Audio Overview artifact.

        NotebookLM embeds the audio URL inside the LIST_ARTIFACTS response once
        the artifact reaches COMPLETED status. The URL is a signed Google Storage
        URL that is valid for a limited time and requires your session cookies.

        Returns:
            URL string (str) or None if not yet available / not an audio artifact.
        """
        raw = self.get_raw(notebook_id, artifact_id)
        if not raw:
            return None
        return self._extract_url_from_artifact(raw)

    @staticmethod
    def _extract_url_from_artifact(raw: list) -> str | None:
        """
        Extract the primary audio URL from a completed audio artifact.

        Real API structure (from live data inspection):
          raw[6][5] = list of media tracks: [url, track_type, mime_type?]
            track_type 1 = primary MP4 audio  (=m140)
            track_type 4 = download version   (=m140-dv)
            track_type 2 = HLS stream         (=mm,hls)
            track_type 3 = DASH stream        (=mm,dash)

        Prefers track_type=1 (primary MP4). Falls back to type=4, then any track.
        """
        try:
            tracks = raw[6][5]
            if isinstance(tracks, list):
                # prefer primary (type 1), then download (type 4), then first
                preferred = None
                fallback = None
                for track in tracks:
                    if isinstance(track, list) and len(track) >= 1:
                        url = track[0]
                        ttype = track[1] if len(track) > 1 else None
                        if ttype == 1:
                            preferred = url
                        elif ttype == 4 and not fallback:
                            fallback = url
                return preferred or fallback
        except (IndexError, TypeError):
            pass
        return None

    @staticmethod
    def _parse_audio_block(block: list) -> dict:
        """Parse the audio data block (raw[6]) into a clean dict."""
        if not isinstance(block, list):
            return {}

        # Config is at block[1]: ['instructions', length_code, None, source_ids, language, ...]
        language = None
        length_code = None
        instructions = None
        try:
            config = block[1]
            if isinstance(config, list):
                instructions = config[0] if config[0] else None
                length_code = config[1]
                language = config[4] if len(config) > 4 else None
        except (IndexError, TypeError):
            pass

        # Duration at block[6]: [seconds, nanoseconds]
        duration_seconds = None
        try:
            dur = block[6]
            if isinstance(dur, list) and len(dur) >= 1:
                duration_seconds = dur[0]
        except (IndexError, TypeError):
            pass

        # Media tracks at block[5]
        urls = {}
        _TRACK_NAMES = {1: "primary", 2: "hls", 3: "dash", 4: "download"}
        try:
            tracks = block[5]
            if isinstance(tracks, list):
                for track in tracks:
                    if isinstance(track, list) and len(track) >= 1:
                        url = track[0]
                        ttype = track[1] if len(track) > 1 else None
                        name = _TRACK_NAMES.get(ttype, f"track_{ttype}")
                        mime = track[2] if len(track) > 2 else None
                        urls[name] = {"url": url, "mime": mime}
        except (IndexError, TypeError):
            pass

        return {
            "language": language,
            "length_code": length_code,
            "instructions": instructions,
            "duration_seconds": duration_seconds,
            "urls": urls,
        }

    @staticmethod
    def _extract_source_ids(raw_sources) -> list[str]:
        """Flatten the nested source_ids triple structure."""
        ids = []
        def _walk(obj):
            if isinstance(obj, str) and len(obj) > 8:
                ids.append(obj)
            elif isinstance(obj, list):
                for item in obj:
                    _walk(item)
        _walk(raw_sources)
        return list(dict.fromkeys(ids))  # deduplicate, preserve order

    def parse_artifact(self, raw: list) -> dict:
        """
        Parse a single raw artifact list (from list()) into a clean readable dict.

        Returns a dict with keys:
          id, title, type, type_code, status, status_code, source_ids, created_at,
          etag — and a nested 'audio' key for audio artifacts with urls, duration,
          language, etc.

        Example output for an audio artifact:
        {
            "id": "1f0e6f7e-...",
            "title": "My Podcast",
            "type": "audio",
            "type_code": 1,
            "status": "completed",
            "status_code": 3,
            "source_ids": ["97b50e77-..."],
            "created_at": 1761996173,
            "etag": "MTc2MT...",
            "audio": {
                "language": "si",
                "length_code": 2,
                "instructions": None,
                "duration_seconds": 1534,
                "urls": {
                    "primary":  {"url": "https://...=m140",    "mime": "audio/mp4"},
                    "download": {"url": "https://...=m140-dv", "mime": "audio/mp4"},
                    "hls":      {"url": "https://...=mm,hls",  "mime": None},
                    "dash":     {"url": "https://...=mm,dash", "mime": None},
                }
            }
        }
        """
        _TYPE_NAMES = {
            1: "audio", 2: "report", 3: "video", 4: "quiz",
            5: "mind_map", 7: "infographic", 8: "slide_deck", 9: "data_table",
        }
        _STATUS_NAMES = {
            1: "processing", 2: "pending", 3: "completed", 4: "failed",
        }

        artifact_id    = raw[0]  if len(raw) > 0 else None
        title          = raw[1]  if len(raw) > 1 else None
        type_code      = raw[2]  if len(raw) > 2 else None
        raw_sources    = raw[3]  if len(raw) > 3 else []
        status_code    = raw[4]  if len(raw) > 4 else None
        media_block    = raw[6]  if len(raw) > 6 else None
        created_ts     = raw[10] if len(raw) > 10 else None
        etag           = raw[21] if len(raw) > 21 else None

        # Created timestamp: [unix_seconds, nanoseconds]
        created_at = None
        if isinstance(created_ts, list) and len(created_ts) >= 1:
            created_at = created_ts[0]

        result = {
            "id":          artifact_id,
            "title":       title,
            "type":        _TYPE_NAMES.get(type_code, f"unknown_{type_code}"),
            "type_code":   type_code,
            "status":      _STATUS_NAMES.get(status_code, "unknown"),
            "status_code": status_code,
            "source_ids":  self._extract_source_ids(raw_sources),
            "created_at":  created_at,
            "etag":        etag,
        }

        # Attach audio details if this is an audio artifact
        if type_code == ArtifactTypeCode.AUDIO and media_block:
            result["audio"] = self._parse_audio_block(media_block)

        return result

    def list_parsed(self, notebook_id: str) -> list[dict]:
        """
        List all artifacts as clean, readable dicts.

        This is the human-friendly version of list(). Instead of opaque nested
        lists, you get structured dicts with named fields.

        Example:
            for artifact in client.artifacts.list_parsed(nb_id):
                print(artifact["title"], artifact["status"])
                if artifact["type"] == "audio":
                    print("Duration:", artifact["audio"]["duration_seconds"], "sec")
                    print("Download URL:", artifact["audio"]["urls"]["primary"]["url"])
        """
        return [self.parse_artifact(raw) for raw in self.list(notebook_id)]

    def download_audio(
        self,
        notebook_id: str,
        artifact_id: str,
        output_path: str,
        wait: bool = True,
        poll_interval: int = 5,
        timeout: int = 300,
    ) -> str:
        """
        [DEPRECATED / BLOCKED BY GOOGLE]
        Downloading audio directly via Python `requests` is blocked by Google's
        cross-domain anti-bot protections on lh3.googleusercontent.com, which
        will redirect headless scripts to a Google Login HTML page.

        To securely download audio, you must use `get_audio_url()` and pass the
        resulting URL to a legitimate authenticated Browser (e.g., via `webbrowser.open`
        or `playwright`).
        """
        raise NotImplementedError(
            "Programmatic downloading of NotebookLM audio is actively blocked by Google's "
            "anti-bot servers (which returns an HTML login page instead of the mp3). "
            "To download, please use `client.artifacts.get_audio_url()` to retrieve the raw "
            "URL and open it in a real browser, or use Python's `webbrowser.open(url)`."
        )

    def delete(self, notebook_id: str, artifact_id: str) -> bool:
        """Delete an artifact permanently."""
        params = [[2], notebook_id, [[artifact_id]]]
        self._core.rpc_call(RPCMethod.DELETE_ARTIFACT, params, f"/notebook/{notebook_id}")
        return True

    def rename(self, notebook_id: str, artifact_id: str, new_title: str) -> bool:
        """Rename an artifact."""
        params = [[2], notebook_id, artifact_id, new_title]
        self._core.rpc_call(RPCMethod.RENAME_ARTIFACT, params, f"/notebook/{notebook_id}")
        return True

    def export(self, notebook_id: str, artifact_id: str, export_type: ExportType = ExportType.DOCS) -> dict:
        """
        Export an artifact to Google Docs or Google Sheets.

        Args:
            export_type: ExportType.DOCS or ExportType.SHEETS
        """
        params = [[2], notebook_id, artifact_id, export_type.value]
        result = self._core.rpc_call(RPCMethod.EXPORT_ARTIFACT, params, f"/notebook/{notebook_id}")
        return result if result else {}

    def share(self, notebook_id: str, artifact_id: str) -> dict:
        """Get a shareable link for an artifact."""
        params = [[2], notebook_id, artifact_id]
        result = self._core.rpc_call(RPCMethod.SHARE_ARTIFACT, params, f"/notebook/{notebook_id}")
        return result if result else {}

    def get_interactive_html(self, notebook_id: str, artifact_id: str) -> str:
        """Fetch the raw HTML for interactive artifacts (Quiz / Flashcards)."""
        params = [[2], notebook_id, artifact_id]
        result = self._core.rpc_call(RPCMethod.GET_INTERACTIVE_HTML, params, f"/notebook/{notebook_id}")
        try:
            return result[0] if isinstance(result, list) else result
        except Exception:
            return ""

    # ──────────────────────────────────────────
    # AUDIO OVERVIEW (Podcast)
    # ──────────────────────────────────────────

    def generate_audio(
        self,
        notebook_id: str,
        language: str = "en",
        length: AudioLength = AudioLength.DEFAULT,
        audio_format: AudioFormat = AudioFormat.DEEP_DIVE,
        instructions: str = None,
        source_ids: list = None,
    ) -> str | None:
        """
        Generate an Audio Overview (Podcast).

        Args:
            language: Language code — "en", "si", "ja", "zh_Hans", etc.
            length: AudioLength.SHORT | DEFAULT | LONG
            audio_format: AudioFormat.DEEP_DIVE | BRIEF | CRITIQUE | DEBATE
            instructions: Custom host instructions (e.g. "Explain like I'm 5")
            source_ids: Override which sources to use (defaults to all)

        Returns:
            artifact_id (str) or None
        """
        if source_ids is None:
            source_ids = self._core.get_source_ids(notebook_id)

        source_ids_triple = [[[sid]] for sid in source_ids]
        source_ids_double = [[sid] for sid in source_ids]

        params = [
            [2],
            notebook_id,
            [
                None,
                None,
                ArtifactTypeCode.AUDIO,
                source_ids_triple,
                None,
                None,
                [
                    None,
                    [
                        instructions,
                        length.value,
                        None,
                        source_ids_double,
                        language,
                        None,
                        audio_format.value,
                    ],
                ],
            ],
        ]
        result = self._core.rpc_call(RPCMethod.CREATE_ARTIFACT, params, f"/notebook/{notebook_id}")
        if result and isinstance(result, list) and len(result) > 0:
            return result[0][0] if isinstance(result[0], list) else result[0]
        return None

    # ──────────────────────────────────────────
    # VIDEO OVERVIEW
    # ──────────────────────────────────────────

    def generate_video(
        self,
        notebook_id: str,
        video_format: VideoFormat = VideoFormat.EXPLAINER,
        style: VideoStyle = VideoStyle.AUTO_SELECT,
        language: str = "en",
        source_ids: list = None,
    ) -> str | None:
        """
        Generate a Video Overview.

        Args:
            video_format: VideoFormat.EXPLAINER | BRIEF | CINEMATIC
            style: VideoStyle.AUTO_SELECT | CLASSIC | WHITEBOARD | KAWAII | ANIME | etc.
            language: Language code
            source_ids: Override which sources to use

        Returns:
            artifact_id (str) or None
        """
        if source_ids is None:
            source_ids = self._core.get_source_ids(notebook_id)

        source_ids_triple = [[[sid]] for sid in source_ids]
        source_ids_double = [[sid] for sid in source_ids]

        params = [
            [2],
            notebook_id,
            [
                None,
                None,
                ArtifactTypeCode.VIDEO,
                source_ids_triple,
                None,
                None,
                [
                    None,
                    [
                        None,
                        None,
                        source_ids_double,
                        language,
                        video_format.value,
                        style.value,
                    ],
                ],
            ],
        ]
        result = self._core.rpc_call(RPCMethod.CREATE_ARTIFACT, params, f"/notebook/{notebook_id}")
        if result and isinstance(result, list) and len(result) > 0:
            return result[0][0] if isinstance(result[0], list) else result[0]
        return None

    # ──────────────────────────────────────────
    # QUIZ
    # ──────────────────────────────────────────

    def generate_quiz(
        self,
        notebook_id: str,
        quantity: QuizQuantity = QuizQuantity.STANDARD,
        difficulty: QuizDifficulty = QuizDifficulty.MEDIUM,
        language: str = "en",
        source_ids: list = None,
    ) -> str | None:
        """
        Generate an interactive Quiz.

        Args:
            quantity: QuizQuantity.FEWER | STANDARD
            difficulty: QuizDifficulty.EASY | MEDIUM | HARD
            language: Language code
            source_ids: Override which sources to use

        Returns:
            artifact_id (str) or None
        """
        if source_ids is None:
            source_ids = self._core.get_source_ids(notebook_id)

        source_ids_triple = [[[sid]] for sid in source_ids]

        params = [
            [2],
            notebook_id,
            [
                None,
                None,
                ArtifactTypeCode.QUIZ,
                source_ids_triple,
                None,
                None,
                [
                    None,
                    [
                        None,
                        quantity.value,
                        difficulty.value,
                        language,
                    ],
                ],
            ],
        ]
        result = self._core.rpc_call(RPCMethod.CREATE_ARTIFACT, params, f"/notebook/{notebook_id}")
        if result and isinstance(result, list) and len(result) > 0:
            return result[0][0] if isinstance(result[0], list) else result[0]
        return None

    # ──────────────────────────────────────────
    # FLASHCARDS
    # ──────────────────────────────────────────

    def generate_flashcards(
        self,
        notebook_id: str,
        quantity: QuizQuantity = QuizQuantity.STANDARD,
        language: str = "en",
        source_ids: list = None,
    ) -> str | None:
        """
        Generate a Flashcard set.

        Returns:
            artifact_id (str) or None
        """
        # Flashcards use the same type code as quiz (4) with slightly different params
        if source_ids is None:
            source_ids = self._core.get_source_ids(notebook_id)

        source_ids_triple = [[[sid]] for sid in source_ids]

        params = [
            [2],
            notebook_id,
            [
                None,
                None,
                ArtifactTypeCode.QUIZ_FLASHCARD,
                source_ids_triple,
                None,
                None,
                [
                    None,
                    [
                        None,
                        quantity.value,
                        None,   # no difficulty for flashcards
                        language,
                        1,      # flashcard mode flag
                    ],
                ],
            ],
        ]
        result = self._core.rpc_call(RPCMethod.CREATE_ARTIFACT, params, f"/notebook/{notebook_id}")
        if result and isinstance(result, list) and len(result) > 0:
            return result[0][0] if isinstance(result[0], list) else result[0]
        return None

    # ──────────────────────────────────────────
    # INFOGRAPHIC
    # ──────────────────────────────────────────

    def generate_infographic(
        self,
        notebook_id: str,
        orientation: InfographicOrientation = InfographicOrientation.PORTRAIT,
        detail: InfographicDetail = InfographicDetail.STANDARD,
        style: InfographicStyle = InfographicStyle.AUTO_SELECT,
        language: str = "en",
        source_ids: list = None,
    ) -> str | None:
        """
        Generate an Infographic.

        Args:
            orientation: InfographicOrientation.LANDSCAPE | PORTRAIT | SQUARE
            detail: InfographicDetail.CONCISE | STANDARD | DETAILED
            style: InfographicStyle.AUTO_SELECT | SKETCH_NOTE | PROFESSIONAL | etc.
            language: Language code
            source_ids: Override which sources to use

        Returns:
            artifact_id (str) or None
        """
        if source_ids is None:
            source_ids = self._core.get_source_ids(notebook_id)

        source_ids_triple = [[[sid]] for sid in source_ids]

        params = [
            [2],
            notebook_id,
            [
                None,
                None,
                ArtifactTypeCode.INFOGRAPHIC,
                source_ids_triple,
                None,
                None,
                [
                    None,
                    [
                        None,
                        orientation.value,
                        detail.value,
                        style.value,
                        language,
                    ],
                ],
            ],
        ]
        result = self._core.rpc_call(RPCMethod.CREATE_ARTIFACT, params, f"/notebook/{notebook_id}")
        if result and isinstance(result, list) and len(result) > 0:
            return result[0][0] if isinstance(result[0], list) else result[0]
        return None

    # ──────────────────────────────────────────
    # SLIDE DECK
    # ──────────────────────────────────────────

    def generate_slide_deck(
        self,
        notebook_id: str,
        slide_format: SlideDeckFormat = SlideDeckFormat.DETAILED_DECK,
        length: SlideDeckLength = SlideDeckLength.DEFAULT,
        language: str = "en",
        source_ids: list = None,
    ) -> str | None:
        """
        Generate a Slide Deck.

        Args:
            slide_format: SlideDeckFormat.DETAILED_DECK | PRESENTER_SLIDES
            length: SlideDeckLength.DEFAULT | SHORT
            language: Language code
            source_ids: Override which sources to use

        Returns:
            artifact_id (str) or None
        """
        if source_ids is None:
            source_ids = self._core.get_source_ids(notebook_id)

        source_ids_triple = [[[sid]] for sid in source_ids]

        params = [
            [2],
            notebook_id,
            [
                None,
                None,
                ArtifactTypeCode.SLIDE_DECK,
                source_ids_triple,
                None,
                None,
                [
                    None,
                    [
                        None,
                        slide_format.value,
                        length.value,
                        language,
                    ],
                ],
            ],
        ]
        result = self._core.rpc_call(RPCMethod.CREATE_ARTIFACT, params, f"/notebook/{notebook_id}")
        if result and isinstance(result, list) and len(result) > 0:
            return result[0][0] if isinstance(result[0], list) else result[0]
        return None

    def revise_slide(self, notebook_id: str, artifact_id: str, slide_index: int, prompt: str) -> dict:
        """
        Revise a single slide within a Slide Deck artifact using a text prompt.

        Args:
            slide_index: Zero-based index of the slide to revise
            prompt: Instruction for how to revise the slide
        """
        params = [[2], notebook_id, artifact_id, slide_index, prompt]
        result = self._core.rpc_call(RPCMethod.REVISE_SLIDE, params, f"/notebook/{notebook_id}")
        return result if result else {}

    # ──────────────────────────────────────────
    # REPORT (Briefing Doc, Study Guide, Blog, Custom)
    # ──────────────────────────────────────────

    def generate_report(
        self,
        notebook_id: str,
        report_type: str = "briefing_doc",
        custom_title: str = None,
        custom_prompt: str = None,
        language: str = "en",
        source_ids: list = None,
    ) -> str | None:
        """
        Generate a text-based Report artifact.

        Args:
            report_type: "briefing_doc" | "study_guide" | "blog_post" | "custom"
            custom_title: Override the report title (used for custom type)
            custom_prompt: Prompt describing the custom report (used for custom type)
            language: Language code
            source_ids: Override which sources to use

        Returns:
            artifact_id (str) or None
        """
        # Predefined templates
        _REPORT_TEMPLATES = {
            "briefing_doc": ("Briefing Doc", None),
            "study_guide":  ("Study Guide", None),
            "blog_post":    ("Blog Post", None),
        }

        if source_ids is None:
            source_ids = self._core.get_source_ids(notebook_id)

        source_ids_triple = [[[sid]] for sid in source_ids]

        if report_type in _REPORT_TEMPLATES:
            title, prompt = _REPORT_TEMPLATES[report_type]
        else:
            title = custom_title or "Custom Report"
            prompt = custom_prompt

        params = [
            [2],
            notebook_id,
            [
                None,
                None,
                ArtifactTypeCode.REPORT,
                source_ids_triple,
                None,
                None,
                [
                    None,
                    [
                        title,
                        prompt,
                        language,
                    ],
                ],
            ],
        ]
        result = self._core.rpc_call(RPCMethod.CREATE_ARTIFACT, params, f"/notebook/{notebook_id}")
        if result and isinstance(result, list) and len(result) > 0:
            return result[0][0] if isinstance(result[0], list) else result[0]
        return None

    # ──────────────────────────────────────────
    # CONVENIENCE ALIASES
    # ──────────────────────────────────────────

    def generate_briefing_doc(self, notebook_id: str, language: str = "en", source_ids: list = None) -> str | None:
        """Shortcut: generate a Briefing Document."""
        return self.generate_report(notebook_id, "briefing_doc", language=language, source_ids=source_ids)

    def generate_study_guide(self, notebook_id: str, language: str = "en", source_ids: list = None) -> str | None:
        """Shortcut: generate a Study Guide."""
        return self.generate_report(notebook_id, "study_guide", language=language, source_ids=source_ids)

    def generate_blog_post(self, notebook_id: str, language: str = "en", source_ids: list = None) -> str | None:
        """Shortcut: generate a Blog Post."""
        return self.generate_report(notebook_id, "blog_post", language=language, source_ids=source_ids)

    # ──────────────────────────────────────────
    # DATA TABLE  (ArtifactTypeCode = 9)
    # ──────────────────────────────────────────

    def generate_data_table(
        self,
        notebook_id: str,
        language: str = "en",
        source_ids: list = None,
    ) -> str | None:
        """
        Generate a Data Table artifact from notebook sources.

        NotebookLM extracts structured tabular data from source documents
        and presents it as an interactive, formatted table.

        Args:
            language: Language code (e.g. "en", "ja", "si")
            source_ids: Override which sources to use (defaults to all)

        Returns:
            artifact_id (str) or None
        """
        if source_ids is None:
            source_ids = self._core.get_source_ids(notebook_id)

        source_ids_triple = [[[sid]] for sid in source_ids]

        params = [
            [2],
            notebook_id,
            [
                None,
                None,
                ArtifactTypeCode.DATA_TABLE,
                source_ids_triple,
                None,
                None,
                [
                    None,
                    [language],
                ],
            ],
        ]
        result = self._core.rpc_call(RPCMethod.CREATE_ARTIFACT, params, f"/notebook/{notebook_id}")
        if result and isinstance(result, list) and len(result) > 0:
            return result[0][0] if isinstance(result[0], list) else result[0]
        return None

    # ──────────────────────────────────────────
    # MIND MAP via CREATE_ARTIFACT  (ArtifactTypeCode = 5)
    # ──────────────────────────────────────────

    def generate_mind_map(
        self,
        notebook_id: str,
        language: str = "en",
        source_ids: list = None,
    ) -> str | None:
        """
        Generate a Mind Map artifact using the Studio CREATE_ARTIFACT pipeline.

        This differs from ``notes.generate_mind_map()`` which uses the older
        ``GENERATE_MIND_MAP`` RPC — this version creates a proper Studio
        artifact that can be renamed, exported, and shared like other artifacts.

        Args:
            language: Language code (e.g. "en", "ja", "si")
            source_ids: Override which sources to use (defaults to all)

        Returns:
            artifact_id (str) or None
        """
        if source_ids is None:
            source_ids = self._core.get_source_ids(notebook_id)

        source_ids_triple = [[[sid]] for sid in source_ids]

        params = [
            [2],
            notebook_id,
            [
                None,
                None,
                ArtifactTypeCode.MIND_MAP,
                source_ids_triple,
                None,
                None,
                [
                    None,
                    [language],
                ],
            ],
        ]
        result = self._core.rpc_call(RPCMethod.CREATE_ARTIFACT, params, f"/notebook/{notebook_id}")
        if result and isinstance(result, list) and len(result) > 0:
            return result[0][0] if isinstance(result[0], list) else result[0]
        return None