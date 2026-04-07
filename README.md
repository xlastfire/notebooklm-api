# NotebookLM Python API Wrapper

An unofficial, synchronous Python API wrapper for Google's NotebookLM. This library allows you to programmatically manage notebooks, upload sources (files, URLs, Google Drive), generate smart artifacts (Podcasts, Videos, FAQs, Study Guides), conduct Deep Research, and chat with your documents.

It reverse-engineers the inner `batchexecute` RPC mechanisms of NotebookLM, wrapping them into a clean, intuitive, and strongly-typed Python interface.

## ⚠️ Disclaimer
**This is an unofficial, reverse-engineered wrapper.** It is not affiliated with, endorsed by, or supported by Google. It relies on internal APIs (`batchexecute`) which are subject to change without notice. Use carefully and responsibly, as Google may throttle or block accounts aggressively exhibiting programmatic or bot-like behavior.

---

## 📦 Installation

*(This package is not currently published on PyPI. You must install it from source)*

```bash
git clone https://github.com/xlastfire/notebooklm-api.git
cd notebooklm-api
pip install -e .
# Alternatively, you can drop the `notebooklm` folder directly into your project.
```

### Dependencies
- `requests`

---

## 🔑 Authentication (Cookies)

Because Google does not expose a public API or OAuth scope for NotebookLM, this wrapper requires you to inject your live browser cookies to authenticate.

1. Install a browser extension like **[Get cookies.txt LOCALLY](https://chrome.google.com/webstore/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpgnnhmhlida)**.
2. Log in directly to [notebooklm.google.com](https://notebooklm.google.com).
3. Export your cookies for that domain.
4. Save the cookies into a JSON dictionary format.

**Example `accounts.json` setup:**
```json
{
  "your.email@gmail.com": {
    "__Secure-1PSID": "g.a00...",
    "SID": "...",
    "HSID": "..."
  }
}
```

---

## 🚀 Quick Start

Here is a simple example that creates a Notebook, uploads a Wikipedia article, and asks a chat question:

```python
import json
from notebooklm.client import NotebookLMClient

# 1. Load your extracted cookies
with open("accounts.json", "r") as f:
    cookies = json.load(f)["your.email@gmail.com"]

# 2. Initialize the client (Synchronous & Blocking)
client = NotebookLMClient(cookies)

# 3. Create a new Notebook
notebook = client.notebooks.create("History Research")
nb_id = notebook["id"]
print(f"Created Notebook: {notebook['title']}")

# 4. Add a web URL as a source
client.sources.add_url(nb_id, "https://en.wikipedia.org/wiki/Roman_Empire")

# 5. Chat with the source!
response = client.chat.ask(nb_id, "What caused the fall of the Roman Empire?")
print("NotebookLM:", response)
```

---

## 📖 Feature Guide

### Managing Notebooks
```python
# List all notebooks
notebooks = client.notebooks.list()

# Get a specific notebook's settings (like chat prompt configurations)
config = client.notebooks.get_chat_config(nb_id)

# Delete a notebook
client.notebooks.delete(nb_id)
```

### Managing Sources
NotebookLM supports URLs, Raw Text, local Files, and Google Drive files.

```python
# Add standard URL
client.sources.add_url(nb_id, "https://example.com/article")

# Upload a local file (e.g. PDF, TXT)
client.sources.upload_file(nb_id, "data/financial_report.pdf")

# Check the sync/processing status of sources
sources = client.sources.list(nb_id)
for src in sources:
    print(f"Source: {src['title']} - Status: {src['status']}")
```

### 🎧 Generating Audio Podcasts
Generate deeply insightful conversational podcasts.

```python
from notebooklm.rpc.types import AudioFormat, AudioLength

# Generate the Podcast
artifact_id = client.artifacts.generate_audio(
    nb_id,
    language="en", 
    instructions="Focus exclusively on the philosophical metaphors."
)

# -> Important Note on Audio Downloading (Read the Known Issues section!)
raw_url = client.artifacts.get_audio_url(nb_id, artifact_id)

# Play or save it natively via your browser:
import webbrowser
webbrowser.open(raw_url)
```

### Artifact Generation (Video, Quiz, Timeline, Briefings)
You can utilize advanced Studio tools.
```python
# Create a Multi-Question Quiz based on your sources
quiz_id = client.artifacts.generate_quiz(nb_id)

# Generate an Executive Briefing Report
report_id = client.artifacts.generate_report(nb_id)

# Poll until the artifact is generated and parse the data!
parsed = client.artifacts.list_parsed(nb_id)
```

### Advanced Research
Trigger the asynchronous Deep Research pipeline.
```python
# Quick Fast-Research
client.research.fast_research(nb_id, query="Summarize the core themes")

# Deep Research (saves findings sequentially to a new Note)
research_id = client.research.deep_research(nb_id, query="Analyze the economic impact.")
status = client.research.get_status(nb_id, research_id)
print(status["response"]) # See the deep research insights
```

---

## 🚫 Known Issues & Limitations

1. **Programmatic Podcast/MP3 Downloads Are Blocked:**  
   Google aggressively protects their `lh3.googleusercontent.com` media endpoints against automated bots. The `requests` library will cleanly interface with the primary NotebookLM API, but attempting to use `requests.get()` on the final audio `.mp3`/`.wav` securely will trigger Google's silent re-authentication redirect (`accounts.google.com/ServiceLogin`), which returns an unplayable HTML login page instead of the audio file.
   * **The Solution:** Use `client.artifacts.get_audio_url(nb_id, art_id)` to extract the raw media URL, and open it automatically in your authenticated OS browser using `import webbrowser; webbrowser.open(url)`.

2. **Session / CSRF Expiration:**  
   Your browser cookies (particularly `__Secure-1PSID` and `SID`) must remain valid. If your script begins throwing `AuthError` or `401 Unauthorized` during initialization, you must re-export fresh cookies from your browser.

3. **Rate Limiting:**  
   Be polite. Google actively throttles or bans accounts making high-volume, rapid overlapping RPC requests. Limit intense artifact generation commands.

---

## 📂 Project Structure
```text
notebooklm-api/
├── notebooklm/
│   ├── __init__.py          # Main entrypoint
│   ├── client.py            # NotebookLMClient class
│   ├── core.py              # Requests Session & CSRF handling
│   ├── exceptions.py        # Library exceptions
│   ├── api_notebooks.py     # Notebooks CRUD methods
│   ├── api_artifacts.py     # Audio/Video/Quiz generations
│   ├── api_chat.py          # Chat generation
│   ├── api_sources.py       # File/URL uploading
│   ├── api_research.py      # Automated deep research logic
│   └── rpc/                 # Internal Google `batchexecute` decoder/encoder
├── demo.py                  # Extensive code examples
├── test_download.py         # Podcast download demonstration
└── README.md
```

## 🤝 Contributing
Since this library interacts with an undocumented, unofficial API, some components may break unexpectedly if Google updates their systems. For instance, **downloading audio artifacts programmatically currently faces strict Google bot-protection errors** (as detailed in Known Issues).

If you find workarounds for these issues or discover new API methods, **Pull Requests and Issues are highly welcome!** Let's build a robust open-source tool for NotebookLM together.

## 🙏 Acknowledgements
This library was developed entirely with the assistance of AI, with the overarching goal of making NotebookLM's capabilities more accessible and developer-friendly.

It builds heavily upon the foundational reverse-engineering work from the original [notebooklm-py](https://github.com/teng-lin/notebooklm-py) repository by teng-lin. Much credit goes to them for exposing the underlying `batchexecute` mechanisms.

## ⚖️ License
Released under the MIT License.
