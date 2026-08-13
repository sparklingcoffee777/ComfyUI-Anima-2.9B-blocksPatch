# ComfyUI-Anima-2.9B-blocksPatch

**English** | [日本語](README.ja.md)

A load-time patch that lets ComfyUI correctly load depth-expanded Anima models (Anima-2.9B: 40 blocks). No workflow nodes are added.

## Status: still needed on released ComfyUI

ComfyUI merged a native fix on 2026-08-12 ([PR #15555](https://github.com/Comfy-Org/ComfyUI/pull/15555)) that derives the block count
from the state dict. As of this writing that commit is **only on `master`** — it landed
after the v0.32.0 release (2026-08-11) and is not in any tagged release yet.

So:

- **On a released ComfyUI build** (v0.32.0 or earlier, Desktop, portable): you still need
  this patch, or Anima-2.9B loads as a truncated 28-block model.
- **Tracking `master` directly**: the fix is already in, and you can skip this patch.

Its post-load verification has no upstream equivalent either — it fails the load loudly
rather than letting a truncated model through, which is useful if you build or expand
Anima checkpoints yourself.

## Why it is needed

ComfyUI does not count Anima's transformer blocks from the state dict; it hardcodes 28 blocks whenever `model_channels == 2048` (`comfy/model_detection.py`).

Anima-2.9B is a **block expansion (depth upscale)** of anima-base-v1.0 (28 blocks). Verified by direct weight comparison:

- All 28 original blocks are present bit-identically (max|diff| = 0)
- 12 new blocks were inserted at indices 2, 5, 8, 11, 14, 17, 21, 24, 27, 30, 33, 36
- Only `llm_adapter` was further trained

Without a patch, ComfyUI builds a 28-block model from the 40-block file **without any error** (weights load with `strict=False`) and runs inference with 12 blocks missing, silently producing broken output.

## Installation

1. Put this folder into `ComfyUI/custom_nodes/`
2. Restart ComfyUI

That's all. No extra pip installs, no workflow changes.

**Note: nothing appears in the node list (Add Node menu).** This patch takes effect automatically at startup; the startup log below is the only way to confirm it is active.

To uninstall, delete the folder or append `.disabled` to its name.

## How it works

1. Wraps `comfy.supported_models.Anima.get_model`
2. Counts the actual blocks in the state dict using ComfyUI's own `count_blocks()` and fixes `num_blocks` on that instance's private `unet_config` copy
3. After the model is built, verifies the constructed block count against the state dict. On mismatch it **raises a RuntimeError** so the load fails visibly instead of silently truncating

Regular 28-block Anima models are a complete no-op (not even a log line).

## Verifying it works

Startup log:

```
[Anima blocks patch] installed on comfy.supported_models.Anima.get_model (strict=True).
```

When loading 2.9B:

```
[Anima blocks patch] state dict has 40 transformer blocks, config said 28; patching num_blocks.
```

## Environment variables

| Variable | Default | Meaning |
|---|---|---|
| `ANIMA_BLOCKS_STRICT` | `1` | Set to `0` to log an ERROR and continue instead of stopping on a block-count mismatch |

## Safety design

- Arguments are forwarded verbatim via `*args/**kwargs` and resolved by name with `inspect.signature().bind()`; an upstream signature change degrades to "fix skipped + ERROR log" instead of an exception
- The fix mutates the per-instance `unet_config` copy created by `BASE.__init__`, so it cannot leak into other models
- Idempotent: importing twice keeps a single wrap (sentinel guard)

## Relationship with the original ComfyUI-Anima-2.9B (official patch)

**Not mutually exclusive — running both is harmless.** With both active, the official patch fixes num_blocks first and this patch becomes a no-op (its verification still runs).

We still **recommend disabling the official node**, not because of a conflict, but because of its failure mode: it wraps `detect_unet_config` — the common path every model load goes through — with a fixed signature, so a ComfyUI update that changes that function's arguments breaks loading of **all** models, not just Anima. This patch hooks an Anima-only method and tolerates signature changes (see above), so its blast radius is structurally limited to Anima.

To disable a node, append `.disabled` to its folder name (officially skipped by ComfyUI).

## Related repositories

- [ComfyUI-Anima-2.9B-loraPatch](https://github.com/sparklingcoffee777/ComfyUI-Anima-2.9B-loraPatch) — applies 28-block Anima LoRAs to 2.9B with the correct layer mapping. Install it too if you use LoRAs with 2.9B

## Acknowledgements

The observation that the hardcoded block count is the problem originates from [gazingstars123/ComfyUI-Anima-2.9B](https://github.com/gazingstars123/ComfyUI-Anima-2.9B) (Apache-2.0). The code here is an independent implementation of a fix for the same issue, differing in hook point (`Anima.get_model`), signature-agnostic forwarding, and post-load verification.

## Development notes

This project was vibe-coded with **Claude Opus 5** (Anthropic) in a Claude Code session: the investigation, the weight measurements and the code were all produced by the model under human direction.

The block mapping is not guesswork. It was derived by comparing the actual `.safetensors` weights of `Anima-2.9B-preview-v1` against `anima-base-v1.0` tensor by tensor, which is how the 28 bit-identical blocks and the 12 insertion points were identified. The patch was then verified against the real model files before release.

That said, please read the code before trusting it — it is short and single-purpose on purpose. Bug reports and corrections are welcome in the issue tracker.

## License

GPL-3.0, matching ComfyUI itself, since this patch hooks ComfyUI internals directly.
