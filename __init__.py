"""
ComfyUI-Anima-2.9B-blocksPatch

Fixes the transformer block count when loading depth-expanded Anima models
(Anima-2.9B: 40 blocks) on a ComfyUI whose detection hardcodes 28 blocks for
model_channels == 2048 (comfy/model_detection.py).

Replacement for the upstream ComfyUI-Anima-2.9B node, with a safer design:

1. Narrow hook (blast radius: Anima only).
   Instead of wrapping comfy.model_detection.detect_unet_config -- the common
   code path every model load goes through, where a signature change upstream
   breaks loading of ALL models -- this wraps comfy.supported_models.Anima
   .get_model. That method is Anima-specific, and BASE.__init__ gives every
   model config its own unet_config copy, so mutating it here cannot leak into
   other models. If this hook ever breaks, only Anima loading is affected.

2. Signature-drift tolerant.
   Arguments are forwarded verbatim via *args/**kwargs and introspected by
   name with inspect.signature().bind(), so upstream adding, reordering or
   keyword-ifying parameters does not raise. If introspection fails, the fix
   degrades to a pass-through with a loud log line instead of an exception.

3. Loud verification (no silent 12-block truncation).
   After the model is built, the number of instantiated transformer blocks is
   compared against the number of blocks present in the state dict. Without
   this class of patch ComfyUI builds a 28-block model from a 40-block file
   and only emits a debug-level "unet unexpected" line while producing garbage.
   On mismatch this node raises a RuntimeError by default so the load fails
   visibly. Set ANIMA_BLOCKS_STRICT=0 to downgrade that to logging.error.

Coexistence: safe alongside the original ComfyUI-Anima-2.9B node (both write
the same measured value), but the original should be disabled since it retains
the break-everything signature risk this node exists to remove. Independent of
ComfyUI-Anima-2.9B-loraPatch (different hook, no shared state).

No workflow nodes are added; this is a load-time patch only.
"""

import inspect
import logging
import os

import comfy.model_detection
import comfy.supported_models

LOG_PREFIX = "[Anima blocks patch]"


def _strict():
    return os.environ.get("ANIMA_BLOCKS_STRICT", "1").strip().lower() not in ("0", "off", "false", "no", "warn")


def _count_state_dict_blocks(state_dict, prefix):
    # e.g. prefix "net." matches net.blocks.N.* but not net.llm_adapter.blocks.N.*
    return comfy.model_detection.count_blocks(
        state_dict.keys(), "{}blocks.".format(prefix) + "{}."
    )


def _built_blocks(model):
    try:
        return len(model.diffusion_model.blocks)
    except Exception:
        return None  # unexpected model layout; verification not possible


_orig_get_model = comfy.supported_models.Anima.get_model


def patched_get_model(self, *args, **kwargs):
    # --- resolve arguments by name, tolerating upstream signature changes ---
    state_dict = None
    prefix = None
    try:
        bound = inspect.signature(_orig_get_model).bind(self, *args, **kwargs)
        bound.apply_defaults()
        state_dict = bound.arguments.get("state_dict")
        prefix = bound.arguments.get("prefix")
    except Exception as err:
        logging.error(
            "{} could not introspect Anima.get_model arguments ({}); block-count fix "
            "NOT applied -- a depth-expanded Anima model may load truncated. Please "
            "update or remove this custom node.".format(LOG_PREFIX, err)
        )

    # --- fix num_blocks on this instance's private unet_config copy ---
    expected = None
    if state_dict is not None and prefix is not None:
        try:
            counted = _count_state_dict_blocks(state_dict, prefix)
            if counted > 0:
                expected = counted
                configured = self.unet_config.get("num_blocks")
                if counted != configured:
                    logging.info(
                        "{} state dict has {} transformer blocks, config said {}; "
                        "patching num_blocks.".format(LOG_PREFIX, counted, configured)
                    )
                    self.unet_config["num_blocks"] = counted
        except Exception as err:
            logging.error("{} block counting failed ({}); leaving config untouched.".format(LOG_PREFIX, err))

    out = _orig_get_model(self, *args, **kwargs)

    # --- verify the built model, loudly ---
    if expected is not None:
        actual = _built_blocks(out)
        if actual is None:
            logging.warning(
                "{} cannot verify built block count (no .diffusion_model.blocks).".format(LOG_PREFIX)
            )
        elif actual != expected:
            msg = (
                "{} BLOCK COUNT MISMATCH: state dict has {} transformer blocks but the "
                "built model has {}. The model would run with missing/misplaced layers "
                "and produce broken output.".format(LOG_PREFIX, expected, actual)
            )
            if _strict():
                raise RuntimeError(msg + " Set ANIMA_BLOCKS_STRICT=0 to continue anyway.")
            logging.error(msg)

    return out


patched_get_model._anima29b_blocks_patch = True

if getattr(_orig_get_model, "_anima29b_blocks_patch", False):
    logging.info("{} already installed; skipping.".format(LOG_PREFIX))
else:
    comfy.supported_models.Anima.get_model = patched_get_model
    logging.info(
        "{} installed on comfy.supported_models.Anima.get_model "
        "(strict={}).".format(LOG_PREFIX, _strict())
    )

NODE_CLASS_MAPPINGS = {}
NODE_DISPLAY_NAME_MAPPINGS = {}
