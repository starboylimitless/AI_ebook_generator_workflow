# Chess Academy AI Workflow

Automated multi-agent workflow to convert a raw chess ebook into a professionally designed ebook, using a reference PDF as a style guide.

## Project Structure

- `chess_academy_ai_workflow/`
  - `input_docs/` — input PDFs (`ebook_ads.pdf`, `next_move_reference.pdf`)
  - `agents/` — multi-agent implementations
  - `workflows/` — master agent and workflow controller
  - `prompts/` — prompt templates for each agent
  - `utils/` — shared utilities (PDF, logging, LLM client)
  - `output/` — intermediate JSON outputs and final ebook
- `main.py` — entrypoint to run the full pipeline
- `requirements.txt` — Python dependencies

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Set your OpenAI API key:

```powershell
$env:OPENAI_API_KEY="YOUR_KEY_HERE"
```

Place the following files in `chess_academy_ai_workflow/input_docs/`:

- `ebook_ads.pdf` — raw content source
- `next_move_reference.pdf` — style and layout reference

## Run

```bash
python main.py
```

The final formatted ebook and intermediate artifacts will be written to `chess_academy_ai_workflow/output/`.

