# Splunk ↔ GPU inference research

Date: 2026-05-24

## Local facts verified

- GPU host: `gpu-host`
- GPU: NVIDIA GeForce RTX 3090, driver `595.58.03`, `24576 MiB` VRAM
- Docker: installed (`Docker version 29.4.3`) with `nvidia` runtime present
- Splunk host via MCP: `workbox`, Splunk Enterprise `10.2.3`, Linux x86_64, 4 cores, ~15.5 GB RAM, KV Store ready, health green
- Current Splunk app inventory does **not** show Splunk AI Toolkit, MLTK, PSC, or DSDL installed
- No local Ollama/vLLM Python stack is currently installed/running on `gpu-host` at the checked ports

## What Splunk can do officially

### 1. AI Toolkit `ai` command → external LLM endpoint

Splunk AI Toolkit documents an `ai` ML-SPL command that sends Splunk search data to externally hosted LLM providers and returns the result into the SPL pipeline. Supported providers include Ollama, OpenAI, Azure OpenAI, Anthropic, Gemini, Bedrock, and Groq.

Docs: https://help.splunk.com/en/splunk-enterprise/apply-machine-learning/use-ai-toolkit/5.7.2/ai-toolkit-commands-macros-and-visualizations/about-the-ai-command

Key constraints:

- Requires AI Toolkit, currently not installed here.
- Data is sent to an external service; for this lab, that could be a LAN-local Ollama/vLLM endpoint on `gpu-host`.
- Splunk warns that the command is risky, can trigger SPL safeguards, has no built-in input inspection, and returns unguarded LLM output.
- Good for analyst summarization/explanation after a detector flags windows.
- Not ideal as the first TamperGuard detector over raw live logs.

### 2. AI Toolkit ONNX upload/apply

AI Toolkit 5.4+ supports uploading externally trained ONNX models and using `apply onnx:<model>` or `apply app:onnx:<model>` from SPL.

Docs: https://help.splunk.com/en/splunk-cloud-platform/apply-machine-learning/use-ai-toolkit/5.7.3/ai-toolkit-models/upload-and-inference-pre-trained-onnx-models-in-the-ai-toolkit

Key constraints:

- Requires AI Toolkit 5.4+ and compatible Python for Scientific Computing add-on.
- Requires upload capabilities such as `upload_lookup_files` and `upload_onnx_model_file`.
- Upload/runtime constraints matter; the model is stored as a lookup-backed artifact.
- Runs inference inside Splunk’s ML command path, not directly on this RTX 3090 unless Splunk/AI Toolkit runtime is actually connected to a GPU-capable environment.
- Good future path for compact models; not available in the current installed Splunk app set.

### 3. DSDL / MLTKContainer → Docker/Kubernetes/OpenShift GPU containers

Splunk App for Data Science and Deep Learning (DSDL) is the official Splunk path for offloading heavier ML/DL work to external containers. Splunk docs describe DSDL connecting Splunk to Docker, Kubernetes, or OpenShift containers, with endpoint URLs for bidirectional data transfer between Splunk and container algorithms.

Docs:

- Architecture: https://help.splunk.com/en/splunk-enterprise/apply-machine-learning/use-splunk-app-for-data-science-and-deep-learning/5.2.0/about-the-splunk-app-for-data-science-and-deep-learning/splunk-app-for-data-science-and-deep-learning-architecture
- Container management/scaling: https://docs.splunk.com/Documentation/DSDL/5.2.2/User/ContainerManagement
- GPU support: https://help.splunk.com/en/splunk-cloud-platform/apply-machine-learning/use-splunk-app-for-data-science-and-deep-learning/5.1.0/deploy-the-splunk-app-for-data-science-and-deep-learning/using-multi-gpu-computing-for-heavily-parallelled-processing

Key constraints:

- Requires MLTK + PSC + DSDL app installation/configuration.
- Docker is mostly dev/test and commonly same-host as the search head; Kubernetes/OpenShift is the scalable/production pattern.
- GPU containers need NVIDIA runtime/GPU scheduling.
- For this lab, Splunk is on a thin client and the GPU is on `gpu-host`, so “official DSDL to GPU” likely means either:
  - run DSDL container environment remotely on `gpu-host`/Kubernetes and let Splunk reach it over LAN; or
  - move Splunk/search head to the GPU host, which we previously decided not to do for v0.
- This is valid, but probably too much moving machinery for v0.

### 4. Custom search command / scripted external lookup → local LAN GPU inference service

Splunk Developer docs support Python custom search commands using `splunklib.searchcommands`. A `StreamingCommand` can augment each search result as it travels through the SPL pipeline, and `@Configuration(local=True)` can force it to run only on the search head rather than indexers.

Docs: https://dev.splunk.com/enterprise/docs/devtools/customsearchcommands/pythonclassescustom/

Practical pattern:

```text
Splunk scheduled/relative search
→ feature window rows
→ custom SPL command or external lookup calls LAN-local inference API on gpu-host
→ command adds score/probability/summary fields
→ results written to lookup/summary index/alert
```

Key constraints:

- This is more custom code than AI Toolkit, but fewer Splunk app dependencies than DSDL.
- Need strict timeouts, batching, payload limits, retries, schema validation, and redaction.
- Avoid running this on real-time searches at first. Use scheduled searches every 1–5 minutes over recent windows.
- For V1, a simple REST microservice on `gpu-host` can score feature rows; Splunk only sees bounded feature data, not raw private logs.

### 5. External poller/service → Splunk REST search API + GPU inference + HEC back into Splunk

Splunk HEC officially supports sending JSON/application events into Splunk over HTTP/HTTPS with token auth.

Docs: https://help.splunk.com/en/splunk-enterprise/get-started/get-data-in/10.4/get-data-with-http-event-collector/set-up-and-use-http-event-collector-in-splunk-web

Practical pattern:

```text
GPU-host service on a schedule
→ call Splunk REST/MCP saved search for recent feature windows
→ run GPU inference locally
→ POST scores/explanations back to Splunk via HEC or lookup/REST
→ dashboards/alerts consume scored events
```

Key constraints:

- This is the least invasive Splunk-side path.
- It keeps GPU dependencies off the thin-client Splunk box.
- It works even without AI Toolkit/MLTK/DSDL.
- It is not “inside SPL” inference; Splunk orchestrates/receives results rather than executing the model.

## Live-data note

Splunk ML `fit`/`apply` docs say those commands work on relative-time searches but do not complete on real-time searches. For this lab, “live” should mean scheduled near-real-time windows, for example every 1 minute over `earliest=-5m@m latest=now`, not Splunk real-time search mode.

Docs: https://help.splunk.com/en/splunk-enterprise/apply-machine-learning/use-ai-toolkit/5.6.4/ai-toolkit-commands-macros-and-visualizations/about-the-fit-and-apply-commands

## Recommendation for V1 / V2 planning

This research is **not** meant to change the v0 path. v0 stays the no-ML-app, CPU-safe, deterministic SPL-scoring smoke test.

For a potential V1 or V2, the right question is: how much of the inference loop should Splunk own versus how much should live in a GPU service adjacent to Splunk?

### V1 candidate: GPU inference service beside Splunk

Use an external GPU inference service on `gpu-host`, called by a scheduled Splunk workflow or by a GPU-host poller, with results returned to Splunk.

Possible V1 shape:

```text
Splunk workbox
  scheduled saved search builds actor_60m / actor_5m feature rows
  → either exports via REST to gpu-host poller OR invokes a custom command

gpu-host RTX 3090
  FastAPI / Ollama / vLLM / PyTorch inference service
  batch scores rows or summarizes bounded evidence bundles
  returns score/probability/model_version/evidence_summary

Splunk workbox
  indexes/scans scored results in `soc_summary` or `ai_tamperguard` lookup/summary index
  alert/dashboard reads those scored rows
```

Why this is probably the best V1 bridge:

- Keeps Splunk stable on the thin client.
- Uses the RTX 3090 without moving Splunk.
- Avoids making V1 depend on AI Toolkit/MLTK/DSDL installation success.
- Supports richer models than v0 while keeping Splunk as the operational system of record.
- Makes claim boundaries clean: Splunk orchestrates and stores evidence; the GPU service performs inference.

### V2 candidate: Splunk-native ML/LLM integration

If the goal becomes “Splunk itself should manage the ML/LLM runtime,” install/configure AI Toolkit + PSC + possibly DSDL, then choose:

1. `ai` command + Ollama/vLLM-compatible local endpoint on `gpu-host` for LLM summarization;
2. DSDL + GPU Docker/Kubernetes for heavier model inference/training; or
3. ONNX upload/apply for compact third-party-trained models.

This is more Splunk-native, but it adds app/runtime dependency risk. Treat it as V2 unless V1 explicitly needs Splunk-managed ML commands.

## Security guardrails

- Send feature windows or synthetic/evidence summaries to the GPU service, not raw `_raw` logs by default.
- Bind GPU inference service to LAN or localhost tunnel only; no internet exposure.
- Use a dedicated token/API key in local `.env`, never in repo docs.
- Use strict schema: required feature columns, max rows per request, max prompt/context length, timeout under Splunk scheduled-search limits.
- Add `model_version`, `scored_at`, `source_window_start`, `source_window_end`, and `inference_path` to every result.
- For LLM calls, treat output as analyst aid, not ground truth detection.

## Bottom line

Splunk can interface with the GPU on this machine in three viable ways:

1. **Official but heavier:** AI Toolkit/DSDL manages GPU-backed external containers.
2. **Official-ish LLM path:** AI Toolkit `ai` command calls LAN-local Ollama/vLLM on the RTX 3090.
3. **Pragmatic V1 bridge:** a GPU-host inference microservice or poller exchanges feature rows/results with Splunk via REST/HEC/custom command.

For AI TamperGuard V1, option 3 is the cleanest lobster ramp: fewer Splunk app dependencies, real GPU use, and less chance we spend two days debugging app plumbing instead of proving inference on live-ish windows. For V2, revisit option 1 or 2 if we specifically want Splunk-managed ML/LLM runtime ownership.
