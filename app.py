# =========================================================================
# ファイル名 : app.py
# 役割       : サーバー監視ダッシュボードのバックエンド（Flaskアプリ）
# 概要       : 動作中のPC・サーバーのリソース情報（CPU・メモリ・ディスク・
#              ネットワーク・プロセス）を psutil で取得し、JSON APIとして
#              フロントエンド（ブラウザ）に返す。
#
# 使い方     :
#   1) 依存ライブラリをインストール
#        pip install -r requirements.txt
#   2) このファイルを実行
#        python app.py
#   3) ブラウザで http://localhost:5000/ にアクセス
# =========================================================================

# ===== 必要なライブラリのインポート =====
# Flask         ：軽量なWebアプリフレームワーク
# render_template：HTMLテンプレートを描画する関数
# jsonify       ：Python辞書をJSON形式に変換するヘルパー
from flask import Flask, render_template, jsonify

# psutil ：CPU・メモリ・ディスクなどシステム情報を取得するライブラリ
import psutil

# Python標準ライブラリ
import platform   # OS情報やマシン情報の取得
import datetime   # 日時の取り扱い
import socket     # ホスト名の取得


# ===== Flaskアプリのインスタンス生成 =====
# __name__ は現在のファイル名を表す特殊変数。
# Flaskが静的ファイル・テンプレートの場所を判定するのに使う。
app = Flask(__name__)


# =========================================================================
#  ルーティング定義
# =========================================================================

# ----- トップページ：ダッシュボード本体を返す -----
# @app.route('/') は「URLが / にアクセスされたら、この関数を実行」という宣言。
@app.route('/')
def index():
    # templates/index.html を描画してブラウザに返す
    return render_template('index.html')


# ----- API：リソース情報をJSONで返す -----
# フロントエンドのJSが定期的にこのURLを叩いて最新情報を取得する。
@app.route('/api/stats')
def stats():
    """
    システム全体のリソース使用状況を取得し、JSONとして返す。
    """
    # ===== CPU情報 =====
    # cpu_percent(interval=0.5) は0.5秒間サンプリングしてCPU使用率(%)を返す
    cpu_percent = psutil.cpu_percent(interval=0.5)
    # 論理コア数（ハイパースレッディング含む）と物理コア数
    cpu_count_logical = psutil.cpu_count(logical=True)
    cpu_count_physical = psutil.cpu_count(logical=False)
    # コアごとの使用率（リストで返ってくる）
    cpu_per_core = psutil.cpu_percent(interval=0, percpu=True)

    # CPU周波数（取得できない環境ではNoneが返るのでtryで保護）
    try:
        freq = psutil.cpu_freq()
        cpu_freq_current = round(freq.current, 0) if freq else 0
        cpu_freq_max = round(freq.max, 0) if freq else 0
    except Exception:
        cpu_freq_current = 0
        cpu_freq_max = 0

    # ===== メモリ情報 =====
    # 物理メモリ（RAM）
    mem = psutil.virtual_memory()
    # スワップ（仮想メモリ）
    swap = psutil.swap_memory()

    # ===== ディスク情報 =====
    # 接続されている全パーティションを順番に確認し、使用状況を取得
    disk_partitions = []
    for part in psutil.disk_partitions(all=False):
        try:
            usage = psutil.disk_usage(part.mountpoint)
            disk_partitions.append({
                'device': part.device,           # 例：C:\, /dev/sda1
                'mountpoint': part.mountpoint,   # マウントポイント
                'fstype': part.fstype,           # ファイルシステム（NTFS, ext4など）
                'total': usage.total,            # 総容量(byte)
                'used': usage.used,              # 使用量(byte)
                'free': usage.free,              # 空き容量(byte)
                'percent': usage.percent         # 使用率(%)
            })
        except (PermissionError, OSError):
            # 取得できないディスクはスキップ（CDドライブ等）
            continue

    # ===== ネットワーク情報 =====
    # 起動からの累積送受信バイト数を取得
    net = psutil.net_io_counters()

    # ===== システム情報 =====
    # 起動時刻と稼働時間（uptime）の計算
    boot_time = datetime.datetime.fromtimestamp(psutil.boot_time())
    uptime = datetime.datetime.now() - boot_time

    # ===== レスポンスをJSON化して返す =====
    return jsonify({
        'cpu': {
            'percent': cpu_percent,
            'count_logical': cpu_count_logical,
            'count_physical': cpu_count_physical,
            'per_core': cpu_per_core,
            'freq_current': cpu_freq_current,
            'freq_max': cpu_freq_max,
        },
        'memory': {
            'total': mem.total,
            'used': mem.used,
            'available': mem.available,
            'percent': mem.percent,
        },
        'swap': {
            'total': swap.total,
            'used': swap.used,
            'percent': swap.percent,
        },
        'disk': disk_partitions,
        'network': {
            'bytes_sent': net.bytes_sent,
            'bytes_recv': net.bytes_recv,
            'packets_sent': net.packets_sent,
            'packets_recv': net.packets_recv,
        },
        'system': {
            'os': platform.system(),                         # Windows / Linux / Darwin
            'os_release': platform.release(),                # OSのリリース番号
            'hostname': socket.gethostname(),                # マシン名
            'machine': platform.machine(),                   # アーキテクチャ（x86_64など）
            'processor': platform.processor() or 'N/A',      # CPU名（取得できない場合はN/A）
            'python_version': platform.python_version(),
            'boot_time': boot_time.strftime('%Y-%m-%d %H:%M:%S'),
            'uptime_seconds': int(uptime.total_seconds()),
        },
        # 取得した時刻（フロント側で「最終更新」として表示する用）
        'timestamp': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
    })


# ----- API：プロセス一覧を返す（CPU使用率順、上位15件） -----
@app.route('/api/processes')
def processes():
    """
    実行中プロセスのうち、CPU使用率が高い順に上位15件を返す。
    """
    procs = []

    # process_iter() は実行中の全プロセスを順番に返すジェネレータ。
    # 引数attrsで取得したい情報だけ指定しておくと高速。
    for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent', 'username']):
        try:
            info = proc.info
            procs.append({
                'pid': info['pid'],
                'name': info['name'] or 'Unknown',
                # NoneのときはJSの数値計算で困るので0に変換
                'cpu_percent': round(info['cpu_percent'] or 0, 1),
                'memory_percent': round(info['memory_percent'] or 0, 2),
                'username': info['username'] or 'N/A',
            })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            # プロセスが既に終了している、または権限不足でアクセス不可の場合はスキップ
            continue

    # CPU使用率の高い順（降順）に並び替えて、上位15件だけ返す
    procs.sort(key=lambda p: p['cpu_percent'], reverse=True)
    return jsonify(procs[:15])


# =========================================================================
#  エントリーポイント
# =========================================================================
# このファイルが直接実行されたとき（python app.py）だけ動く。
# 他ファイルからimportされた場合は実行されない。
if __name__ == '__main__':
    # 学習用・ローカル確認用のため、安全側の初期値として自分のPCからのみアクセス可能にする。
    # LAN内へ公開する場合はREADMEの注意事項を確認し、debug=Falseのままhostを調整する。
    app.run(host='127.0.0.1', port=5000, debug=False)
