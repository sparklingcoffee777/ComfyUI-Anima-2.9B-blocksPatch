# ComfyUI-Anima-2.9B-blocksPatch

日本語 / English (English follows Japanese)

---

## 日本語

### これは何？

深さ拡張された Anima モデル（Anima-2.9B: 40 ブロック）を ComfyUI で正しくロードするための起動時パッチです。ワークフローノードは追加しません。

### なぜ必要か

ComfyUI 本体は Anima のブロック数を state_dict から数えず、`model_channels == 2048` なら 28 ブロックと決め打ちします（`comfy/model_detection.py`）。

Anima-2.9B は anima-base-v1.0（28 ブロック）の **block expansion（深さ拡張）** モデルです。重み比較で実測した結果:

- 元の 28 ブロックはビット完全一致（max|diff| = 0）で全て残存
- 新規 12 ブロックがインデックス 2, 5, 8, 11, 14, 17, 21, 24, 27, 30, 33, 36 に挿入
- `llm_adapter` のみ追加学習

パッチなしでロードすると、ComfyUI は `strict=False` のため **エラーを出さずに** 28 ブロックのモデルを構築し、後半 12 ブロックが欠損した壊れたモデルで推論が走ります。

### 動作

1. `comfy.supported_models.Anima.get_model` をラップ
2. state_dict の実ブロック数を本体の `count_blocks()` で数え、設定値と違えばそのインスタンス専有の `unet_config` を修正
3. モデル構築後、実際に構築されたブロック数と state_dict を照合。不一致なら **RuntimeError でロードを停止**（サイレント破損の防止）

28 ブロックの通常 Anima モデルでは何もしません（ログも出ません）。

### 既存の ComfyUI-Anima-2.9B（オフィシャルパッチ）との関係

**排他ではありません。併用しても壊れません。** 両方有効な場合、オフィシャル側が先に num_blocks を修正し、本パッチは値が一致するため no-op になります（検証だけは動きます）。

それでも **オフィシャル側の無効化を推奨** します。理由は競合ではなく、オフィシャル側の実装リスクです: あちらは全モデル共通の `detect_unet_config` を固定シグネチャでラップしているため、ComfyUI 更新でこの関数の引数が変わると **Anima 以外も含む全モデルのロードが例外で死にます**。本パッチは Anima 専用メソッドをフックし、引数変更にも耐えるため（下記）、被害範囲が構造的に Anima のみに限定されます。

無効化はフォルダ名の末尾に `.disabled` を付けるだけです（ComfyUI が公式にスキップします）。

### 設計上の安全策

- 引数は `*args/**kwargs` 透過 + `inspect.signature().bind()` で名前解決。上流のシグネチャ変更では例外にならず、「修正スキップ + ERROR ログ」に降格
- 修正は `BASE.__init__` が作るインスタンス専有の `unet_config` コピーに対して行うため、他モデルへ漏れない
- 二重 import しても一重ラップのまま（センチネルで防止）

### インストール / 使い方

1. このフォルダを `ComfyUI/custom_nodes/` に置く（ZIP ならそのまま展開）
2. ComfyUI を再起動

以上です。追加の pip インストールは不要、ワークフローの変更も不要です。

**注意: ノード一覧（Add Node メニュー）には何も追加されません。** これは起動時に自動で効くパッチであり、動作確認は下記の起動ログのみで行います。

アンインストールはフォルダを削除するか、フォルダ名の末尾に `.disabled` を付けてください。

### 環境変数

| 変数 | 既定 | 意味 |
|---|---|---|
| `ANIMA_BLOCKS_STRICT` | `1` | `0` にするとブロック数不一致でも停止せず ERROR ログのみで続行 |

### 確認方法

起動ログ:

```
[Anima blocks patch] installed on comfy.supported_models.Anima.get_model (strict=True).
```

2.9B ロード時:

```
[Anima blocks patch] state dict has 40 transformer blocks, config said 28; patching num_blocks.
```

---

## English

### What is this?

A load-time patch that lets ComfyUI correctly load depth-expanded Anima models (Anima-2.9B: 40 blocks). No workflow nodes are added.

### Why it is needed

ComfyUI does not count Anima's transformer blocks from the state dict; it hardcodes 28 blocks whenever `model_channels == 2048` (`comfy/model_detection.py`).

Anima-2.9B is a **block expansion (depth upscale)** of anima-base-v1.0 (28 blocks). Verified by direct weight comparison:

- All 28 original blocks are present bit-identically (max|diff| = 0)
- 12 new blocks were inserted at indices 2, 5, 8, 11, 14, 17, 21, 24, 27, 30, 33, 36
- Only `llm_adapter` was further trained

Without a patch, ComfyUI builds a 28-block model from the 40-block file **without any error** (weights load with `strict=False`) and runs inference with 12 blocks missing, silently producing broken output.

### How it works

1. Wraps `comfy.supported_models.Anima.get_model`
2. Counts the actual blocks in the state dict using ComfyUI's own `count_blocks()` and fixes `num_blocks` on that instance's private `unet_config` copy
3. After the model is built, verifies the constructed block count against the state dict. On mismatch it **raises a RuntimeError** so the load fails visibly instead of silently truncating

Regular 28-block Anima models are a complete no-op (not even a log line).

### Relationship with the original ComfyUI-Anima-2.9B (official patch)

**Not mutually exclusive — running both is harmless.** With both active, the official patch fixes num_blocks first and this patch becomes a no-op (its verification still runs).

We still **recommend disabling the official node**, not because of a conflict, but because of its failure mode: it wraps `detect_unet_config` — the common path every model load goes through — with a fixed signature, so a ComfyUI update that changes that function's arguments breaks loading of **all** models, not just Anima. This patch hooks an Anima-only method and tolerates signature changes (see below), so its blast radius is structurally limited to Anima.

To disable a node, append `.disabled` to its folder name (officially skipped by ComfyUI).

### Safety design

- Arguments are forwarded verbatim via `*args/**kwargs` and resolved by name with `inspect.signature().bind()`; an upstream signature change degrades to "fix skipped + ERROR log" instead of an exception
- The fix mutates the per-instance `unet_config` copy created by `BASE.__init__`, so it cannot leak into other models
- Idempotent: importing twice keeps a single wrap (sentinel guard)

### Installation / Usage

1. Put this folder into `ComfyUI/custom_nodes/` (just extract the ZIP as-is)
2. Restart ComfyUI

That's all. No extra pip installs, no workflow changes.

**Note: nothing appears in the node list (Add Node menu).** This patch takes effect automatically at startup; the startup log below is the only way to confirm it is active.

To uninstall, delete the folder or append `.disabled` to its name.

### Environment variables

| Variable | Default | Meaning |
|---|---|---|
| `ANIMA_BLOCKS_STRICT` | `1` | Set to `0` to log an ERROR and continue instead of stopping on a block-count mismatch |

### Verifying it works

Startup log:

```
[Anima blocks patch] installed on comfy.supported_models.Anima.get_model (strict=True).
```

When loading 2.9B:

```
[Anima blocks patch] state dict has 40 transformer blocks, config said 28; patching num_blocks.
```

---

## 関連リポジトリ / Related repositories

- [ComfyUI-Anima-2.9B-loraPatch](https://github.com/sparklingcoffee777/ComfyUI-Anima-2.9B-loraPatch) — 28 ブロック用 LoRA を 2.9B に正しく適用するパッチ。2.9B で LoRA を使うなら併せて導入してください / applies 28-block LoRAs to 2.9B with the correct layer mapping; install it too if you use LoRAs with 2.9B

## 謝辞 / Acknowledgements

ブロック数の決め打ちが問題であるという指摘は [gazingstars123/ComfyUI-Anima-2.9B](https://github.com/gazingstars123/ComfyUI-Anima-2.9B) (Apache-2.0) に由来します。本リポジトリのコードは同じ問題に対する独立した実装で、フック位置（`Anima.get_model`）・引数透過・ロード後検証が異なります。

The observation that the hardcoded block count is the problem originates from [gazingstars123/ComfyUI-Anima-2.9B](https://github.com/gazingstars123/ComfyUI-Anima-2.9B) (Apache-2.0). The code here is an independent implementation of a fix for the same issue, differing in hook point (`Anima.get_model`), signature-agnostic forwarding, and post-load verification.

## ライセンス / License

GPL-3.0. ComfyUI 本体（GPL-3.0）の内部を直接フックするため、同一ライセンスを採用しています。 / GPL-3.0, matching ComfyUI itself, since this patch hooks ComfyUI internals directly.
