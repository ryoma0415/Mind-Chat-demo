# Mind-Chat 設定ファイル (`mindchat_settings.json`) について

このドキュメントは、プロジェクト直下の `mindchat_settings.json` に書ける設定項目を、
目的・影響範囲・例とともに説明します。  
環境変数による上書きがある項目は、設定ファイルよりも環境変数が優先されます。

## 基本ルール
- 設定ファイルは **JSON形式** です。
- 数値は **整数/小数**、`true/false` は **真偽値** で書きます。
- `null` は「未指定」を意味し、アプリのデフォルト値が使われます。
- 変更後は **アプリを再起動** してください。

## 設定一覧

### app
- `app.default_mode_key`
  - 起動時に選択される会話モードのキー。
  - 例: `"plain_chat"` / `"mind_chat"`

### llm
- `llm.model_path`
  - LLMモデル（GGUF）へのパス。`null` の場合は `model/` 配下の既定ファイルを探します。
  - 環境変数 `MINDCHAT_MODEL_PATH` が最優先。
- `llm.max_context_tokens`
  - 1回の推論でLLMに渡す最大コンテキスト長（トークン数）。
- `llm.max_response_tokens`
  - LLMが生成する最大トークン数。
- `llm.temperature`
  - 応答の多様性（大きいほどランダム）。
- `llm.top_p`
  - nucleus sampling の閾値。小さいほど保守的な出力。
- `llm.gpu_layers`
  - llama.cpp の GPU レイヤ数。0でCPUのみ。
- `llm.threads`
  - llama.cpp のスレッド数。`null` で自動設定。

### history
- `history.max_conversations`
  - 履歴に保持する会話数の上限。
- `history.max_favorites`
  - お気に入り登録数の上限。

### speech
音声認識（Vosk）に関する設定です。

- `speech.model_path`
  - Voskモデルのパス。`null` で `model/vosk-model-ja-0.22` を使用。
  - 環境変数 `MINDCHAT_SPEECH_MODEL_PATH` が最優先。

#### speech.preprocess
録音データを Vosk に渡す前の前処理を制御します。

- `speech.preprocess.enabled`
  - 前処理全体のON/OFF。
  - `false` の場合、録音の生PCMをそのままVoskへ渡します。
- `speech.preprocess.force_mono`
  - `true` の場合、ステレオ音声をモノラルに変換。
- `speech.preprocess.resample`
  - `true` の場合、指定サンプルレートへリサンプリング。
- `speech.preprocess.target_sample_rate`
  - リサンプル先のサンプルレート（通常は 16000）。
- `speech.preprocess.convert_format`
  - `true` の場合、int16以外のフォーマットを int16 に変換。

#### speech.postprocess
Voskの認識結果（単語の空白区切り）を読みやすく整形します。

- `speech.postprocess.normalize_spaces`
  - CJK（日本語）同士の空白を削除し、余分な空白を整形。
- `speech.postprocess.append_punctuation`
  - 文末に「。」または「？」を簡易付与。
  - 既に句読点がある場合は追加しません。
- `speech.postprocess.use_timing`
  - `true` の場合、Voskの単語タイムスタンプを使って長い無音区間に「。」を挿入。
  - `false` の場合、文末だけの付与になります。
- `speech.postprocess.sentence_gap_sec`
  - `use_timing` 有効時に「。」を挿入する無音の長さ（秒）。
  - 例: `0.6` なら 0.6秒以上の間が空いた箇所で文区切りを入れます。

### embedding
- `embedding.model_path`
  - 埋め込みモデルのパス。`null` で既定の配置場所を使用。
  - 環境変数 `MINDCHAT_EMBEDDING_MODEL_PATH` が最優先。

### voicevox
- `voicevox.base_url`
  - VOICEVOXエンジンのURL。
  - 例: `"http://127.0.0.1:50021"`

## 設定例
```json
{
  "speech": {
    "preprocess": {
      "enabled": true,
      "force_mono": true,
      "resample": true,
      "target_sample_rate": 16000,
      "convert_format": true
    },
    "postprocess": {
      "normalize_spaces": true,
      "append_punctuation": true
    }
  },
  "voicevox": {
    "base_url": "http://127.0.0.1:50021"
  }
}
```
