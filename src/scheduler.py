import os, sys
import yaml
import threading
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

DATA_DIR = os.environ.get('DATA_DIR', '/data')
SCHEDULE_PATH = os.path.join(DATA_DIR, 'scheduler.yaml')
CONFIG_PATH = os.path.join(DATA_DIR, 'config.yaml')
LOG_DIR = os.path.join(DATA_DIR, 'logs')

os.makedirs(LOG_DIR, exist_ok=True)

scheduler = BackgroundScheduler()
_run_lock = threading.Lock()


def load_schedule():
    if os.path.isfile(SCHEDULE_PATH):
        try:
            with open(SCHEDULE_PATH, encoding='utf-8') as f:
                return yaml.safe_load(f)
        except Exception:
            pass
    return {'enabled': False, 'cron': '0 6 * * *', 'last_run': None, 'last_status': None}


def clean_old_logs():
    if not os.path.isdir(LOG_DIR):
        return
    logs = sorted([f for f in os.listdir(LOG_DIR) if f.endswith('.log')], reverse=True)
    for f in logs[7:]:
        os.remove(os.path.join(LOG_DIR, f))


def run_job():
    if not _run_lock.acquire(False):
        return
    try:
        from src.scraper import process
        log_file = os.path.join(LOG_DIR, datetime.now().strftime('run_%Y%m%d_%H%M%S') + '.log')
        with open(log_file, 'a', encoding='utf-8') as lf:
            sys.stdout = lf
            sys.stderr = lf
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Scheduled run started")
            process(config_path=CONFIG_PATH, data_dir=DATA_DIR)
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Scheduled run finished")
            sys.stdout = sys.__stdout__
            sys.stderr = sys.__stderr__
        sched = load_schedule()
        sched['last_run'] = datetime.now().isoformat()
        sched['last_status'] = 'success'
        with open(SCHEDULE_PATH, 'w', encoding='utf-8') as f:
            yaml.dump(sched, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
    except Exception as e:
        print(f"[ERROR] Scheduled run: {e}")
    finally:
        clean_old_logs()
        _run_lock.release()


def restart_scheduler():
    scheduler.remove_all_jobs()
    sched = load_schedule()
    if sched.get('enabled'):
        parts = sched['cron'].strip().split()
        if len(parts) == 5:
            trigger = CronTrigger(
                minute=parts[0], hour=parts[1], day=parts[2],
                month=parts[3], day_of_week=parts[4],
                timezone='Asia/Shanghai'
            )
            scheduler.add_job(run_job, trigger, id='iptv_run', replace_existing=True)
            print(f"Scheduler enabled: {sched['cron']}")


def init_scheduler():
    scheduler.start()
    restart_scheduler()


def get_scheduler():
    return scheduler


def get_run_lock():
    return _run_lock
