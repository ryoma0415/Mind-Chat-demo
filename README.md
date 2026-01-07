# Mind-Chat

Mind-Chat は Gemma 2 2B Japanese IT (GGUF) をローカルで実行し、オフラインで会話やカウンセリングができるデスクトップアプリです。UI は PySide6 で構築され、履歴は JSON に保存されます。

## 主な機能
- 完全ローカルの LLM 推論（`llama-cpp-python` 経由で GGUF を直接ロード）
- 2 種類の会話モード（Mind-Chat / 通常モード）とモード別の履歴・テーマ・メディア表示
- Mind-Chat モードは相談内容に応じてトピックを推定し、専用の system prompt を動的に合成
- 返信は Markdown 表示（コードブロック/表/改行をサポート）
- 音声入力（Vosk, オフライン）と音声出力（VOICEVOX, 任意）
- 履歴のお気に入り管理・削除、最新の会話が先頭に並ぶ履歴リスト

## セットアップ手順
```bash
git clone <this-repo>
cd Mind-Chat
python -m venv .venv
source .venv/bin/activate    # Windows: .venv\Scripts\activate
# Llama をビルドせずに導入する（CPU 版 prebuilt wheel）
python -m pip install "llama-cpp-python==0.3.2" --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cpu --only-binary=:all:
pip install -r requirements.txt
```

LLMモデルダウンロードページ: https://huggingface.co/alfredplpl/gemma-2-2b-jpn-it-gguf  
Voskモデルダウンロードページ: https://alphacephei.com/vosk/models

## モデルの準備
### LLM (Gemma 2 2B Japanese IT)
- `model/gemma-2-2b-it-japanese-it.gguf` を配置します。
- 別名/別パスの場合は `MINDCHAT_MODEL_PATH` か `mindchat_settings.json` の `llm.model_path` を指定します。

### 音声認識 (Vosk)
- `model/vosk-model-ja-0.22/` に配置します。
- 別パスの場合は `MINDCHAT_SPEECH_MODEL_PATH` か `mindchat_settings.json` の `speech.model_path` を指定します。

### 埋め込みモデル（トピック推定用）
- 既定: `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`
- `model/embedding/paraphrase-multilingual-MiniLM-L12-v2/` に配置するか、`MINDCHAT_EMBEDDING_MODEL_PATH` を指定します。
- 依存ライブラリやモデルが不足している場合、トピック推定は無効化されます。

## VOICEVOX音声出力機能のセットアップ手順
Dockerをインストールする  
Dockerインストールページ: https://www.docker.com/ja-jp/get-started/  
ターミナルやPowershellで以下を実行（初回のみ: コンテナ作成）
```bash
docker run -d --name voicevox -p 50021:50021 --restart unless-stopped voicevox/voicevox_engine:cpu-latest
```
2回目以降は以下で起動できます（削除した場合は上の `docker run` を再実行）
```bash
docker start voicevox
```
停止する場合は以下のコマンド
```bash
docker stop voicevox
```

## 起動方法
```bash
python -m app.main
```

## 使い方の概要
- 画面上部のモード切り替えで Mind-Chat / 通常モードを選択
- 左ペインで履歴の選択・お気に入り切り替え・削除が可能
- 右下のマイクボタンで録音開始/停止（最大 2 分、無音 30 秒で自動停止）
- 音声出力を使う場合は「音声出力」を ON にし、話者を選択
- 上部のメディア領域にモード別の動画/画像が表示

## 設定
- `mindchat_settings.json` で各種パラメータを変更できます。
- 詳細は `setting.md` を参照してください。

主な項目:
- `app.default_mode_key`: 起動時のモード (`plain_chat` / `mind_chat`)
- `llm.*`: トークン長、温度、GPU レイヤ、スレッド数など
- `speech.*`: Vosk 前処理/後処理の挙動
- `voicevox.base_url`: VOICEVOX エンジンの URL

## プロジェクト構成
```
Mind-Chat/
├── app/
│   ├── __init__.py
│   ├── main.py                # アプリ起動エントリ
│   ├── config.py              # パス/モード/LLM 設定
│   ├── settings.py            # 設定読み込み
│   ├── resources.py           # PyInstaller 対応のリソース解決
│   ├── llm_client.py          # llama.cpp ラッパー
│   ├── speech_recognizer.py   # Vosk 音声認識
│   ├── voicevox_client.py     # VOICEVOX クライアント
│   ├── history.py             # 履歴/お気に入り管理
│   ├── models.py              # Conversation / ChatMessage
│   ├── counseling/
│   │   ├── prompt_catalog.py  # 相談トピック別プロンプト
│   │   ├── topic_router.py    # トピック推定と prompt 合成
│   │   ├── embedding.py       # SentenceTransformer ローダー
│   │   ├── retriever.py       # ChromaDB 検索
│   │   └── db/chroma/         # 相談トピック用ベクトルDB
│   └── ui/
│       ├── main_window.py
│       ├── conversation_widget.py
│       ├── history_panel.py
│       ├── media_display.py
│       ├── audio_recorder.py
│       ├── voice_player.py
│       └── workers.py
├── data/
│   ├── history_mindchat.json
│   └── history_plain.json
├── model/
│   ├── gemma-2-2b-it-japanese-it.gguf
│   ├── vosk-model-ja-0.22/
│   └── embedding/
│       └── paraphrase-multilingual-MiniLM-L12-v2/
├── screen_display/
│   ├── Mind-Chat/             # Mind-Chat モード用動画
│   └── 通常モード/             # 通常モード用画像
├── mindchat_launcher.py       # PyInstaller 用ランチャー
├── mindchat_settings.json     # 設定ファイル
├── requirements.txt
└── setting.md                 # 設定ドキュメント
```
