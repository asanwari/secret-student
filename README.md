---
title: Secret Student
emoji: "\U0001F30D"
colorFrom: purple
colorTo: gray
sdk: docker
app_port: 7860
pinned: false
license: mit
short_description: "A Pokemon-inspired, local-first AI school adventure"
tags:
  - track:backyard
  - track:wood
  - sponsor:openbmb
  - sponsor:openai
  - sponsor:nvidia
  - sponsor:modal
  - achievement:offgrid
  - achievement:offbrand
  - achievement:llama
  - achievement:sharing
  - achievement:fieldnotes
---

<div align="center">

# Secret Student

### A Pokemon-inspired AI school game built for a niece who loves games and hates school

[![Build Small: Backyard](https://img.shields.io/badge/Build_Small-Backyard_Adventure-6d28d9)](https://huggingface.co/build-small-hackathon)
[![Build Small: Woods](https://img.shields.io/badge/Build_Small-Deploy_to_the_Woods-166534)](https://huggingface.co/build-small-hackathon)
[![Live Space](https://img.shields.io/badge/Play-Live_Space-fbbf24?logo=huggingface&logoColor=black)](https://huggingface.co/spaces/asanwari/secret-student)
[![Source](https://img.shields.io/badge/Source-GitHub-181717?logo=github)](https://github.com/asanwari/secret-student)
[![llama.cpp](https://img.shields.io/badge/Inference-llama.cpp-2563eb)](https://github.com/ggml-org/llama.cpp)

**Learn at school. Get briefed by Grandma. Defeat a villain with what you learned.**

</div>

Secret Student turns an AI-generated lesson into a retro 2D mission. The player
is a student by day and a secret agent after class. Lessons become intelligence,
quizzes become training, and the final assessment becomes a boss battle.

The whole AI stack can run locally through two small GGUF models and llama.cpp.
There is no required cloud model API, and the custom Phaser interface looks and
plays like a game rather than a default chatbot.

## Hackathon Submission

Secret Student is submitted to **both** [Build Small](https://huggingface.co/build-small-hackathon)
tracks:

> [!IMPORTANT]
> **The working AI demo is the personal NVIDIA-backed Space:**
> **[asanwari/secret-student](https://huggingface.co/spaces/asanwari/secret-student)**.
> The required organization submission is
> **[build-small-hackathon/secret-student](https://huggingface.co/spaces/build-small-hackathon/secret-student)**,
> but that organization Space cannot currently provision a GPU. It mirrors the
> same source and serves as the official submission artifact; use the personal
> Space above to test the complete Qwen3 plus MiniCPM-V experience.

## Judges: Inference and GPU Setup

> [!CAUTION]
> **Please read this before evaluating latency.** The organization submission is
> currently configured as a CPU-hosted game that calls two Modal GPU endpoints.
> Modal scales those endpoints down when idle, so the first lesson or handwritten
> answer after an idle period can be **significantly slower while the GPU starts
> and the GGUF model is loaded**. This is cold-start latency, not the normal warm
> inference path. The application was deliberately built so the same Space can
> instead run both models locally with only environment changes.

### Recommended Evaluation Setup: One L4 Space GPU

The Docker image already includes CUDA-enabled llama.cpp, and `app.runtime`
already knows how to launch and health-check separate text and vision servers.
No code changes or additional inference service are required.

1. Assign an **NVIDIA L4** to the Space.
2. In **Settings -> Variables and secrets**, replace the external runtime
   configuration with the values below.
3. Perform a **Factory Restart**. On the first boot, allow time for the model
   downloads unless the GGUF files have already been placed in persistent
   `/data/models` storage.

**Variables:**

```text
LLM_RUNTIME=embedded_dual_llamacpp
LLM_PROVIDER=openai_compatible

LLM_MODEL=Qwen/Qwen3-8B-GGUF:Q4_K_M
LLAMA_CPP_MODEL_REF=Qwen/Qwen3-8B-GGUF:Q4_K_M
LLAMA_CPP_CTX_SIZE=8192
LLAMA_CPP_GPU_LAYERS=999
LLAMA_CPP_THREADS=8
LLAMA_CPP_PARALLEL=1
LLAMA_CPP_STARTUP_TIMEOUT=900

VISION_LLM_MODEL=openbmb/MiniCPM-V-4_5-gguf:Q4_K_M
VISION_LLAMA_CPP_MODEL_REF=openbmb/MiniCPM-V-4_5-gguf:Q4_K_M
VISION_LLAMA_CPP_CTX_SIZE=4096
VISION_LLAMA_CPP_GPU_LAYERS=999
VISION_LLAMA_CPP_PORT=8002
```

**Secrets:**

Secrets are already set and don't need to be touched.

If the Space does not have preloaded model files, **delete**
`LLAMA_CPP_MODEL_PATH`, `VISION_LLAMA_CPP_MODEL_PATH`, and
`VISION_LLAMA_CPP_MMPROJ_PATH` from its variables. Their absence tells the
runtime to download the configured GGUF repositories through llama.cpp. For
faster restarts with persistent storage, preload the files and set:

```text
LLAMA_CPP_MODEL_PATH=/data/models/qwen3-8b/Qwen3-8B-Q4_K_M.gguf
VISION_LLAMA_CPP_MODEL_PATH=/data/models/minicpm-v-4_5/MiniCPM-V-4_5-Q4_K_M.gguf
VISION_LLAMA_CPP_MMPROJ_PATH=/data/models/minicpm-v-4_5/mmproj-model-f16.gguf
```

`LLM_BASE_URL`, `VISION_LLM_BASE_URL`, `LLM_API_KEY`, and
`VISION_LLM_API_KEY` belong to the current Modal configuration. They are ignored
by `embedded_dual_llamacpp` and may be removed when switching to local Space
inference.

### Configurability Built Into the Project

| Area | Configuration |
| --- | --- |
| Inference topology | `mock`, one external endpoint, one embedded llama.cpp server, or independent embedded text and vision servers via `LLM_RUNTIME` |
| Model selection | Text and vision model IDs, GGUF repositories, local file paths, and the MiniCPM-V projector are independent environment variables |
| Hosting | One Docker Space, two Modal endpoints, another OpenAI-compatible service, local NVIDIA Docker, or consumer hardware running llama.cpp |
| Performance | Context size, GPU layers, CPU threads, parallel slots, ports, startup timeout, and arbitrary extra llama.cpp arguments are configurable independently |
| Storage | Models may download from the Hub at startup or load from persistent `/data/models`; SQLite progress and traces can also use `/data` |
| Educational flow | Quiz count, boss-question count, maximum mistakes, and model thinking mode are environment-controlled |
| Observability | Traces can be disabled, written locally, or uploaded in redacted form to a public or private Hub dataset |

The repository includes `set_env_for_space.py` to apply either topology in one
command. Full model-preloading, Modal, Docker Compose, and trace instructions are
in the [Technical Guide](docs/TECHNICAL.md).

| Track | How Secret Student qualifies |
| --- | --- |
| **Backyard Adventure** | The [actual public demo](https://huggingface.co/spaces/asanwari/secret-student) runs as a Docker Space on a persistent NVIDIA GPU, with the application and both llama.cpp servers in one deployment. The organization-owned submission mirrors the same code but currently lacks permission to provision GPU hardware. |
| **Deploy to the Woods** | The text and vision models are small, quantized GGUFs that run on consumer hardware. Each model is well below the track's 32B-parameter ceiling. |

The application can also separate the CPU-hosted game from inference. In
`external` mode, independent OpenAI-compatible endpoints can be assigned to the
text and vision roles through `LLM_BASE_URL` and `VISION_LLM_BASE_URL`. The
included Modal llama.cpp server can therefore be deployed twice, once for
Qwen3-8B and once for MiniCPM-V, if organization GPU access remains unavailable.

### Submission Links

| Artifact | Link |
| --- | --- |
| **Actual GPU demo** | **[Play the complete application at asanwari/secret-student](https://huggingface.co/spaces/asanwari/secret-student)** |
| Organization submission | [build-small-hackathon/secret-student](https://huggingface.co/spaces/build-small-hackathon/secret-student) - repository mirror; organization GPU provisioning is unavailable |
| Source code | [github.com/asanwari/secret-student](https://github.com/asanwari/secret-student) |
| Codex development history | [Main commit history](https://github.com/asanwari/secret-student/commits/main/) and [`codex/*` branches](https://github.com/asanwari/secret-student/branches/all) |
| Field notes | [I Built a Pokemon-Inspired AI School Game for My Niece](https://medium.com/@asanwari/i-built-a-pokemon-inspired-ai-school-game-for-my-niece-986ad1df69f6) |
| Demo video | [Watch the Secret Student gameplay demo on YouTube](https://youtu.be/sOw0Z8YGeNs?si=F449Jw-N1M8PakhA) |
| LinkedIn post | [Secret Student launch post on LinkedIn](https://www.linkedin.com/posts/asanwari_i-am-excited-to-share-the-ai-based-game-i-share-7472059176928673792-NtpK/?utm_source=share&utm_medium=member_desktop&rcm=ACoAABLvphoBYCEHypneAStkPtmp_zXb5crlagM) |
| Open LLM traces | [Secret Student LLM traces on Hugging Face](https://huggingface.co/datasets/asanwari/secret-student-llm-traces) |

> The `achievement:welltuned` tag is intentionally not claimed: the current
> models are configurable base models, not a fine-tuned model published by this
> project.

## The Game

1. **Create your agent.** Choose a student name, secret codename, grade, and the
   hair, shirt, and pants colors for the backpack-wearing character.
2. **Go to school.** Pick a topic and receive a structured, age-appropriate
   lesson generated for that student.
3. **Ask the teacher.** Follow-up chat stays grounded in the current lesson.
4. **Take the quiz.** Type an answer or draw it in the notebook. Feedback remains
   visible until the player chooses to continue.
5. **Return home.** Review material at the desk, then answer the secret phone for
   a comic-style briefing from the handler known only as **Grandma**.
6. **Enter headquarters.** Fight a villain by answering harder questions based
   on the lesson. Correct answers damage the boss; mistakes cost health.
7. **Start another mission.** Return to the map and learn something new.

<table>
  <tr>
    <td width="50%"><img src="frontend/static/assets/classroom-blank.png" alt="Pixel-art Secret Student classroom"></td>
    <td width="50%"><img src="frontend/static/assets/bedroom-agent.png" alt="Pixel-art Secret Student bedroom"></td>
  </tr>
  <tr>
    <td align="center"><strong>School: lessons, teacher chat, and quizzes</strong></td>
    <td align="center"><strong>Home: review and mission briefings</strong></td>
  </tr>
</table>

## Small Models, Separate Jobs

```mermaid
flowchart LR
    P[Player] --> UI[Custom Phaser game]
    UI --> API[FastAPI game API]
    API --> DB[(SQLite progress)]
    API -->|Lessons, chat, typed grading| TEXT[Qwen3-8B GGUF]
    API -->|Handwriting only| VISION[MiniCPM-V 4.5 GGUF]
    TEXT --> L1[llama.cpp text server]
    VISION --> L2[llama.cpp vision server]
    L1 --> TRACE[Validated traces]
    L2 --> TRACE
```

One approximately 8B text model handles lesson generation, teacher chat,
question creation, and typed-answer grading. A separate OpenBMB MiniCPM-V model
is called only when pixels need to become an answer. Both are quantized and
served by llama.cpp through OpenAI-compatible local endpoints.

This split keeps the common path fast and leaves vision work to a model designed
for it. Model repositories, files, ports, context sizes, and GPU layers are all
environment-configurable; Qwen and MiniCPM-V are defaults, not hard dependencies.

The default pair is comfortable on a 16 GB NVIDIA GPU with conservative context
settings. Practical consumer options include the RTX 4060 Ti 16 GB, RTX 4070 Ti
SUPER 16 GB, RTX 4080 16 GB, and RTX 3090/4090 24 GB. Partial CPU offload can
reduce VRAM requirements at the cost of latency. The hosted demo uses NVIDIA GPU
infrastructure for additional headroom.

## Reliable Generated Content

The model never writes directly into the game. Secret Student treats every
completion as untrusted input:

```mermaid
flowchart LR
    A[Prompt + JSON Schema] --> B[Model completion]
    B --> C[Extract and parse JSON]
    C --> D[Normalize safe aliases]
    D --> E[Pydantic + content rules]
    E -->|Valid| F[Persist lesson]
    E -->|Invalid| G[Repair prompt with exact errors]
    G --> H[Validate again]
    H -->|Valid| F
    H -->|Invalid| I[Fail with trace ID]
```

The validation layer enforces six to ten progressive lesson steps, a 150-word
limit per step, concrete expected answers, exact question counts, and no
references to unavailable maps, images, videos, or worksheets. Common JSON
formatting damage is repaired locally. Deeper schema or content failures are
sent back to the model with the exact validation errors for one constrained
self-correction pass. Only a valid result is saved.

Every model call can produce a durable trace containing timing, parsing,
normalization, validation, repair, and final status. Secrets are redacted and
image payloads are replaced with hashes.

## Sponsor Stack

| Sponsor | Role in the project |
| --- | --- |
| [![NVIDIA](https://img.shields.io/badge/NVIDIA-GPU_Inference-76B900?logo=nvidia&logoColor=white)](https://www.nvidia.com/) | NVIDIA GPU hardware runs the public dual-model Space and CUDA-accelerated llama.cpp. NVIDIA Nemotron 3 Nano Omni GGUF was also evaluated as a candidate for the unified text-and-vision deployment before the project adopted its current two-model architecture. |
| [![Modal](https://img.shields.io/badge/Modal-Optional_GPU_Deployment-111111)](https://modal.com/) | The repository includes a configurable Modal deployment for an external OpenAI-compatible llama.cpp server with persistent model caching. |
| [![OpenBMB](https://img.shields.io/badge/OpenBMB-MiniCPM--V-7c3aed)](https://huggingface.co/openbmb) | MiniCPM-V is the vision specialist used to read and grade handwritten answers. |
| [![OpenAI](https://img.shields.io/badge/OpenAI-Codex_Assisted-000000?logo=openai&logoColor=white)](https://openai.com/codex/) | Codex was the coding collaborator throughout implementation, testing, responsive UI work, model infrastructure, and documentation. The evidence is visible in the public commits and `codex/*` branches. |

## Achievement Evidence

| Achievement | Evidence |
| --- | --- |
| **Off the Grid** | Embedded llama.cpp modes run the complete model workflow without a cloud model API. |
| **Off-Brand** | A custom HTML/CSS/JavaScript and Phaser frontend is hosted through Gradio, with original pixel-art scenes and game controls. |
| **Llama Champion** | Both text and vision models are served through pinned llama.cpp CUDA images. |
| **Field Notes** | The public [Medium build report](https://medium.com/@asanwari/i-built-a-pokemon-inspired-ai-school-game-for-my-niece-986ad1df69f6) covers the product idea, architecture, validation, hardware, and lessons learned. |
| **Sharing is Caring** | The public [Secret Student LLM trace dataset](https://huggingface.co/datasets/asanwari/secret-student-llm-traces) exposes the model-call lifecycle, including validation, repair, timing, and final status. Sensitive values and image payloads are redacted by the application before upload. |
| **Well-Tuned** | Not claimed. A project-owned fine-tuned model has not been published. |

## Built for the Judging Criteria

- **Technical implementation:** two specialized local models, explicit routing,
  validated structured generation, model-assisted repair, durable traces,
  persistence, and responsive desktop/tablet controls.
- **Model choice and use:** an 8B text model handles language-heavy work while
  MiniCPM-V is invoked only for handwriting. Game rules remain deterministic
  application code rather than being delegated to the models.
- **Creativity:** the lesson, quiz, home briefing, and boss fight form one coherent
  Pokemon-inspired adventure instead of a chatbot wrapped in educational copy.

## Run Locally

The fastest local preview uses deterministic mock content:

```bash
uv sync
cp .env.example .env
LLM_RUNTIME=mock uv run uvicorn main:app --reload --host 0.0.0.0 --port 7860
```

Open `http://127.0.0.1:7860`.

For the full dual-model setup, Hugging Face Space configuration, Modal
deployment, model preloading, tracing, API routes, and tests, see
**[Technical Guide](docs/TECHNICAL.md)**.

## Project Links

- [Live Hugging Face Space](https://huggingface.co/spaces/asanwari/secret-student)
- [GitHub source and Codex-assisted history](https://github.com/asanwari/secret-student)
- [Technical guide](docs/TECHNICAL.md)
- [Medium field notes](https://medium.com/@asanwari/i-built-a-pokemon-inspired-ai-school-game-for-my-niece-986ad1df69f6)
- [Public LLM trace dataset](https://huggingface.co/datasets/asanwari/secret-student-llm-traces)
- [Qwen3-8B GGUF](https://huggingface.co/Qwen/Qwen3-8B-GGUF)
- [OpenBMB MiniCPM-V 4.5 GGUF](https://huggingface.co/openbmb/MiniCPM-V-4_5-gguf)
- [llama.cpp](https://github.com/ggml-org/llama.cpp)
