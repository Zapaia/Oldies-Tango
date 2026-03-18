# Oldies Tango — Automated Video Factory

A multi-agent system that automatically generates vintage tango videos for YouTube. Combines AI agents (Claude API), audio/video processing, and automated publishing.

## What it does

The pipeline runs once a day and produces a `.mp4` video ready to upload to YouTube:

1. **Creative Director** (Claude API) → generates the video concept (`brief.json`)
2. **Music Agent** (Claude API) → generates a prompt to create music in Suno AI
3. **Visual Agent** (Claude API) → generates a prompt for the image in DALL-E
4. **[Manual]** Generate image in ChatGPT/DALL-E and audio in Suno.com
5. **Mixer** → blends music with ambient effects (rain, vinyl, café)
6. **Renderer** → combines image + audio → `video.mp4`
7. **Metadata Agent** (Claude API) → generates title, description and tags for YouTube
8. **Publisher Agent** → uploads the video to YouTube via API
9. **Notifier** → sends an email summary of the run (trace, costs, ContentID alerts)

All agents use **structured output via tool use** from the Anthropic API — no manual JSON parsing.

## Structure

```
src/
├── agents/
│   ├── creative_director.py   # Creative concept for the video
│   ├── music_agent.py         # Prompt for Suno AI
│   ├── visual_agent.py        # Prompt for DALL-E
│   ├── editor_agent.py        # Clip evaluation and selection
│   ├── metadata_agent.py      # Title, description, tags for YouTube
│   └── publisher_agent.py     # Uploads video to YouTube
├── core/
│   ├── settings.py            # Config and .env loading
│   ├── logger.py              # Structured JSON logging
│   ├── storage.py             # Per-run artifact management
│   ├── brief.py               # Brief data model
│   ├── tracer.py              # Per-run span tracing
│   ├── evaluator.py           # Objective + subjective evaluation (Claude Haiku)
│   ├── notifier.py            # Email summaries
│   └── youtube_stats.py       # Channel stats queries
├── media/
│   ├── audio/mixer.py         # Audio + ambient effects mixing
│   ├── image/thumbnail.py     # Video thumbnail
│   ├── image/mosaic.py        # Mosaic for compilations
│   └── video/renderer.py      # Final rendering (MoviePy + FFmpeg)
└── pipelines/
    ├── run_daily.py           # Main orchestrator
    └── compile_videos.py      # Generates multi-video compilations
configs/
├── pipeline.yaml              # General pipeline parameters
├── channels.yaml              # YouTube channel configuration
└── prompts/                   # Base prompts for each agent
```

## Setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

Requires **FFmpeg** installed and available in the system PATH.

### 2. Configure environment variables

Copy `.env.example` to `.env` and fill in:

```env
ANTHROPIC_API_KEY=sk-ant-...
GMAIL_USER=you@gmail.com
GMAIL_APP_PASSWORD=...
```

### 3. YouTube authentication (optional)

For automated publishing, add `youtube_client_secret.json` with OAuth credentials from Google Cloud Console (YouTube Data API v3).

### 4. Run the pipeline

```bash
python -m src.pipelines.run_daily
```

The pipeline automatically detects if manual files (image/audio) are missing and waits until they are available.

## Stack

| Component | Technology |
|---|---|
| AI Agents | Claude API (claude-sonnet-4-6) |
| Subjective evaluation | Claude Haiku (claude-haiku-4-5-20251001) |
| Image generation | DALL-E 3 (manual via ChatGPT) |
| Music generation | Suno AI (manual via web) |
| Video rendering | MoviePy + FFmpeg |
| Publishing | YouTube Data API v3 |
| Configuration | YAML + dotenv |
| Output format | JSON (per-run artifacts) |

## Cost

- **Anthropic API:** ~$0.09 per video
- **Total marginal cost:** near $0 if subscriptions (Suno, ChatGPT) are already paid

## Goal

A learning project for building real multi-agent systems end-to-end. Passive monetization via YouTube is a secondary objective.
