"""
demo.py — Full end-to-end demonstration of the NotebookLM API wrapper.

Replace MY_COOKIES with your actual cookies from notebooklm.google.com.
"""

import time
import sys
from notebooklm.client import NotebookLMClient
from notebooklm.rpc.types import (
    AudioFormat, AudioLength,
    VideoFormat, VideoStyle,
    QuizQuantity, QuizDifficulty,
    InfographicOrientation, InfographicDetail, InfographicStyle,
    SlideDeckFormat, SlideDeckLength,
    ChatGoal, ChatResponseLength,
    ExportType,
)
from notebooklm.exceptions import AuthError, RateLimitError, RPCError

# ─────────────────────────────────────────────────
# 1. AUTH — paste your cookies here
# ─────────────────────────────────────────────────
MY_COOKIES = {
    "SID": "YOUR_SID_COOKIE",
    "HSID": "YOUR_HSID_COOKIE",
    "SSID": "YOUR_SSID_COOKIE",
    "APISID": "YOUR_APISID_COOKIE",
    "SAPISID": "YOUR_SAPISID_COOKIE",
    "__Secure-1PSID": "YOUR___Secure-1PSID_COOKIE",
    "__Secure-3PSID": "YOUR___Secure-3PSID_COOKIE",
    "__Secure-1PSIDTS": "YOUR___Secure-1PSIDTS_COOKIE",
    "__Secure-3PSIDTS": "YOUR___Secure-3PSIDTS_COOKIE",
    "SIDCC": "YOUR_SIDCC_COOKIE",
}

def separator(title: str):
    print(f"\n{'═' * 60}")
    print(f"  {title}")
    print('═' * 60)


def main():
    # ─── Connect ──────────────────────────────────
    separator("Connecting to NotebookLM")
    try:
        client = NotebookLMClient(MY_COOKIES)
        print(f"✅ Connected! {client}")
    except AuthError:
        print("❌ Auth failed — cookies are invalid or expired.")
        sys.exit(1)

    # ─── User Settings ────────────────────────────
    separator("User Settings")
    settings = client.settings.get()
    print(f"  Current output language: {settings['output_language']}")
    # client.settings.set_output_language("en")

    # ─── Notebooks ────────────────────────────────
    separator("Notebooks — List & Create")
    existing = client.notebooks.list()
    print(f"  You have {len(existing)} existing notebook(s).")

    nb = client.notebooks.create(f"Demo Notebook {int(time.time())}")
    nb_id = nb["id"]
    print(f"  ✅ Created: '{nb['title']}' [{nb_id}]")

    # ─── Sources ──────────────────────────────────
    separator("Sources — Add URL & Text")
    client.sources.add_url(nb_id, "https://en.wikipedia.org/wiki/Artificial_intelligence")
    print("  ✅ Added Wikipedia URL source.")

    client.sources.add_text(
        nb_id,
        title="Quick Definition",
        content="Artificial intelligence (AI) is intelligence demonstrated by machines."
    )
    print("  ✅ Added text source.")

    # Wait for sources to be indexed
    print("  Waiting 10s for sources to be indexed...")
    time.sleep(10)

    sources = client.sources.list(nb_id)
    print(f"  Sources: {[s['title'] for s in sources]}")

    # ─── Chat ─────────────────────────────────────
    separator("Chat — Ask a Question")
    answer = client.chat.ask(nb_id, "Give me a one-sentence summary of AI.")
    print(f"  Answer: {answer}")

    # ─── Notes ────────────────────────────────────
    separator("Notes — Create & List")
    note_id = client.notes.create(nb_id, content="Remember: AI is transforming every industry.", title="Key Insight")
    print(f"  ✅ Note created: {note_id}")

    notes = client.notes.list_clean(nb_id)
    print(f"  Notes: {[n['title'] for n in notes]}")

    # ─── Mind Map ─────────────────────────────────
    separator("Mind Map — Generate")
    mm_id = client.notes.generate_mind_map(nb_id)
    print(f"  ✅ Mind map artifact ID: {mm_id}")

    # ─── Artifacts: Audio Overview ─────────────────
    separator("Artifact — Audio Overview (Podcast)")
    audio_id = client.artifacts.generate_audio(
        nb_id,
        language="en",
        length=AudioLength.SHORT,
        audio_format=AudioFormat.BRIEF,
    )
    print(f"  ✅ Audio generation started: {audio_id}")
    print("  Polling for completion...")
    status = client.artifacts.wait_for_completion(nb_id, audio_id, poll_interval=5, timeout=120)
    print(f"  Status: {status}")

    # ─── Artifacts: Study Guide ────────────────────
    separator("Artifact — Study Guide (Report)")
    guide_id = client.artifacts.generate_study_guide(nb_id, language="en")
    print(f"  ✅ Study guide started: {guide_id}")

    # ─── Artifacts: Quiz ──────────────────────────
    separator("Artifact — Quiz")
    quiz_id = client.artifacts.generate_quiz(
        nb_id,
        quantity=QuizQuantity.STANDARD,
        difficulty=QuizDifficulty.MEDIUM,
    )
    print(f"  ✅ Quiz started: {quiz_id}")

    # ─── Artifacts: Infographic ───────────────────
    separator("Artifact — Infographic")
    info_id = client.artifacts.generate_infographic(
        nb_id,
        orientation=InfographicOrientation.PORTRAIT,
        detail=InfographicDetail.STANDARD,
        style=InfographicStyle.PROFESSIONAL,
    )
    print(f"  ✅ Infographic started: {info_id}")

    # ─── Artifacts: Slide Deck ─────────────────────
    separator("Artifact — Slide Deck")
    slides_id = client.artifacts.generate_slide_deck(
        nb_id,
        slide_format=SlideDeckFormat.DETAILED_DECK,
        length=SlideDeckLength.DEFAULT,
    )
    print(f"  ✅ Slide deck started: {slides_id}")

    # ─── List All Artifacts ───────────────────────
    separator("Artifacts — List All")
    all_artifacts = client.artifacts.list(nb_id)
    print(f"  Total artifacts: {len(all_artifacts)}")

    # ─── Research ─────────────────────────────────
    separator("Research — Fast Research")
    outcome = client.research.run_and_import(
        nb_id,
        query="Latest AI breakthroughs in 2025",
        deep=False,
        poll_interval=5,
        timeout=120,
    )
    print(f"  Research outcome: {outcome}")

    # ─── Notebook Configuration ───────────────────
    separator("Notebook — Configure Chat")
    client.notebooks.configure_chat(
        nb_id,
        goal=ChatGoal.LEARNING_GUIDE,
        response_length=ChatResponseLength.LONGER,
    )
    print("  ✅ Chat mode set to: Learning Guide, Longer responses")

    # ─── Cleanup ──────────────────────────────────
    separator("Cleanup")
    confirm = input(f"  Delete demo notebook '{nb_id}'? [y/N]: ")
    if confirm.strip().lower() == "y":
        client.notebooks.delete(nb_id)
        print("  ✅ Notebook deleted.")
    else:
        print("  Skipped deletion. Notebook preserved.")

    separator("Demo Complete!")


if __name__ == "__main__":
    try:
        main()
    except RateLimitError:
        print("\n⚠️  Rate limited by Google. Wait a few minutes and try again.")
    except RPCError as e:
        print(f"\n❌ RPC Error [{e.method_id}]: {e}")
    except KeyboardInterrupt:
        print("\n\nInterrupted by user.")
