# ComfyUI-Anima-2.9B-blocksPatch

[English](README.md) | **日本語**

深さ拡張された Anima モデル（Anima-2.9B: 40 ブロック）を ComfyUI で正しくロードするための起動時パッチです。ワークフローノードは追加しません。

## 状態: リリース版 ComfyUI では引き続き必要です

ComfyUI 本体に 2026-08-12、ブロック数を state_dict から算出するネイティブ修正が
マージされました（[PR #15555](https://github.com/Comfy-Org/ComfyUI/pull/15555)）。ただしこの記述時点では **`master` にのみ存在**し、
v0.32.0 リリース（2026-08-11）より後に入ったため、**タグ付きリリースには未収録**です。

したがって:

- **リリース版の ComfyUI**（v0.32.0 以前、Desktop 版、portable 版）: 本パッチが必要です。
  入れないと Anima-2.9B が 28 ブロックに切り詰められた状態でロードされます
- **`master` を直接追っている場合**: 修正済みなので本パッチは不要です

またロード後検証には上流に相当機能がありません（切り詰められたモデルを通さず、ロードを
明示的に失敗させる）。Anima 系チェックポイントを自分で作成・拡張する場合に役立ちます。

## なぜ必要か

ComfyUI 本体は Anima のブロック数を state_dict から数えず、`model_channels == 2048` なら 28 ブロックと決め打ちします（`comfy/model_detection.py`）。

Anima-2.9B は anima-base-v1.0（28 ブロック）の **block expansion（深さ拡張）** モデルです。重み比較で実測した結果:

- 元の 28 ブロックはビット完全一致（max|diff| = 0）で全て残存
- 新規 12 ブロックがインデックス 2, 5, 8, 11, 14, 17, 21, 24, 27, 30, 33, 36 に挿入
- `llm_adapter` のみ追加学習

パッチなしでロードすると、ComfyUI は `strict=False` のため **エラーを出さずに** 28 ブロックのモデルを構築し、後半 12 ブロックが欠損した壊れたモデルで推論が走ります。

## インストール

1. このフォルダを `ComfyUI/custom_nodes/` に置く
2. ComfyUI を再起動

以上です。追加の pip インストールは不要、ワークフローの変更も不要です。

**注意: ノード一覧（Add Node メニュー）には何も追加されません。** これは起動時に自動で効くパッチであり、動作確認は下記の起動ログのみで行います。

アンインストールはフォルダを削除するか、フォルダ名の末尾に `.disabled` を付けてください。

## 動作

1. `comfy.supported_models.Anima.get_model` をラップ
2. state_dict の実ブロック数を本体の `count_blocks()` で数え、設定値と違えばそのインスタンス専有の `unet_config` を修正
3. モデル構築後、実際に構築されたブロック数と state_dict を照合。不一致なら **RuntimeError でロードを停止**（サイレント破損の防止）

28 ブロックの通常 Anima モデルでは何もしません（ログも出ません）。

## 確認方法

起動ログ:

```
[Anima blocks patch] installed on comfy.supported_models.Anima.get_model (strict=True).
```

2.9B ロード時:

```
[Anima blocks patch] state dict has 40 transformer blocks, config said 28; patching num_blocks.
```

## 環境変数

| 変数 | 既定 | 意味 |
|---|---|---|
| `ANIMA_BLOCKS_STRICT` | `1` | `0` にするとブロック数不一致でも停止せず ERROR ログのみで続行 |

## 設計上の安全策

- 引数は `*args/**kwargs` 透過 + `inspect.signature().bind()` で名前解決。上流のシグネチャ変更では例外にならず、「修正スキップ + ERROR ログ」に降格
- 修正は `BASE.__init__` が作るインスタンス専有の `unet_config` コピーに対して行うため、他モデルへ漏れない
- 二重 import しても一重ラップのまま（センチネルで防止）

## 既存の ComfyUI-Anima-2.9B（オフィシャルパッチ）との関係

**排他ではありません。併用しても壊れません。** 両方有効な場合、オフィシャル側が先に num_blocks を修正し、本パッチは値が一致するため no-op になります（検証だけは動きます）。

それでも **オフィシャル側の無効化を推奨** します。理由は競合ではなく、オフィシャル側の実装リスクです: あちらは全モデル共通の `detect_unet_config` を固定シグネチャでラップしているため、ComfyUI 更新でこの関数の引数が変わると **Anima 以外も含む全モデルのロードが例外で死にます**。本パッチは Anima 専用メソッドをフックし、引数変更にも耐えるため（上記）、被害範囲が構造的に Anima のみに限定されます。

無効化はフォルダ名の末尾に `.disabled` を付けるだけです（ComfyUI が公式にスキップします）。

## 関連リポジトリ

- [ComfyUI-Anima-2.9B-loraPatch](https://github.com/sparklingcoffee777/ComfyUI-Anima-2.9B-loraPatch) — 28 ブロック用 LoRA を 2.9B に正しく適用するパッチ。2.9B で LoRA を使うなら併せて導入してください

## 謝辞

ブロック数の決め打ちが問題であるという指摘は [gazingstars123/ComfyUI-Anima-2.9B](https://github.com/gazingstars123/ComfyUI-Anima-2.9B) (Apache-2.0) に由来します。本リポジトリのコードは同じ問題に対する独立した実装で、フック位置（`Anima.get_model`）・引数透過・ロード後検証が異なります。

## 開発について

本プロジェクトは Claude Code 上で **Claude Opus 5**（Anthropic）によるバイブコーディングで作成されました。調査・重みの実測・コードはいずれも人間の指示のもとでモデルが生成したものです。

ブロック対応は推測ではありません。`Anima-2.9B-preview-v1` と `anima-base-v1.0` の `.safetensors` の重みをテンソル単位で比較し、28 ブロックがビット完全一致であることと 12 箇所の挿入位置を実測して導出しています。公開前に実際のモデルファイルで動作検証も行っています。

とはいえ利用前にコードを読むことを推奨します（意図的に短く単一目的に保っています）。不具合の報告や修正提案は Issue へどうぞ。

## ライセンス

GPL-3.0。ComfyUI 本体（GPL-3.0）の内部を直接フックするため、同一ライセンスを採用しています。
