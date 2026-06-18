import os
import sys
import json
import yaml
import threading
import logging
from datetime import datetime, timedelta
from io import StringIO
from queue import Queue

logging.getLogger('werkzeug').setLevel(logging.ERROR)

from flask import (
    Flask, render_template, request, jsonify,
    send_from_directory, Response, stream_with_context,
)

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from src.scraper import process as run_process

app = Flask(__name__,
    template_folder=os.path.join(os.path.dirname(__file__), 'templates'),
    static_folder=os.path.join(os.path.dirname(__file__), 'static'))

DATA_DIR = os.environ.get('DATA_DIR', '/data')
CONFIG_PATH = os.path.join(DATA_DIR, 'config.yaml')
SCHEDULE_PATH = os.path.join(DATA_DIR, 'scheduler.yaml')
LOGS_DIR = os.path.join(DATA_DIR, 'logs')

os.makedirs(LOGS_DIR, exist_ok=True)

run_status = {'state': 'idle', 'pid': 0}
log_queue = Queue()


def load_yaml(path):
    with open(path, encoding='utf-8') as f:
        return yaml.safe_load(f)


def save_yaml(path, data):
    with open(path, 'w', encoding='utf-8') as f:
        yaml.dump(data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)


def clean_old_logs():
    if not os.path.isdir(LOGS_DIR):
        return
    logs = sorted([f for f in os.listdir(LOGS_DIR) if f.endswith('.log')], reverse=True)
    for f in logs[7:]:
        os.remove(os.path.join(LOGS_DIR, f))


def load_schedule():
    if os.path.isfile(SCHEDULE_PATH):
        with open(SCHEDULE_PATH, encoding='utf-8') as f:
            return yaml.safe_load(f)
    return {'enabled': False, 'cron': '0 6 * * *', 'last_run': None, 'last_status': None}


def save_schedule(data):
    with open(SCHEDULE_PATH, 'w', encoding='utf-8') as f:
        yaml.dump(data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)


def run_task(config_path, data_dir):
    global run_status
    run_status['state'] = 'running'
    log_file = os.path.join(LOGS_DIR, datetime.now().strftime('run_%Y%m%d_%H%M%S') + '.log')
    try:
        with open(log_file, 'a', encoding='utf-8') as lf:
            tee = Tee(StringIO(), lf)
            sys.stdout = tee
            sys.stderr = tee
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Run started")
            try:
                run_process(config_path=config_path, data_dir=data_dir)
            except Exception as e:
                print(f"[ERROR] {e}")
                run_status['state'] = 'error'
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Run finished")
    finally:
        sys.stdout = sys.__stdout__
        sys.stderr = sys.__stderr__
        clean_old_logs()
        sys.stdout = sys.__stdout__
        sys.stderr = sys.__stderr__
        log_queue.put('__END__')
        run_status['state'] = 'idle'
        sched = load_schedule()
        sched['last_run'] = datetime.now().isoformat()
        sched['last_status'] = 'success' if run_status['state'] != 'error' else 'error'
        save_schedule(sched)


class Tee:
    def __init__(self, *files):
        self.files = files
    def write(self, data):
        for f in self.files:
            f.write(data)
            f.flush()
        stripped = data.strip()
        if stripped:
            log_queue.put(stripped)
    def flush(self):
        for f in self.files:
            f.flush()


def get_data_dir():
    return DATA_DIR


# ── Routes ──────────────────────────────────────────────

@app.route('/')
def index():
    sched = load_schedule()
    return render_template('index.html', status=run_status, schedule=sched)


@app.route('/config', methods=['GET', 'POST'])
def config_page():
    if request.method == 'POST':
        data = {
            'login': {
                k: request.form.get(f'login.{k}', '')
                for k in ['server', 'userId', 'password', 'stbId', 'mac', 'ipaddr',
                          'conntype', 'stbType', 'stbVersion', 'softwareVersion',
                          'templateName', 'areaId', 'lang', 'supportHD', 'stbidShort']
            },
            'epg': {
                k: request.form.get(f'epg.{k}', '')
                for k in ['areaCode', 'daysBefore', 'daysAfter']
            },
        }
        data['login']['igmp'] = {
            'host': request.form.get('login.igmp.host', ''),
            'port': int(request.form.get('login.igmp.port', 4022)),
        }
        data['login']['headers'] = {
            k: request.form.get(f'login.headers.{k}', '')
            for k in ['User-Agent', 'Connection', 'X-Requested-With']
        }
        ch = load_yaml(CONFIG_PATH)
        data['channels'] = ch.get('channels', [])
        save_yaml(CONFIG_PATH, data)
        return jsonify({'ok': True})

    cfg = load_yaml(CONFIG_PATH)
    return render_template('config.html', cfg=cfg)


@app.route('/channels', methods=['GET', 'POST'])
def channels_page():
    if request.method == 'POST':
        channels = request.json or []
        cfg = load_yaml(CONFIG_PATH)
        cfg['channels'] = channels
        save_yaml(CONFIG_PATH, cfg)
        return jsonify({'ok': True})

    all_txt = os.path.join(DATA_DIR, 'channels.txt')
    all_names = []
    if os.path.isfile(all_txt):
        with open(all_txt, encoding='utf-8') as f:
            all_names = [line.strip() for line in f if line.strip()]

    cfg = load_yaml(CONFIG_PATH)
    selected = cfg.get('channels', [])
    selected_map = {c['original']: c for c in selected}
    return render_template('channels.html', all_names=all_names, selected=selected_map)


@app.route('/schedule', methods=['GET', 'POST'])
def schedule_page():
    if request.method == 'POST':
        data = {
            'enabled': request.form.get('enabled') == 'on',
            'cron': request.form.get('cron', '0 6 * * *'),
        }
        sched = load_schedule()
        sched.update(data)
        save_schedule(sched)
        from src.scheduler import restart_scheduler as _rs
        _rs()
        return jsonify({'ok': True})
    sched = load_schedule()
    return render_template('schedule.html', sched=sched)


@app.route('/run', methods=['POST'])
def trigger_run():
    if run_status['state'] == 'running':
        return jsonify({'error': 'Already running'}), 409
    t = threading.Thread(target=run_task, args=(CONFIG_PATH, DATA_DIR), daemon=True)
    t.start()
    return jsonify({'ok': True})


@app.route('/run/stream')
def run_stream():
    def generate():
        while True:
            line = log_queue.get()
            yield f'data: {line}\n\n'
            if line == '__END__':
                break
    return Response(stream_with_context(generate()), mimetype='text/event-stream')


@app.route('/status')
def get_status():
    return jsonify(run_status)


def log_status(path):
    try:
        with open(path, 'rb') as f:
            tail = f.read(500)
            if not tail:
                return 'unknown'
            content = tail.decode('utf-8', errors='replace')
            if 'ERROR' in content or 'Error' in content:
                return 'error'
            if 'Run finished' in content or 'Scheduled run finished' in content:
                return 'success'
            return 'unknown'
    except Exception:
        return 'unknown'


@app.route('/logs')
def logs_page():
    logs = []
    if os.path.isdir(LOGS_DIR):
        for fname in sorted(os.listdir(LOGS_DIR), reverse=True):
            if fname.endswith('.log'):
                path = os.path.join(LOGS_DIR, fname)
                size = os.path.getsize(path)
                ts = fname.replace('run_', '').replace('.log', '')
                try:
                    dt = datetime.strptime(ts, '%Y%m%d_%H%M%S')
                    display = dt.strftime('%Y-%m-%d %H:%M:%S')
                except ValueError:
                    display = fname
                logs.append({
                    'name': fname,
                    'display': display,
                    'size': size,
                    'status': log_status(path),
                })
    return render_template('logs.html', logs=logs)


@app.route('/logs/<name>')
def log_detail(name):
    path = os.path.join(LOGS_DIR, name)
    if not os.path.isfile(path):
        return 'No log', 404
    with open(path, encoding='utf-8') as f:
        content = f.read()
    return render_template('log_detail.html', name=name, content=content)


@app.route('/files/<name>')
def download_file(name):
    return send_from_directory(DATA_DIR, name)


def create_app():
    return app


if __name__ == '__main__':
    port = int(os.environ.get('WEB_PORT', '5000'))
    ssl_key = os.environ.get('SSL_CERT_KEY')
    ssl_ctx = (ssl_key,) if ssl_key and os.path.isfile(ssl_key) else None

    # Copy template config if not exists
    if not os.path.isfile(CONFIG_PATH):
        tmpl = os.path.join(os.path.dirname(__file__), '..', 'config.yaml')
        if os.path.isfile(tmpl):
            import shutil
            shutil.copy(tmpl, CONFIG_PATH)
            print(f"Template config copied to {CONFIG_PATH}")

    from src.scheduler import init_scheduler
    init_scheduler()

    proto = 'https' if ssl_ctx else 'http'
    print(f"Web UI started: {proto}://0.0.0.0:{port}")
    app.run(host='0.0.0.0', port=port, ssl_context=ssl_ctx, debug=False, threaded=True)
