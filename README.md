# Secret Student

Secret Student is a Gradio-hosted retro learning game for the Hugging Face Build Small Hackathon. A player registers as a school kid with a secret identity, learns a topic at school, gets a mission call at home, and fights a boss at `{player_name}'s Grandma's House`.

The app uses a custom Phaser frontend embedded in a Gradio shell, with FastAPI routes for game data and a SQLite database for persistence.

## Run Locally

```bash
uv sync
cp .env.example .env
LLM_PROVIDER=mock uv run uvicorn main:app --reload --host 0.0.0.0 --port 7860
```

Open:

```text
http://127.0.0.1:7860
```

To open the game from another device on the same Wi-Fi network, use the
laptop's local network address instead, for example:

```text
http://192.168.1.123:7860
```

The address may change when the laptop reconnects to Wi-Fi. On macOS, find it
under System Settings > Wi-Fi > Details > TCP/IP, or run `ifconfig en0`.

Mock mode is fully playable without a model endpoint.

## Model Configuration

The backend expects an OpenAI-compatible chat completions endpoint when using a local or hosted model server:

```bash
LLM_PROVIDER=openai_compatible
LLM_BASE_URL=http://127.0.0.1:8001
LLM_API_KEY=
LLM_MODEL=openbmb/MiniCPM-V-4.6
```

The lesson generator requests structured JSON and parses it into Pydantic classes. Text and numeric answers are checked deterministically first. Drawn answers are sent to the vision model only when the player submits notebook handwriting.

## LLM Traces

Every OpenAI-compatible model call records its request, full response, parse or
repair step, schema validation, timing, and final status. For local debugging:

```bash
TRACE_DESTINATION=local
TRACE_DIR=debug_traces
```

Failed API responses include a trace ID. Find the matching JSON file under
`debug_traces/`; malformed model JSON is retained there before any automatic
repair is attempted. Image data is replaced by a hash and API keys are never
written to traces.

To publish completed traces to a Hugging Face dataset repository instead:

```bash
TRACE_DESTINATION=hub
TRACE_HUB_REPO_ID=your-name/secret-student-traces
TRACE_HUB_TOKEN=hf_your_write_token
TRACE_HUB_PRIVATE=true
TRACE_HUB_INCLUDE_CONTENT=false
```

Hub traces remove the internal user ID. Prompts and raw completions are also
removed unless `TRACE_HUB_INCLUDE_CONTENT=true`; review traces carefully before
enabling that option, especially when testing with real learners.

## Key Routes

- `POST /api/auth/register`
- `POST /api/auth/login`
- `GET /api/me`
- `POST /api/lesson/start`
- `GET /api/lesson/{lesson_id}`
- `POST /api/lesson/{lesson_id}/ask`
- `POST /api/quiz/submit`
- `POST /api/boss/start`
- `POST /api/boss/submit`
- `POST /api/state/location`

## Tests

```bash
uv run pytest
```

## Hugging Face Space

Use the Docker Space runtime or run:

```bash
uv run uvicorn main:app --host 0.0.0.0 --port 7860
```

The Gradio root embeds `/game`, which serves the custom Phaser app. Static files are under `frontend/static`.
