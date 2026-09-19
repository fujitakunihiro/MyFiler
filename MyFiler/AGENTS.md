# AGENTS.md

## 1. Project Overview

このプロジェクトでは、Windows上で動作する仕事用ファイラー「MyFiler」を開発する。

MyFilerの目的は、Windows Explorerを完全に置き換えることではない。

仕事中に多数のExplorerウィンドウやフォルダを開くことで、
「どのフォルダが何の作業用なのか分からなくなる」
「作業を切り替えた後、元の場所へ戻れない」
という問題を解決する。

中心となる概念は以下の2階層とする。

Workspace
└── Explorer Tab
└── Directory / Files

Workspaceは「作業単位」、Explorer Tabは「その作業で使用する場所」を表す。

例:

Panel開発
├── src
├── logs
├── spec
└── test

不具合 #1234
├── source
├── logs
└── evidence

## 2. Target Environment

対象環境:

* OS: Windows
* Language: Python 3
* GUI: tkinter / ttk
* Storage: JSON
* Runtime: ローカルPC
* Network: 使用禁止

原則としてPython標準ライブラリのみ使用する。

## 3. Dependency Policy

外部Pythonパッケージを使用してはならない。

禁止例:

* PyQt
* PySide
* requests
* pandas
* Flask
* FastAPI
* Electron
* Node.js依存
* 外部UIライブラリ
* 外部アイコンライブラリ

pip installを必要とする設計は禁止する。

使用可能な標準ライブラリ例:

* tkinter
* tkinter.ttk
* pathlib
* os
* subprocess
* json
* threading
* queue
* datetime
* shutil
* logging
* unittest

標準ライブラリ以外が必要だと判断した場合、勝手に導入せず理由を提示すること。

## 4. Security Requirements

本プロジェクトはセキュリティ制約の厳しい業務PCでの利用を想定する。

以下を絶対条件とする。

### Network

外部通信を実装してはならない。

禁止:

* HTTP通信
* HTTPS通信
* WebSocket
* Cloud API
* AI API
* 外部サーバ接続
* 自動アップデート
* テレメトリ
* 利用状況送信
* クラッシュ情報送信

ネットワーク機能を将来用として実装することも禁止する。

### File Data

V1ではファイル内容を解析・収集・保存しない。

基本的に扱ってよい情報:

* ファイル名
* フルパス
* 拡張子
* サイズ
* 更新日時
* ディレクトリ情報

ファイル内容を設定JSONや別ファイルへコピーしてはならない。

### Configuration

アプリケーション設定はローカルJSONへ保存する。

保存対象例:

* Workspace
* Explorer Tab
* 最後に開いていたディレクトリ
