# このスクリプトは、CPU、メモリ、I/Oの負荷テストを行い、
# ターゲットプログラムを起動してそのパフォーマンスを測定します。
# 汎用的に使えるように設計されています。
# 必要なライブラリをインポートします。

import subprocess
import threading
import time
import os
import logging
import psutil


# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s',
    handlers=[
        logging.FileHandler('test_log.txt', mode='w', encoding='utf-8'),  # mode='w'で毎回クリア
        logging.StreamHandler()
    ]
)

# 停止フラグをグローバルで用意
stop_event = threading.Event()

# CPU負荷をかける関数。duration秒間、CPUに計算負荷を与え続けます。
def cpu_stress(duration):
    end = time.time() + duration
    while time.time() < end:
        if stop_event.is_set():
            break
        _ = sum(i*i for i in range(10000))  # 10000回の計算を繰り返すことでCPUを使う

# メモリ負荷をかける関数。size_mbで指定したMB分のメモリをduration秒間確保します。
def memory_stress(size_mb, duration):
    end = time.time() + duration
    data = []
    while time.time() < end:
        if stop_event.is_set():
            break
        data.append(bytearray(1024 * 1024))  # 1MB分のバイト配列を追加
        if len(data) > size_mb:
            data = []  # 指定サイズを超えたら解放して再度確保

# I/O負荷をかける関数。指定ファイルにduration秒間1MBずつランダムデータを書き込みます。
def io_stress(file_path, duration):
    end = time.time() + duration
    with open(file_path, "wb") as f:
        while time.time() < end:
            if stop_event.is_set():
                break
            f.write(os.urandom(1024 * 1024))  # 1MB書き込み
            f.flush()  # データをディスクに即時書き出し
            f.seek(0)  # ファイル先頭に戻ることで上書きし続ける

# 各種負荷テスト関数をスレッドで実行するためのラッパー関数。
def monitor_thread(target, *args):
    try:
        target(*args)
    except Exception as e:
        logging.error(f"Error in {target.__name__}: {e}")

# 負荷テストのメイン処理を呼び出す関数。
def run_load_test():
    # 負荷テスト本体を直接ここで実行する
    threads = []
    test_duration = 300  # 負荷テスト時間を300秒に調整
    threads.append(threading.Thread(target=cpu_stress, args=(test_duration,)))
    threads.append(threading.Thread(target=memory_stress, args=(100, test_duration)))
    threads.append(threading.Thread(target=io_stress, args=("io_test.tmp", test_duration)))
    
    for t in threads:
        t.start()
    
    # メインスレッドでリソース使用率を監視
    end_time = time.time() + test_duration
    while time.time() < end_time and not stop_event.is_set():
        log_resource_usage()
        time.sleep(1)
    
    stop_event.set()  # 負荷テスト終了を通知
    for t in threads:
        t.join()
    
    # 一時ファイルの削除
    if os.path.exists("io_test.tmp"):
        try:
            os.remove("io_test.tmp")
        except:
            pass

# リソース使用状況をログに記録する関数
def log_resource_usage():
    cpu = psutil.cpu_percent(interval=1)
    mem = psutil.virtual_memory().percent
    disk = psutil.disk_usage('.').percent
    logging.info(f"CPU使用率: {cpu}%, メモリ使用率: {mem}%, ディスク(I/O)使用率: {disk}%")

# メイン関数。ターゲットプログラムの起動と負荷テストの開始・終了を管理します。
def main(stop_event_arg=None):
    global stop_event
    if stop_event_arg is not None:
        stop_event = stop_event_arg
    
    # 対象プログラムのパス
    target_cmd = ["python", "main.py"]

    try:
        # 対象プログラムを起動
        proc = subprocess.Popen(target_cmd)
        logging.info("ターゲットプログラムを起動しました")

        # 負荷テストを別スレッドで開始
        load_test_thread = threading.Thread(target=run_load_test)
        load_test_thread.start()

        try:
            # タイムアウトを負荷テスト時間+10秒に設定
            proc.wait(timeout=310)  # 300秒+10秒
        except subprocess.TimeoutExpired:
            logging.info("ターゲットプログラムを終了します")
            proc.terminate()
            try:
                proc.wait(timeout=5)  # 終了を最大5秒待つ
            except subprocess.TimeoutExpired:
                proc.kill()  # 強制終了
        
        logging.info("ターゲットプログラムが終了しました")
        
    finally:
        # 確実に停止処理を行う
        stop_event.set()
        if load_test_thread.is_alive():
            load_test_thread.join(timeout=5)
        logging.info("負荷テストも終了しました")
        
        # プロセスとスレッドの終了を確認
        if proc.poll() is None:
            proc.kill()
        
        # 一時ファイルの削除を試みる
        if os.path.exists("io_test.tmp"):
            try:
                os.remove("io_test.tmp")
            except:
                pass
        
        os._exit(0)  # 確実に終了
    



if __name__ == "__main__":
    main()