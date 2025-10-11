# AI Staff Connector
メタバースと現実世界を橋渡しするハイブリッド型AI職員 | AI staff agent bridging virtual and physical worlds via voice interaction

## 📋 概要
### 開発経緯
- 大学内で、学生や教員が自然と集まり雑談や情報共有を行っていた場所に勤務していた派遣契約の職員が退職して以降、真っ暗な場所になったので、AIアバターによるAI職員（仮称 デカネさん）を配置することで、学生の居場所づくりに役立つか試むために開発。
- 前提として、なるべく無料で利用できるソフトウェアで構成する。
  - ビジネスにしたい場合、一部のソフトウェアにはエンタープライズライセンスがあるものもあるが、このソフトウェア自体でお金を稼ぐのではなく、運用支援も含めたソリューションビジネスに向く。

### 動かし方
[Wiki](https://github.com/kolinz/ai-staff-connector/wiki)をご覧ください。

### 主要機能
- メタバースまたは現実世界から得た音声での会話を、テキストに変換し、AIエージェント（Dify）から返答を得て、以下を実行する。
  - 返答結果を、AIアバターが音声で読み上げる。
  - Outgoing Webhoookで、別のシステムに転送する。
- カメラの認識結果やセンサーなどの値をIncoming Webhookを用いて、AIエージェント（Dify）に渡し、返答を得て、以下を実行する。
  - 返答結果を、AIアバターが音声で読み上げる
  - Outgoing Webhoookで、別のシステムに転送する。
- 一定時間、AIアバターを放置するとアイドル（待機状態）チャットを発動。
  - 環境変数ファイル .env で決めた時間毎に、環境変数ファイル .env で決めた複数の文章を、ランダムで読み上げる。
    - 標準の時間は1分。推奨は3～5分程度。
    - 読み上げる文章の例は、「授業で困っていることはありますか？」「お話相手を探しています！」など。
- 指定キーワードを、AIアバターに音声で指示すると休眠状態に移行
  - 環境変数ファイル .env で決めた時間、静かにしている。
  - 環境変数ファイル .env で決めた文章を、10分置きに話す。休眠状態で静かにしつつ、時々存在していることを主張する。
    - 読み上げる文章の例は、「ラララ〜、今日もいい天気だなぁ...」「フフン、デカネさんは最強だぞ...」など。
- AIアバターを介して、現実世界の教室とメタバース内のキャンパス（校舎）や教室をつなげる
  - AIアバターの運用環境をメタバースとしているために、実現が簡単。メタバース内のキャンパス（校舎）や教室は、自分で用意してください。たとえばUnityの無料アセットを使えば作ることができます。

### 動作に必要なハードウェア
#### 本ソフトウェアを動かす環境
- ディスプレイが利用できるPC(パソコン）または、サーバー
  - ノートPC、ディスプレイ付きのデスクトップPC、ディスプレイ付きのサーバーのいずれか１つを用意ということになります。
  - Windows または、Mac
    - Virtual Audio Cableと同等の機能を再現することができる人は、Liinux も可能
#### 現実世界の建物内にAI職員を表示する
- ノートPC、ディスプレイ付きのデスクトップPCのどちらかを用意してください。

### 動作に必要なソフトウェア
#### 運用するPCまたはサーバーに導入する
- Python（Python 3.12系で確認済み）
- Virtual Audio Cable（非商用なら無料）
- Node-RED
#### 運用形態としてオンプレミスまたはパブリッククラウドのどちらかで用意する
- AIエージェント <--必須
  - Dify
    - LLM/SLM <-- Difyをオンプレミス環境やパブリッククラウドのIaaSで運用する場合は、LLM/SLM を自分で運用しないといけない
      - Ollama または LM Stduio <-- LLM/SLMの運用にどちらかを使う
      - おすすめのLLM/SLM
        - IBM Granite 4
- Speech To Text(STT) <--下記から１つ
  - Faster Whisper（別途インストール不要）（オンプレミス運用ならこれ一択）
  - OpenAI API
  - IBM Watson Speech To Text
- Text To Speech(TTS) <--下記から１つ
  - VOICEVOX（オンプレミス運用ならこれ一択）
  - IBM Watson Text To Speech
#### AI職員を配置する
- メタバース内に建物を用意してください。
  - 推奨のメタバースは下記です。
    - Vket Cloud
    - Roomiq（以前のNTT DOOR）
    - Spatial 

## 🤖 AI-Assisted Development Notice
> **⚠️ このプロジェクトは実験的なものです**
> 
> このプロジェクトは、**生成AI** を使用して開発されました。以下の点にご注意ください：

### 実験的プロジェクトとしての位置づけ

このプロジェクトは以下の目的で公開されています：

✅ **学習・研究目的**
- 生成AIを活用した開発手法の実証
- 音声エージェント構築のリファレンス実装
- メタバース内の教室と、現実世界の教室やキャンパスとのハイブリッドによるAI職員の開発

⚠️ **本番環境での使用について**
- まずは開発環境やテスト環境で動作をご確認ください
- お使いの環境に合わせてカスタマイズできます
- 本番環境で使用する場合は、十分な検証を行ってください

## 🌟 実際の利用例

このプロジェクトは以下のような環境で活用されています：
- 個人の学習・研究プロジェクト
- 大学の研究室での音声インターフェース実験
- 大学内でのAI職員としての実証実験

## 📚 参考リンク

- [Dify公式ドキュメント](https://docs.dify.ai/)
- [Voicevox公式サイト](https://voicevox.hiroshiba.jp/)
- [Node-RED](https://nodered.org/)
- [Faster Whisper](https://github.com/SYSTRAN/faster-whisper)
- [OpenAI API](https://openai.com/ja-JP/index/openai-api/)
- [IBM Watson Speech To Text公式ドキュメント](https://cloud.ibm.com/docs/speech-to-text?topic=speech-to-text-about&locale=ja)
- [IBM Watson Text To Speech公式ドキュメント](https://cloud.ibm.com/docs/text-to-speech?topic=text-to-speech-about&locale=ja)
- [Ollama](https://ollama.com/)
- [LM Studio](https://lmstudio.ai/)
- [IBM Granite 4](https://www.ibm.com/granite/docs/models/granite)
- [Vket Cloud](https://cloud.vket.com/)
- [Roomiq](https://roomiq.jp/)
- [Spatial](https://www.spatial.io/)
