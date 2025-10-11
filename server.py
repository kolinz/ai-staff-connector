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
    """外部WebアプリからJSONを受け取り、Dify経由で音声を出力するエンドポイント"""
    
    # 1. ロックの取得 (agent_coreのロックを参照)
    # ★ 修正: タイムアウトを 3秒に延長し、アイドルチャットを確実に中断させて WebHook処理を優先する
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
        # agent_core.process_and_respond_core は内部でDify通信、TTS、Outgoing Webhookを実行
        ai_response_text = agent_core.process_and_respond_core(
            user_prompt=query,      # ★ 明示的に指定
            user_id=user_id, 
            source="webhook"        # ★ Incoming Webhookからの入力として識別
        )
        
        # 4. 成功応答
        return jsonify({
            "status": "success",
            "agent_response": ai_response_text
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
    return jsonify({
        "status": "ok",
        "timestamp": time.time(),
        "services": {
            "dify": agent_core.ENABLE_DIFY,
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
    
    # 1. 音声入力監視スレッドを起動
    mic_thread = threading.Thread(target=agent_core.mic_listening_process_core, daemon=True)
    mic_thread.start() 

    # 2. Webサーバーをメインスレッドで起動
    try:
        # 初回起動メッセージを音声で出力
        agent_core.text_to_speech("システム起動シーケンスを開始します。")

        print("==================================================")
        print("      📢 ハイブリッド AI エージェント起動中 📢      ")
        print(f"🌐 Webhook受付中: http://{SERVER_HOST}:{SERVER_PORT}/api/incoming-webhook")
        print(f"💚 ヘルスチェック: http://{SERVER_HOST}:{SERVER_PORT}/health")
        if agent_core.ENABLE_OUTGOING_WEBHOOK:
            print(f"📤 Outgoing Webhook: {agent_core.OUTGOING_WEBHOOK_URL}")
        print("==================================================")
        
        # Flaskを本番に近い設定で実行
        app.run(host=SERVER_HOST, port=SERVER_PORT, threaded=False, debug=False, use_reloader=False)

    except KeyboardInterrupt:
        print("\nプログラムを中断しました。")
    except Exception as e:
        print(f"致命的エラー: サーバー起動中にエラーが発生しました。詳細: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # PyAudioの解放
        agent_core.terminate_pyaudio_core() 
        print("システムを終了しました。")