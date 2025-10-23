# agent_core.py

import os
import time
import io
import wave
import sys
import requests 
import random 
import re 
import threading 
# ★ 排他制御用ロックの定義 (トップレベル)
PROCESS_LOCK = threading.Lock() 

# ライブラリのインポート
from dotenv import load_dotenv
import pyaudio
import speech_recognition as sr 
from ibm_watson import SpeechToTextV1, TextToSpeechV1
from ibm_cloud_sdk_core.authenticators import IAMAuthenticator
from openai import OpenAI 
from faster_whisper import WhisperModel 

# .envファイルから環境変数をロード
load_dotenv() 

# ==========================================================
# 1. グローバル設定のプレースホルダーとリソース初期化
# ==========================================================

# --- グローバル変数初期化 ---
last_idle_sentence = "" 
quiet_mode_until_time = 0.0 
IDLE_CHAT_INTERVAL_SECONDS = 0 
MAX_PROMPT_LENGTH = 1000 
last_interaction_time = 0.0

# API Keys/URLs/Flags - Noneまたはデフォルト値で初期化
stt_service = None; tts_service = None; openai_client = None; whisper_local_model = None
DIFY_API_KEY = None; DIFY_APP_ID = None; DIFY_BASE_URL = None; DIFY_USER_ID = None
WATSON_STT_API_KEY = None; WATSON_STT_URL = None; WATSON_TTS_API_KEY = None; WATSON_TTS_URL = None
WATSON_TTS_VOICE = None; WATSON_STT_MODEL = None; VOICEVOX_BASE_URL = None; VOICEVOX_SPEAKER_ID = "3"
OPENAI_API_KEY = None; WHISPER_LOCAL_MODEL = None
ENABLE_WHISPER_LOCAL = False; ENABLE_WATSON_STT = False; ENABLE_OPENAI_STT = False
ENABLE_VOICEVOX = False; ENABLE_WATSON_TTS = False; ENABLE_DIFY = False
QUIET_KEYWORD = None; STT_WATSON_NO_SPEECH_MSG = None; STT_OPENAI_NO_SPEECH_MSG = None
WAKE_WORD_SET = set(); WAKE_WORD_DISPLAY = 'キーワード'
IDLE_SENTENCES = []; HUM_SENTENCES = []

# ★ LLMプロバイダー関連のグローバル変数
LLM_PROVIDER = "dify"
LLM_TIMEOUT = 60
LANGFLOW_API_KEY = None
LANGFLOW_BASE_URL = None
LANGFLOW_FLOW_ID = None
LANGFLOW_ENDPOINT = None
ENABLE_LANGFLOW = False

# ★ Outgoing Webhook 関連のグローバル変数
OUTGOING_WEBHOOK_URL = None
ENABLE_OUTGOING_WEBHOOK = False
OUTGOING_WEBHOOK_AUTH_TOKEN = None
OUTGOING_WEBHOOK_TIMEOUT = 10
OUTGOING_WEBHOOK_RETRY_COUNT = 3

# 共通リソース (必ず関数外で初期化)
TEMP_AUDIO_FILE = "user_input.wav"
r = sr.Recognizer(); p = pyaudio.PyAudio() 


# ==========================================================
# 2. 初期化関数 (設定とサービス起動を確実に実行)
# ==========================================================

def initialize_global_state():
    """環境変数を読み込み、全てのグローバル変数とサービスインスタンスを設定する"""
    # ★ 必須: すべてのグローバル変数を明示的に宣言し、値を代入
    global DIFY_API_KEY, DIFY_APP_ID, DIFY_BASE_URL, DIFY_USER_ID, WATSON_STT_API_KEY, WATSON_STT_URL, WATSON_TTS_API_KEY
    global WATSON_TTS_URL, WATSON_TTS_VOICE, WATSON_STT_MODEL, VOICEVOX_BASE_URL, VOICEVOX_SPEAKER_ID
    global OPENAI_API_KEY, WHISPER_LOCAL_MODEL, ENABLE_WHISPER_LOCAL, ENABLE_WATSON_STT, ENABLE_OPENAI_STT
    global ENABLE_VOICEVOX, ENABLE_WATSON_TTS, ENABLE_DIFY, WAKE_WORDS_LIST, QUIET_KEYWORD, QUIET_DURATION_MINUTES
    global STT_WATSON_NO_SPEECH_MSG, STT_OPENAI_NO_SPEECH_MSG, IDLE_CHAT_INTERVAL_SECONDS, IDLE_SENTENCES, HUM_SENTENCES
    global WAKE_WORD_SET, WAKE_WORD_DISPLAY
    global stt_service, tts_service, openai_client, whisper_local_model
    global last_interaction_time, quiet_mode_until_time
    # ★ LLMプロバイダー用のグローバル変数を追加
    global LLM_PROVIDER, LLM_TIMEOUT, LANGFLOW_API_KEY, LANGFLOW_BASE_URL, LANGFLOW_FLOW_ID, LANGFLOW_ENDPOINT, ENABLE_LANGFLOW
    # ★ Outgoing Webhook用のグローバル変数を追加
    global OUTGOING_WEBHOOK_URL, ENABLE_OUTGOING_WEBHOOK, OUTGOING_WEBHOOK_AUTH_TOKEN
    global OUTGOING_WEBHOOK_TIMEOUT, OUTGOING_WEBHOOK_RETRY_COUNT

    try:
        # --- 環境変数の読み込みと代入 (安全な読み込み) ---
        
        # LLMプロバイダー設定
        LLM_PROVIDER = os.getenv("LLM_PROVIDER", "dify").lower().strip()
        LLM_TIMEOUT = int(os.getenv("LLM_TIMEOUT", "60").strip())
        
        # ★ Dify設定 (ENABLE_DIFY を先に読み込む)
        ENABLE_DIFY = os.getenv("ENABLE_DIFY", "True").lower().strip() == 'true'
        DIFY_API_KEY = os.getenv("DIFY_API_KEY", "").strip()
        DIFY_APP_ID = os.getenv("DIFY_APP_ID", "").strip()
        DIFY_BASE_URL = os.getenv("DIFY_BASE_URL", "").strip()
        DIFY_USER_ID = os.getenv("DIFY_USER_ID", "").strip()
        
        # ★ Langflow設定 (ENABLE_LANGFLOW を先に読み込む)
        ENABLE_LANGFLOW = os.getenv("ENABLE_LANGFLOW", "True").lower().strip() == 'true'
        LANGFLOW_API_KEY = os.getenv("LANGFLOW_API_KEY", "").strip()
        LANGFLOW_BASE_URL = os.getenv("LANGFLOW_BASE_URL", "http://localhost:7860").strip()
        LANGFLOW_FLOW_ID = os.getenv("LANGFLOW_FLOW_ID", "").strip()
        LANGFLOW_ENDPOINT = os.getenv("LANGFLOW_ENDPOINT", "").strip()
        
        WATSON_STT_API_KEY = os.getenv("WATSON_STT_API_KEY", "").strip()
        WATSON_STT_URL = os.getenv("WATSON_STT_URL", "").strip()
        WATSON_TTS_API_KEY = os.getenv("WATSON_TTS_API_KEY", "").strip()
        WATSON_TTS_URL = os.getenv("WATSON_TTS_URL", "").strip()
        WATSON_TTS_VOICE = os.getenv("WATSON_TTS_VOICE", "").strip()
        WATSON_STT_MODEL = os.getenv("WATSON_STT_MODEL", "").strip()
        VOICEVOX_BASE_URL = os.getenv("VOICEVOX_BASE_URL", "").strip()
        VOICEVOX_SPEAKER_ID = os.getenv("VOICEVOX_SPEAKER_ID", "3").strip()
        OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
        WHISPER_LOCAL_MODEL = os.getenv("WHISPER_LOCAL_MODEL", "").strip()

        # --- サービス有効化フラグ ---
        ENABLE_WHISPER_LOCAL = os.getenv("ENABLE_WHISPER_LOCAL", "False").lower().strip() == 'true'
        ENABLE_WATSON_STT = os.getenv("ENABLE_WATSON_STT", "False").lower().strip() == 'true'
        ENABLE_OPENAI_STT = os.getenv("ENABLE_OPENAI_STT", "False").lower().strip() == 'true'
        ENABLE_VOICEVOX = os.getenv("ENABLE_VOICEVOX", "False").lower().strip() == 'true'
        ENABLE_WATSON_TTS = os.getenv("ENABLE_WATSON_TTS", "False").lower().strip() == 'true'

        # ★ Outgoing Webhook 設定の読み込み
        OUTGOING_WEBHOOK_URL = os.getenv("OUTGOING_WEBHOOK_URL", "").strip()
        ENABLE_OUTGOING_WEBHOOK = os.getenv("ENABLE_OUTGOING_WEBHOOK", "False").lower().strip() == 'true'
        OUTGOING_WEBHOOK_AUTH_TOKEN = os.getenv("OUTGOING_WEBHOOK_AUTH_TOKEN", "").strip()
        OUTGOING_WEBHOOK_TIMEOUT = int(os.getenv("OUTGOING_WEBHOOK_TIMEOUT", "10").strip())
        OUTGOING_WEBHOOK_RETRY_COUNT = int(os.getenv("OUTGOING_WEBHOOK_RETRY_COUNT", "3").strip())

        # 制御/メッセージ設定
        WAKE_WORDS_LIST = os.getenv("WAKE_WORDS_LIST", "AI").strip()
        QUIET_KEYWORD = os.getenv("QUIET_KEYWORD", "静かにして").strip()
        QUIET_DURATION_MINUTES = int(os.getenv("QUIET_DURATION_MINUTES", "30").strip())
        STT_WATSON_NO_SPEECH_MSG = os.getenv("STT_WATSON_NO_SPEECH_MSG", "Watson STT: 音声が聞き取れませんでした。").strip()
        STT_OPENAI_NO_SPEECH_MSG = os.getenv("STT_OPENAI_NO_SPEECH_MSG", "OpenAI Whisper: 音声が聞き取れませんでした。").strip()

        # アイドル設定
        IDLE_CHAT_INTERVAL_SECONDS = int(os.getenv("IDLE_CHAT_INTERVAL_MINUTES", "0").strip()) * 60 

        # リスト生成 (IDLE_SENTENCES)
        IDLE_SENTENCES.clear(); i = 1
        while True: 
            sentence = os.getenv(f"IDLE_SENTENCE_{i}")
            if sentence is None: 
                break
            if sentence.strip(): 
                IDLE_SENTENCES.append(sentence.strip())
            i += 1

        # リスト生成 (HUM_SENTENCES)
        HUM_SENTENCES.clear(); i = 1
        while True: 
            sentence = os.getenv(f"HUM_SENTENCE_{i}"); 
            if sentence is None: 
                break
            if sentence.strip(): 
                HUM_SENTENCES.append(sentence.strip())
            i += 1

        # 複数キーワードの処理と表示用キーワードの設定
        WAKE_WORD_SET.clear()
        if WAKE_WORDS_LIST: 
            WAKE_WORD_SET.update({w.lower().strip() for w in WAKE_WORDS_LIST.split(',')})
        WAKE_WORD_DISPLAY = next(iter(WAKE_WORD_SET), 'キーワード')

        # ★★★ LLMプロバイダーの検証ロジック ★★★
        if LLM_PROVIDER not in ["dify", "langflow"]:
            raise ValueError(f"不明なLLMプロバイダー: {LLM_PROVIDER}。'dify' または 'langflow' を指定してください。")
        
        # ★ Dify使用時の検証
        if LLM_PROVIDER == "dify":
            if not ENABLE_DIFY:
                raise ValueError(f"LLM_PROVIDER='{LLM_PROVIDER}' ですが、ENABLE_DIFY=False になっています。ENABLE_DIFY=True に設定してください。")
            
            required_dify_credentials = [DIFY_API_KEY, DIFY_APP_ID, DIFY_BASE_URL, DIFY_USER_ID]
            if not all(required_dify_credentials):
                raise ValueError("Dify を使用するには、DIFY_API_KEY, DIFY_APP_ID, DIFY_BASE_URL, DIFY_USER_ID を全て設定してください。")
            
            print(f"INFO: LLMプロバイダー: Dify を使用します。")
        
        # ★ Langflow使用時の検証
        elif LLM_PROVIDER == "langflow":
            if not ENABLE_LANGFLOW:
                raise ValueError(f"LLM_PROVIDER='{LLM_PROVIDER}' ですが、ENABLE_LANGFLOW=False になっています。ENABLE_LANGFLOW=True に設定してください。")
            
            if not LANGFLOW_API_KEY:
                raise ValueError("Langflow を使用するには、LANGFLOW_API_KEY を設定してください。")
            if not LANGFLOW_FLOW_ID:
                raise ValueError("Langflow を使用するには、LANGFLOW_FLOW_ID を設定してください。")
            
            print(f"INFO: LLMプロバイダー: Langflow を使用します。")

        # ★ Outgoing Webhook の検証
        if ENABLE_OUTGOING_WEBHOOK and not OUTGOING_WEBHOOK_URL:
            print("警告: ENABLE_OUTGOING_WEBHOOK=True ですが、OUTGOING_WEBHOOK_URL が設定されていません。")
            ENABLE_OUTGOING_WEBHOOK = False
        elif ENABLE_OUTGOING_WEBHOOK:
            print(f"INFO: Outgoing Webhook を有効にしました。送信先: {OUTGOING_WEBHOOK_URL}")

        # --- サービスの初期化 ---
        if ENABLE_WATSON_STT and all([WATSON_STT_API_KEY, WATSON_STT_URL, WATSON_STT_MODEL]):
            stt_authenticator = IAMAuthenticator(WATSON_STT_API_KEY)
            stt_service = SpeechToTextV1(authenticator=stt_authenticator)
            stt_service.set_service_url(WATSON_STT_URL)
            print("INFO: IBM Watson STTサービスを有効にしました。")
            
        if ENABLE_WATSON_TTS and all([WATSON_TTS_API_KEY, WATSON_TTS_URL, WATSON_TTS_VOICE]):
            tts_authenticator = IAMAuthenticator(WATSON_TTS_API_KEY)
            tts_service = TextToSpeechV1(authenticator=tts_authenticator)
            tts_service.set_service_url(WATSON_TTS_URL)
            print("INFO: IBM Watson TTSサービスを有効にしました。")
            
        if ENABLE_OPENAI_STT and OPENAI_API_KEY:
            openai_client = OpenAI(api_key=OPENAI_API_KEY)
            print("INFO: OpenAIクライアントを有効にしました。")
            
        if ENABLE_WHISPER_LOCAL and WHISPER_LOCAL_MODEL:
            try:
                whisper_local_model = WhisperModel(WHISPER_LOCAL_MODEL, device="cpu", compute_type="int8")
                print(f"INFO: ローカル Whisper ({WHISPER_LOCAL_MODEL}) サービスを有効にしました。(STT最優先)")
            except Exception as e:
                print(f"警告: ローカル Whisperの初期化に失敗しました。ローカル STT は無効化されます。詳細: {e}")
                ENABLE_WHISPER_LOCAL = False

        # 最終的な有効性チェック
        stt_active = (stt_service is not None) or (openai_client is not None) or (whisper_local_model is not None)
        tts_active = (VOICEVOX_BASE_URL) or (tts_service is not None)
        
        if not stt_active: 
            raise Exception("STTサービスが一つも有効化されていません。")
        if not tts_active: 
            raise Exception("TTSサービスが一つも有効化されていません。")

        # 最終的なタイムスタンプ設定
        last_interaction_time = time.time() 

    except Exception as e:
        # 例外は server.py で捕捉させる
        raise e


# --- 初期化の実行 ---
try:
    initialize_global_state()
except Exception as e:
    # server.py の起動時にエラーが捕捉され、適切に終了する
    pass 


# ==========================================================
# 3. ユーティリティ関数
# ==========================================================

def terminate_pyaudio_core():
    """PyAudioリソースを解放する関数"""
    global p
    if 'p' in globals() and p:
        p.terminate()

def sanitize_prompt(text):
    """セキュリティ対策: 危険な特殊文字をエスケープまたは置換する"""
    if not text: 
        return ""
    text = text.replace("'", "\\'")
    text = text.replace('"', '\\"')
    text = text.replace('\n', ' [NEWLINE] ')
    text = text.replace('\r', ' [NEWLINE] ')
    text = text.replace('#', '\\#')
    return text

def remove_thinking_tags(text):
    """LLM応答から <think>...</think> ブロックとその内容を効率的に削除する。"""
    if not text or "<think>" not in text.lower(): 
        return text.strip()
    pattern = r'<think>.*?<\/think>'
    cleaned_text = re.sub(pattern, '', text, flags=re.DOTALL | re.IGNORECASE)
    if cleaned_text.strip(): 
        return cleaned_text.strip()
    return ""


# ==========================================================
# 4. TTS 関連関数
# ==========================================================

def _play_audio_stream(audio_stream):
    """共通の音声再生ロジック"""
    global p
    try:
        with wave.open(audio_stream, 'rb') as wf:
            stream = p.open(
                format=p.get_format_from_width(wf.getsampwidth()),
                channels=wf.getnchannels(),
                rate=wf.getframerate(),
                output=True
            ) 
            data = wf.readframes(1024)
            while data: 
                stream.write(data)
                data = wf.readframes(1024)
            stream.stop_stream()
            stream.close()
    except Exception as e:
        print(f"警告: 音声再生に失敗しました。詳細: {e}")

def voicevox_text_to_speech(text):
    """Voicevox WebAPI を使用してテキストを音声として読み上げる"""
    print(f"AI応答 (Voicevox): {text}")
    if not VOICEVOX_BASE_URL: 
        return
    try:
        query_url = f"{VOICEVOX_BASE_URL.rstrip('/')}/audio_query"
        query_params = {"text": text, "speaker": VOICEVOX_SPEAKER_ID}
        query_response = requests.post(query_url, params=query_params)
        query_response.raise_for_status()
        audio_query = query_response.json()
        
        synthesis_url = f"{VOICEVOX_BASE_URL.rstrip('/')}/synthesis"
        synthesis_params = {"speaker": VOICEVOX_SPEAKER_ID}
        synthesis_headers = {"Content-Type": "application/json"}
        synthesis_response = requests.post(
            synthesis_url, 
            params=synthesis_params, 
            headers=synthesis_headers, 
            json=audio_query
        )
        synthesis_response.raise_for_status()
        
        audio_stream = io.BytesIO(synthesis_response.content)
        _play_audio_stream(audio_stream)
    except Exception as e:
        print(f"警告: Voicevox/音声再生に失敗しました。詳細: {e}")

def text_to_speech(text):
    """設定に応じて、VoicevoxまたはWatson TTSを使用してテキストを音声として読み上げる"""
    if VOICEVOX_BASE_URL and ENABLE_VOICEVOX: 
        return voicevox_text_to_speech(text)
        
    if tts_service and ENABLE_WATSON_TTS:
        print(f"AI応答 (Watson TTS): {text}")
        try:
            response = tts_service.synthesize(
                text, 
                voice=WATSON_TTS_VOICE, 
                accept='audio/wav'
            ).get_result()
            audio_stream = io.BytesIO(response.content)
            _play_audio_stream(audio_stream)
        except Exception as e:
            print(f"警告: Watson TTS/音声再生に失敗しました。詳細: {e}")
            return
            
    print("警告: TTSサービスが利用できません。")
    return


# ==========================================================
# 5. STT 関連関数
# ==========================================================

def whisper_speech_to_text(audio_file_path):
    """ローカル Whisper (faster-whisper) を使用して音声ファイルからテキストに変換する"""
    global whisper_local_model
    if not whisper_local_model: 
        return None
    try:
        segments, info = whisper_local_model.transcribe(
            audio_file_path, 
            language="ja", 
            vad_filter=True
        )
        segments_list = list(segments)
        if segments_list:
            user_input = " ".join([segment.text for segment in segments_list]).strip()
            if user_input: 
                return user_input
        print("Local Whisper: 音声が聞き取れませんでした.")
        return None
    except Exception as e:
        print(f"警告: Local Whisper処理中に致命的なエラーが発生しました。詳細: {e}")
        return None

def openai_speech_to_text(audio_file_path):
    """OpenAI Whisper API を使用して音声ファイルからテキストに変換する"""
    global openai_client
    if not openai_client: 
        return None
    try:
        with open(audio_file_path, 'rb') as audio_file:
            transcript = openai_client.audio.transcriptions.create(
                model="whisper-1", 
                file=audio_file, 
                language="ja"
            )
            user_input = transcript.text.strip()
            if not user_input: 
                print(STT_OPENAI_NO_SPEECH_MSG)
                return None
            return user_input
    except Exception as e:
        print(f"警告: OpenAI Whisper通信または認証に失敗しました。詳細: {e}")
        return None

def speech_to_text(audio_file_path):
    """STTのディスパッチャー: 優先順位に従い、排他的にサービスを呼び出す"""
    if not os.path.exists(audio_file_path): 
        return None
    user_input = None
    
    try:
        service_order = []
        if ENABLE_WHISPER_LOCAL: 
            service_order.append('local_whisper')
        if ENABLE_WATSON_STT: 
            service_order.append('watson')
        if ENABLE_OPENAI_STT: 
            service_order.append('openai')

        for service_type in service_order:
            if service_type == 'local_whisper':
                if ENABLE_WHISPER_LOCAL: 
                    user_input = whisper_speech_to_text(audio_file_path)
                if user_input: 
                    return user_input 

            elif service_type == 'watson':
                if not stt_service or not ENABLE_WATSON_STT: 
                    continue
                try:
                    with open(audio_file_path, 'rb') as audio_file:
                        response = stt_service.recognize(
                            audio_file, 
                            content_type='audio/wav', 
                            model=WATSON_STT_MODEL
                        ).get_result()
                        if response.get('results'):
                            user_input = response['results'][0]['alternatives'][0]['transcript']
                            return user_input
                        else: 
                            print(STT_WATSON_NO_SPEECH_MSG)
                except Exception as e:
                    print(f"警告: Watson STT通信失敗。OpenAI Whisperにフォールバックします。詳細: {e}")

            elif service_type == 'openai':
                if not openai_client or not ENABLE_OPENAI_STT: 
                    continue
                user_input = openai_speech_to_text(audio_file_path)
                if user_input: 
                    return user_input
                
        return user_input

    finally:
        try:
            if os.path.exists(TEMP_AUDIO_FILE): 
                os.remove(TEMP_AUDIO_FILE)
        except OSError:
            pass 

def recognize_speech_from_mic():
    """マイクから音声を録音し、WAVファイルとして保存する"""
    global r
    with sr.Microphone() as source: 
        r.adjust_for_ambient_noise(source)
        try:
            audio = r.listen(source, timeout=5, phrase_time_limit=10)
        except sr.WaitTimeoutError: 
            return None
        try:
            with open(TEMP_AUDIO_FILE, "wb") as f: 
                f.write(audio.get_wav_data())
                return TEMP_AUDIO_FILE
        except Exception as e:
            print(f"警告: 録音ファイル作成に失敗しました。詳細: {e}")
            return None


# ==========================================================
# 6. LLM連携関数 (Dify / Langflow)
# ==========================================================

def get_dify_response(prompt):
    """Dify API (Chat App)にリクエストを送信し、応答を取得する"""
    
    # ★ ENABLE_DIFYチェックを追加
    if not ENABLE_DIFY: 
        return "Difyサービスが無効化されているため、AI応答を生成できません。.envでENABLE_DIFY=Trueに設定してください。" 
    
    if len(prompt) > MAX_PROMPT_LENGTH: 
        return f"プロンプトが長すぎます。最大{MAX_PROMPT_LENGTH}文字までです。"
        
    sanitized_prompt = sanitize_prompt(prompt)
    chat_url = f"{DIFY_BASE_URL.rstrip('/')}/v1/chat-messages"
    headers = {
        "Authorization": f"Bearer {DIFY_API_KEY}", 
        "Content-Type": "application/json"
    }
    payload = {
        "inputs": {}, 
        "query": sanitized_prompt, 
        "response_mode": "blocking", 
        "user": DIFY_USER_ID, 
        "conversation_id": ""
    }
    
    try:
        response = requests.post(chat_url, headers=headers, json=payload, timeout=LLM_TIMEOUT)
        response.raise_for_status() 
        data = response.json()
        
        if data.get('answer'):
            final_answer = remove_thinking_tags(data['answer'])
            if final_answer: 
                return final_answer
            return "Difyからの応答は思考ログのみでした。回答が生成されていません。"
        return "Difyからの応答が空でした。Appの設定を確認してください。"
        
    except requests.exceptions.Timeout:
        print(f"警告: Dify API通信がタイムアウトしました。")
        return "ごめんなさい、Difyサービスが応答しませんでした。しばらくしてから再度呼びかけてください。"
        
    except requests.exceptions.RequestException as e:
        print(f"警告: Dify API通信に失敗しました。詳細: {e}")
        return "ごめんなさい、Difyサーバーとの接続に失敗しました。ネットワークを確認してください。"
        
    except Exception as e:
        print(f"警告: Dify応答処理中に予期せぬエラーが発生しました。詳細: {e}")
        return "予期せぬエラーが発生し、応答できませんでした。システム管理者にお問い合わせください。"


def get_langflow_response(prompt):
    """Langflow APIにリクエストを送信し、応答を取得する"""
    
    # ★ ENABLE_LANGFLOWチェックを追加
    if not ENABLE_LANGFLOW:
        return "Langflowサービスが無効化されているため、AI応答を生成できません。.envでENABLE_LANGFLOW=Trueに設定してください。"
    
    if not LANGFLOW_API_KEY:
        return "Langflow APIキーが設定されていません。"
    
    if not LANGFLOW_FLOW_ID:
        return "Langflow Flow IDが設定されていません。"
    
    if len(prompt) > MAX_PROMPT_LENGTH:
        return f"プロンプトが長すぎます。最大{MAX_PROMPT_LENGTH}文字までです。"
    
    sanitized_prompt = sanitize_prompt(prompt)
    
    # エンドポイントURLの構築
    if LANGFLOW_ENDPOINT:
        # 特定エンドポイント名が指定されている場合
        api_url = f"{LANGFLOW_BASE_URL.rstrip('/')}/api/v1/run/{LANGFLOW_ENDPOINT}"
    else:
        # デフォルト: Flow IDを使用
        api_url = f"{LANGFLOW_BASE_URL.rstrip('/')}/api/v1/run/{LANGFLOW_FLOW_ID}"
    
    headers = {
        "x-api-key": LANGFLOW_API_KEY,
        "Content-Type": "application/json"
    }
    
    # Langflow標準ペイロード
    payload = {
        "input_value": sanitized_prompt,
        "output_type": "chat",
        "input_type": "chat",
        "tweaks": {}
    }
    
    try:
        response = requests.post(api_url, headers=headers, json=payload, timeout=LLM_TIMEOUT)
        response.raise_for_status()
        data = response.json()
        
        # Langflowのレスポンス解析
        # 形式1: outputs[0].outputs[0].results.message.text
        if isinstance(data.get('outputs'), list) and len(data['outputs']) > 0:
            output = data['outputs'][0]
            
            # パターン1: outputs[0].outputs[0].results.message.text
            if isinstance(output.get('outputs'), list) and len(output['outputs']) > 0:
                nested_output = output['outputs'][0]
                results = nested_output.get('results', {})
                message = results.get('message', {})
                
                if isinstance(message, dict) and 'text' in message:
                    return message['text'].strip()
                elif isinstance(message, str):
                    return message.strip()
            
            # パターン2: outputs[0].results.message.text
            results = output.get('results', {})
            message = results.get('message', {})
            
            if isinstance(message, dict) and 'text' in message:
                return message['text'].strip()
            elif isinstance(message, str):
                return message.strip()
            
            # パターン3: outputs[0].message (直接メッセージ)
            if 'message' in output:
                msg = output['message']
                if isinstance(msg, dict) and 'text' in msg:
                    return msg['text'].strip()
                elif isinstance(msg, str):
                    return msg.strip()
        
        # 形式2: 直接message/text フィールド
        if 'message' in data:
            msg = data['message']
            if isinstance(msg, dict) and 'text' in msg:
                return msg['text'].strip()
            elif isinstance(msg, str):
                return msg.strip()
        
        if 'text' in data:
            return data['text'].strip()
        
        # デバッグ用: レスポンス構造を出力
        print(f"Langflow レスポンス構造: {data}")
        return "Langflowからの応答形式を解析できませんでした。"
        
    except requests.exceptions.Timeout:
        print(f"警告: Langflow API通信がタイムアウトしました。")
        return "ごめんなさい、Langflowサービスが応答しませんでした。しばらくしてから再度呼びかけてください。"
        
    except requests.exceptions.RequestException as e:
        print(f"警告: Langflow API通信に失敗しました。詳細: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"ステータスコード: {e.response.status_code}")
            print(f"レスポンス内容: {e.response.text}")
        return "ごめんなさい、Langflowサーバーとの接続に失敗しました。ネットワークを確認してください。"
        
    except Exception as e:
        print(f"警告: Langflow応答処理中に予期せぬエラーが発生しました。詳細: {e}")
        return "予期せぬエラーが発生し、応答できませんでした。システム管理者にお問い合わせください。"


def get_llm_response(prompt):
    """
    統合LLMレスポンス取得関数
    環境変数 LLM_PROVIDER に基づいて適切なプロバイダーを呼び出す
    
    Args:
        prompt (str): ユーザーからの入力テキスト
    
    Returns:
        str: LLMからの応答テキスト
    """
    
    if not prompt or not prompt.strip():
        return "入力が空です。"
    
    # ★ プロバイダーの選択 + ENABLE フラグのチェック
    if LLM_PROVIDER == "langflow":
        if not ENABLE_LANGFLOW:
            return "設定エラー: LLM_PROVIDER='langflow' ですが、ENABLE_LANGFLOW=False になっています。.envを確認してください。"
        print(f"[LLM] Langflowプロバイダーを使用")
        return get_langflow_response(prompt)
    
    elif LLM_PROVIDER == "dify":
        if not ENABLE_DIFY:
            return "設定エラー: LLM_PROVIDER='dify' ですが、ENABLE_DIFY=False になっています。.envを確認してください。"
        print(f"[LLM] Difyプロバイダーを使用")
        return get_dify_response(prompt)
    
    else:
        error_msg = f"不明なLLMプロバイダー: {LLM_PROVIDER}"
        print(f"エラー: {error_msg}")
        return f"設定エラー: {error_msg}。.envファイルを確認してください。"


# ==========================================================
# 7. Outgoing Webhook 関連関数
# ==========================================================

def send_outgoing_webhook(user_prompt, ai_response, user_id=None, source="mic"):
    """
    LLM応答を外部エンドポイントに送信する
    
    Args:
        user_prompt (str): ユーザーの入力テキスト
        ai_response (str): LLMからの応答テキスト
        user_id (str): ユーザーID (オプション)
        source (str): 入力ソース ("mic" または "webhook")
    
    Returns:
        bool: 送信成功時True、失敗時False
    """
    
    if not ENABLE_OUTGOING_WEBHOOK:
        return False
    
    if not OUTGOING_WEBHOOK_URL:
        print("警告: Outgoing WebhookのURLが設定されていません。")
        return False
    
    # ペイロードの構築
    payload = {
        "timestamp": time.time(),
        "user_id": user_id or DIFY_USER_ID,
        "source": source,  # "mic" or "webhook"
        "user_input": user_prompt,
        "ai_response": ai_response,
        "llm_provider": LLM_PROVIDER,  # ★ どのプロバイダーを使用したか記録
        "agent_version": "1.0"
    }
    
    # ヘッダーの構築
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "DifyAgent/1.0"
    }
    
    # 認証トークンがあれば追加
    if OUTGOING_WEBHOOK_AUTH_TOKEN:
        headers["Authorization"] = f"Bearer {OUTGOING_WEBHOOK_AUTH_TOKEN}"
    
    # リトライロジック付きで送信
    for attempt in range(OUTGOING_WEBHOOK_RETRY_COUNT):
        try:
            print(f"📤 Outgoing Webhook 送信中 (試行 {attempt + 1}/{OUTGOING_WEBHOOK_RETRY_COUNT}): {OUTGOING_WEBHOOK_URL}")
            
            response = requests.post(
                OUTGOING_WEBHOOK_URL,
                json=payload,
                headers=headers,
                timeout=OUTGOING_WEBHOOK_TIMEOUT
            )
            
            response.raise_for_status()
            
            print(f"✅ Outgoing Webhook 送信成功: ステータス {response.status_code}")
            return True
            
        except requests.exceptions.Timeout:
            print(f"⏱️ Outgoing Webhook タイムアウト (試行 {attempt + 1})")
            if attempt < OUTGOING_WEBHOOK_RETRY_COUNT - 1:
                time.sleep(1)  # リトライ前に1秒待機
                
        except requests.exceptions.RequestException as e:
            print(f"❌ Outgoing Webhook 送信エラー (試行 {attempt + 1}): {e}")
            if attempt < OUTGOING_WEBHOOK_RETRY_COUNT - 1:
                time.sleep(1)
                
        except Exception as e:
            print(f"❌ Outgoing Webhook 予期せぬエラー: {e}")
            break
    
    print("❌ Outgoing Webhook 送信失敗: 全てのリトライが失敗しました。")
    return False


def send_outgoing_webhook_async(user_prompt, ai_response, user_id=None, source="mic"):
    """
    Outgoing Webhookを非同期で送信する (音声出力を遅延させない)
    """
    thread = threading.Thread(
        target=send_outgoing_webhook,
        args=(user_prompt, ai_response, user_id, source),
        daemon=True
    )
    thread.start()


# ==========================================================
# 8. コア処理関数
# ==========================================================

def process_and_respond_core(user_prompt, user_id=None, source="mic"):
    """
    STT入力またはWeb API入力されたプロンプトを処理し、応答を生成・発話する
    
    Args:
        user_prompt (str): ユーザーの入力テキスト
        user_id (str): ユーザーID
        source (str): 入力ソース ("mic" または "webhook")
    """
    
    global last_interaction_time
    
    dify_user = user_id if user_id and user_id != DIFY_USER_ID else DIFY_USER_ID
    
    # 1. ★ 応答生成 (LLMプロバイダーを自動選択)
    ai_response_text = get_llm_response(user_prompt)
    
    # 2. 応答の発話
    text_to_speech(ai_response_text)
    
    # 3. ★ Outgoing Webhook 送信 (非同期)
    if ENABLE_OUTGOING_WEBHOOK:
        send_outgoing_webhook_async(
            user_prompt=user_prompt,
            ai_response=ai_response_text,
            user_id=dify_user,
            source=source
        )
    
    # 4. アイドルタイマーのリセット
    last_interaction_time = time.time()
    
    return ai_response_text


# ==========================================================
# 9. マイク監視/アイドルチャットスレッドの関数
# ==========================================================

def mic_listening_process_core():
    """マイク監視とアイドルチャットのメインループ(サーバー実行中にスレッドで実行される)"""
    
    global last_idle_sentence, quiet_mode_until_time, last_interaction_time
    
    print("🎤 音声監視スレッドを開始しました。")

    idle_interval_seconds = IDLE_CHAT_INTERVAL_SECONDS
    
    while True:
        
        # --- 休憩モード中の振る舞いチェック ---
        if time.time() < quiet_mode_until_time:
            # ★ ロックを取得してから処理 (口ずさみ処理)
            if HUM_SENTENCES and (time.time() - last_interaction_time) > 10 * 60: 
                if PROCESS_LOCK.acquire(blocking=False):
                    try:
                        hum_sentence = random.choice(HUM_SENTENCES)
                        print(f"\n--- 休憩中の口ずさみ ---")
                        text_to_speech(hum_sentence) 
                        last_interaction_time = time.time()
                    finally:
                        PROCESS_LOCK.release()
                
            time.sleep(1)
            continue
            
        # --- 通常のアイドルチャットチェック ---
        if IDLE_CHAT_INTERVAL_SECONDS > 0 and (time.time() - last_interaction_time) > idle_interval_seconds:
            if IDLE_SENTENCES:
                
                # ★ ロックを取得してから処理 (アイドルチャット発話)
                if PROCESS_LOCK.acquire(blocking=False):
                    try:
                        available_sentences = [s for s in IDLE_SENTENCES if s != last_idle_sentence]
                        if not available_sentences: 
                            available_sentences = IDLE_SENTENCES
                        idle_sentence = random.choice(available_sentences)
                        
                        print(f"\n--- アイドルチャット開始 ({(time.time() - last_interaction_time):.0f}秒経過) ---")
                        text_to_speech(idle_sentence)
                        last_interaction_time = time.time()
                        last_idle_sentence = idle_sentence
                        print(f"--- アイドルチャット終了 ---")
                        time.sleep(1)
                    finally:
                        PROCESS_LOCK.release()
                
                continue 
        
        # --- マイク入力処理 ---
        audio_path = recognize_speech_from_mic()
        if audio_path is None: 
            time.sleep(0.5)
            continue
            
        # --- STTと応答処理の実行 (ロックが必要な部分) ---
        if PROCESS_LOCK.acquire(blocking=True, timeout=1): # 1秒待機してロックを取得
            try:
                # マイク入力後のSTT処理
                user_text = speech_to_text(audio_path) 
                if user_text is None: 
                    time.sleep(0.5)
                    continue
                    
                # 起動キーワードチェック
                processed_text = user_text.lower().strip()
                triggered = False
                final_prompt = None
                
                for wake_word_key in WAKE_WORD_SET:
                    if processed_text.startswith(wake_word_key):
                        triggered = True
                        final_prompt = user_text[len(wake_word_key):].strip()
                        if len(user_text.strip()) > len(wake_word_key.strip()): 
                            final_prompt = user_text[len(wake_word_key):].strip()
                        else: 
                            final_prompt = "何かご用でしょうか?" 
                        break 

                if triggered:
                    prompt = final_prompt
                    
                    # 休憩キーワードの検出
                    if QUIET_KEYWORD.lower() in processed_text:
                        quiet_mode_until_time = time.time() + QUIET_DURATION_MINUTES * 60
                        text_to_speech(f"承知いたしました。{QUIET_DURATION_MINUTES}分間、小声で口ずさんで休憩していますね。ご集中ください。")
                        last_interaction_time = time.time()
                        continue
                        
                    # 終了処理 (音声入力のみで終了を許可)
                    if "さようなら" in processed_text or "おわり" in processed_text:
                        text_to_speech("さようなら。またお話ししましょう!")
                        os._exit(0) 

                    # ★ 応答生成と発話 (source="mic" を指定)
                    process_and_respond_core(prompt, DIFY_USER_ID, source="mic")
                    
                else:
                    print(f"待機中: キーワード'{WAKE_WORD_DISPLAY}'が検出されませんでした。")
                    
                time.sleep(0.5)

            finally:
                 # マイク処理が完了したら必ずロックを解放
                 PROCESS_LOCK.release()
        else:
            # ロック取得に失敗した場合(WebHookが処理中)、今回の音声入力をスキップ
            print("警告: WebHook処理中のため、マイク入力後の応答処理をスキップしました。")
            time.sleep(0.1)
