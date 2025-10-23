# server.py

import os
import sys
import threading
import time
from flask import Flask, request, jsonify

# ★ agent_core.py からすべての必要な関数とグローバル変数をインポート
import agent_core 

# --- Flask, Port, App 定義 ---
SERVER_HOST = os.getenv("SERVER_HOST", "0.0.0.0")
SERVER_PORT = int(os.getenv("SERVER_PORT", "8080"))
app = Flask(__name__)
# -----------------------------


# ★★★ 外部APIエンドポイントの定義 ★★★
@app.route('/api/incoming-webhook', methods=['POST'])
def handle_external_webhook():
    """外部WebアプリからJSONを受け取り、LLM経由で音声を出力するエンドポイント"""
    
    # 1. ロックの取得 (agent_coreのロックを参照)
    # ★ タイムアウトを 3秒に延長し、アイドルチャットを確実に中断させて WebHook処理を優先する
    if not agent_core.PROCESS_LOCK.acquire(timeout=3): # 3秒待ってロックが取れなければ 503
        return jsonify({
            "status": "error", 
            "message": "システムがビジー状態です。音声出力が競合しています。しばらくしてから再試行してください。"
        }), 503

    try:
        # 2. JSONデータの解析
        data = request.get_json(silent=True) # 解析エラーがあってもクラッシュしない

        if not data or 'query' not in data:
            return jsonify({
                "status": "error", 
                "message": "JSONデータに 'query' フィールドがありません。"
            }), 400

        query = data.get('query')
        # user_id は JSONから取得できなければ agent_core のデフォルトを使用
        user_id = data.get('user_id', agent_core.DIFY_USER_ID if agent_core.DIFY_USER_ID else "webhook_user")

        print(f"\n🌐 Webhook受信 ({user_id}): {query}")
        
        # 3. ★ 応答生成と発話 (キーワード引数で明示的に指定)
        # agent_core.process_and_respond_core は内部でLLM通信、TTS、Outgoing Webhookを実行
        # ★ LLMプロバイダー（Dify/Langflow）は自動的に選択されます
        ai_response_text = agent_core.process_and_respond_core(
            user_prompt=query,      # ★ 明示的に指定
            user_id=user_id, 
            source="webhook"        # ★ Incoming Webhookからの入力として識別
        )
        
        # 4. 成功応答
        return jsonify({
            "status": "success",
            "agent_response": ai_response_text,
            "llm_provider": agent_core.LLM_PROVIDER  # ★ 使用したプロバイダー情報を返す
        }), 200

    except Exception as e:
        print(f"❌ 外部POST処理中に予期せぬエラー: {e}")
        import traceback
        traceback.print_exc()  # ★ デバッグ用に詳細なスタックトレースを出力
        return jsonify({
            "status": "error", 
            "message": "内部サーバーエラーが発生しました。"
        }), 500
        
    finally:
        # 処理が完了したら、必ずロックを解放する
        if agent_core.PROCESS_LOCK.locked():
             agent_core.PROCESS_LOCK.release()


# ★★★ ヘルスチェックエンドポイント (オプション) ★★★
@app.route('/health', methods=['GET'])
def health_check():
    """システムの稼働状態を確認するエンドポイント"""
    
    # ★ LLMプロバイダーの詳細情報を追加
    llm_status = {
        "provider": agent_core.LLM_PROVIDER,
        "dify_enabled": agent_core.ENABLE_DIFY,
        "langflow_enabled": agent_core.ENABLE_LANGFLOW
    }
    
    # ★ 設定の整合性チェック
    config_valid = True
    config_issues = []
    
    if agent_core.LLM_PROVIDER == "dify" and not agent_core.ENABLE_DIFY:
        config_valid = False
        config_issues.append("LLM_PROVIDER='dify' but ENABLE_DIFY=False")
    
    if agent_core.LLM_PROVIDER == "langflow" and not agent_core.ENABLE_LANGFLOW:
        config_valid = False
        config_issues.append("LLM_PROVIDER='langflow' but ENABLE_LANGFLOW=False")
    
    return jsonify({
        "status": "ok" if config_valid else "warning",
        "timestamp": time.time(),
        "llm": llm_status,
        "config_valid": config_valid,
        "config_issues": config_issues if config_issues else None,
        "services": {
            "llm_dify": agent_core.ENABLE_DIFY,
            "llm_langflow": agent_core.ENABLE_LANGFLOW,
            "tts_voicevox": agent_core.ENABLE_VOICEVOX,
            "tts_watson": agent_core.ENABLE_WATSON_TTS,
            "stt_whisper_local": agent_core.ENABLE_WHISPER_LOCAL,
            "stt_watson": agent_core.ENABLE_WATSON_STT,
            "stt_openai": agent_core.ENABLE_OPENAI_STT,
            "outgoing_webhook": agent_core.ENABLE_OUTGOING_WEBHOOK
        }
    }), 200


# ★★★ メインエントリポイント ★★★
if __name__ == "__main__":
    
    # ★ 初期化エラーチェック
    # agent_core.py の initialize_global_state() でエラーが発生している可能性をチェック
    try:
        # 必須変数が初期化されているか確認
        if not hasattr(agent_core, 'LLM_PROVIDER'):
            raise RuntimeError("agent_core の初期化に失敗しました。.env ファイルを確認してください。")
        
        # LLMプロバイダーの設定検証
        if agent_core.LLM_PROVIDER == "dify" and not agent_core.ENABLE_DIFY:
            raise ValueError(
                "設定エラー: LLM_PROVIDER='dify' ですが、ENABLE_DIFY=False になっています。\n"
                ".env ファイルで ENABLE_DIFY='True' に設定してください。"
            )
        
        if agent_core.LLM_PROVIDER == "langflow" and not agent_core.ENABLE_LANGFLOW:
            raise ValueError(
                "設定エラー: LLM_PROVIDER='langflow' ですが、ENABLE_LANGFLOW=False になっています。\n"
                ".env ファイルで ENABLE_LANGFLOW='True' に設定してください。"
            )
        
        # Dify使用時の設定確認
        if agent_core.LLM_PROVIDER == "dify":
            if not agent_core.DIFY_API_KEY:
                raise ValueError("Dify使用時は DIFY_API_KEY を設定してください。")
            if not agent_core.DIFY_BASE_URL:
                raise ValueError("Dify使用時は DIFY_BASE_URL を設定してください。")
        
        # Langflow使用時の設定確認
        if agent_core.LLM_PROVIDER == "langflow":
            if not agent_core.LANGFLOW_API_KEY:
                raise ValueError("Langflow使用時は LANGFLOW_API_KEY を設定してください。")
            if not agent_core.LANGFLOW_FLOW_ID:
                raise ValueError("Langflow使用時は LANGFLOW_FLOW_ID を設定してください。")
        
    except Exception as e:
        print("=" * 60)
        print("❌ システム起動エラー")
        print("=" * 60)
        print(f"エラー: {e}")
        print("\n📝 対処方法:")
        print("1. .env ファイルが存在するか確認")
        print("2. LLM_PROVIDER の設定を確認（'dify' または 'langflow'）")
        print("3. ENABLE_DIFY / ENABLE_LANGFLOW の設定を確認")
        print("4. 必要な API キーが設定されているか確認")
        print("=" * 60)
        sys.exit(1)
    
    # 1. 音声入力監視スレッドを起動
    mic_thread = threading.Thread(target=agent_core.mic_listening_process_core, daemon=True)
    mic_thread.start() 

    # 2. Webサーバーをメインスレッドで起動
    try:
        # 初回起動メッセージを音声で出力
        agent_core.text_to_speech("システム起動シーケンスを開始します。")

        # ★ 起動情報の詳細表示
        print("=" * 60)
        print("      📢 ハイブリッド AI エージェント起動中 📢      ")
        print("=" * 60)
        print(f"🤖 LLMプロバイダー: {agent_core.LLM_PROVIDER.upper()}")
        print(f"   ├─ Dify: {'✅ 有効' if agent_core.ENABLE_DIFY else '❌ 無効'}")
        print(f"   └─ Langflow: {'✅ 有効' if agent_core.ENABLE_LANGFLOW else '❌ 無効'}")
        print("-" * 60)
        print(f"🌐 Webhook受付中: http://{SERVER_HOST}:{SERVER_PORT}/api/incoming-webhook")
        print(f"💚 ヘルスチェック: http://{SERVER_HOST}:{SERVER_PORT}/health")
        
        if agent_core.ENABLE_OUTGOING_WEBHOOK:
            print(f"📤 Outgoing Webhook: {agent_core.OUTGOING_WEBHOOK_URL}")
        
        print("-" * 60)
        print(f"🎤 STT: ", end="")
        stt_services = []
        if agent_core.ENABLE_WHISPER_LOCAL: stt_services.append("Whisper(Local)")
        if agent_core.ENABLE_WATSON_STT: stt_services.append("Watson")
        if agent_core.ENABLE_OPENAI_STT: stt_services.append("OpenAI")
        print(", ".join(stt_services) if stt_services else "未設定")
        
        print(f"🔊 TTS: ", end="")
        tts_services = []
        if agent_core.ENABLE_VOICEVOX: tts_services.append("Voicevox")
        if agent_core.ENABLE_WATSON_TTS: tts_services.append("Watson")
        print(", ".join(tts_services) if tts_services else "未設定")
        
        print("=" * 60)
        
        # Flaskを本番に近い設定で実行
        app.run(host=SERVER_HOST, port=SERVER_PORT, threaded=False, debug=False, use_reloader=False)

    except KeyboardInterrupt:
        print("\n👋 プログラムを中断しました。")
    except Exception as e:
        print(f"❌ 致命的エラー: サーバー起動中にエラーが発生しました。詳細: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # PyAudioの解放
        agent_core.terminate_pyaudio_core() 
        print("✅ システムを終了しました。")
