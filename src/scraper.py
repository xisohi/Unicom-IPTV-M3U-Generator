import sys
from Crypto.Cipher import DES
from random import randint
from requests import Session
from requests.adapters import HTTPAdapter
from time import sleep
from urllib.parse import urlparse
from re import compile, findall
from os.path import dirname, join, isfile
from os import environ, getcwd
from datetime import datetime, timedelta, timezone
from xml.sax.saxutils import escape
import yaml
import json as _json

sys.path.insert(0, dirname(dirname(__file__)))


def _ts():
    return datetime.now().strftime('%H:%M:%S')


def log(msg):
    print(f"[{_ts()}] {msg}")


def get_paths():
    return environ.get('DATA_DIR', getcwd())


def load_config(path):
    with open(path, encoding='utf-8') as f:
        return yaml.safe_load(f)


def encrypt(encryptToken, secret, userId, stbId, ipaddr, mac, rand_val=None):
    r = rand_val if rand_val is not None else randint(0, 99999999)
    payload = f"{r:08d}${encryptToken}${userId}${stbId}${ipaddr}${mac}$$CTC".encode("ascii")
    key = secret.encode("ascii")
    pad_len = 8 - (len(payload) % 8)
    payload = payload + bytes([pad_len]) * pad_len
    cipher = DES.new(key, DES.MODE_ECB)
    encrypted = cipher.encrypt(payload)
    return encrypted.hex().upper()


def get_encrypt_token(session, server, userId, headers):
    for i in range(3):
        try:
            resp = session.post(
                f'http://{server}/EPG/jsp/authLoginHWCU.jsp',
                data={'UserID': userId, 'VIP': ''},
                headers=headers,
            )
        except Exception as e:
            log(f"Attempt {i + 1} failed: {e}")
            if i == 2:
                return None
            sleep(5)
            continue

        if not resp.ok:
            log(f"Attempt {i + 1} failed: HTTP {resp.status_code}")
            if i == 2:
                return None
            sleep(5)
            continue

        m = compile(r'var EncryptToken = "([A-F0-9]{32})"').search(resp.text)
        if not m:
            snippet = resp.text[:200].replace('\n', ' ').strip()
            log(f"Attempt {i + 1}: EncryptToken not found, response: {snippet}")
            if i == 2:
                return None
            sleep(5)
            continue

        log("EncryptToken obtained successfully")
        return m.group(1)

    return None


def do_auth(session, server, userId, password, stbId, mac, encryptToken, ipaddr, cfg, headers):
    authenticator = encrypt(encryptToken, password, userId, stbId, ipaddr, mac)

    data = {
        'UserID': userId,
        'Lang': cfg['lang'],
        'SupportHD': cfg['supportHD'],
        'NetUserID': '',
        'Authenticator': authenticator,
        'STBType': cfg['stbType'],
        'STBVersion': cfg['stbVersion'],
        'conntype': cfg['conntype'],
        'STBID': stbId,
        'templateName': cfg['templateName'],
        'areaId': cfg['areaId'],
        'userToken': encryptToken,
        'userGroupId': '',
        'productPackageId': '',
        'mac': mac,
        'SoftwareVersion': cfg['softwareVersion'],
        'VIP': '',
    }

    for i in range(3):
        try:
            resp = session.post(
                f'http://{server}/EPG/jsp/ValidAuthenticationHWCU.jsp',
                data=data,
                headers=headers,
            )
        except Exception as e:
            log(f"Auth attempt {i + 1} failed: {e}")
            if i == 2:
                return None
            sleep(20)
            continue

        if not resp.ok:
            log(f"Auth attempt {i + 1} failed: HTTP {resp.status_code}")
            if i == 2:
                return None
            sleep(20)
            continue

        m = compile(r"CUSetConfig\('UserToken','([^']+)'\)").search(resp.text)
        if not m:
            log(f"Auth attempt {i + 1} failed: UserToken not found")
            if i == 2:
                return None
            sleep(20)
            continue

        log("Authentication successful")
        return m.group(1)

    return None


def get_channel_list(session, server, userId, userToken, cfg, headers):
    data = {
        'conntype': cfg['conntype'],
        'UserToken': userToken,
        'tempKey': '',
        'stbid': cfg['stbidShort'],
        'SupportHD': cfg['supportHD'],
        'UserID': userId,
        'Lang': '1',
    }

    resp = session.post(
        f'http://{server}/EPG/jsp/getchannellistHWCU.jsp',
        data=data,
        headers=headers,
    )

    if not resp.ok:
        log(f"Failed to get channel list: HTTP {resp.status_code}")
        return None

    entries = findall(r"iRet = Authentication\.CUSetConfig\('Channel','(.*?)'\);", resp.text)

    channels = []
    for entry in entries:
        pairs = dict(findall(r'(\w+)="([^"]*?)"', entry))
        channels.append(pairs)

    channels.sort(key=lambda c: int(c.get('UserChannelID', 0)))
    log(f"Parsed {len(channels)} channels")
    return channels


def write_channels_txt(channels, output_path):
    with open(output_path, 'w', encoding='utf-8') as f:
        for ch in channels:
            f.write(ch.get('ChannelName', '') + '\n')
    log(f"Channel reference saved: {output_path}")


def generate_m3u(channels, config_channels, igmp_cfg, output_path):
    ch_filter = None
    if config_channels:
        ch_filter = {c['original']: c for c in config_channels}

    entries = []
    max_chno = 0

    for ch in channels:
        chName = ch.get('ChannelName', '')
        if ch_filter and chName not in ch_filter:
            continue

        cfg_ch = ch_filter.get(chName) if ch_filter else None
        display_name = cfg_ch['name'] if cfg_ch else chName
        chno = int(cfg_ch['chno']) if cfg_ch and cfg_ch.get('chno') else 0

        if chno > max_chno:
            max_chno = chno

        entries.append({
            'ch': ch,
            'display_name': display_name,
            'chno': chno,
            'cfg_ch': cfg_ch,
        })

    for e in entries:
        if e['chno'] == 0:
            max_chno += 1
            e['chno'] = max_chno

    entries.sort(key=lambda e: e['chno'])

    lines = [
        '#EXTM3U',
        '#KODIPROP:inputstream=inputstream.ffmpegdirect',
    ]

    for e in entries:
        ch = e['ch']
        chId = ch.get('ChannelID', '')
        chUrl = ch.get('ChannelURL', '')
        tsUrl = ch.get('TimeShiftURL', '')
        display_name = e['display_name']
        chNo = str(e['chno'])

        if chUrl.startswith('igmp://'):
            addr = chUrl[7:]
            proxy_url = f'http://{igmp_cfg["host"]}:{igmp_cfg["port"]}/rtp/{addr}'
        else:
            proxy_url = chUrl

        extinf = f'#EXTINF:0 tvg-id="{chId}" tvg-name="{display_name}" tvg-chno="{chNo}"'

        if tsUrl:
            extinf += f' catchup="default" catchup-source="{tsUrl}&playseek={{utc:YmdHMS}}-{{utcend:YmdHMS}}"'
        else:
            log(f"  {display_name}: missing catchup URL")

        extinf += f',{display_name}'
        lines.append(extinf)
        lines.append(proxy_url)

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines) + '\n')

    log(f"M3U saved: {output_path} ({len(entries)} channels)")


class CombinedSendAdapter(HTTPAdapter):
    def init_poolmanager(self, *args, **kwargs):
        kwargs.setdefault('socket_options', [])
        return super().init_poolmanager(*args, **kwargs)


def get_esaas_channel_map(session, esaas_host, area_code):
    for attempt in range(3):
        try:
            resp = session.post(
                f'http://{esaas_host}/esaas/v2/live/channel',
                json={"timestamp": "0", "areaCode": area_code},
                headers={'User-Agent': 'okhttp/3.10.0'},
                timeout=10,
            )
        except Exception as e:
            if attempt == 2:
                log(f"Failed to get ESAAS channel mapping: {e}")
                return {}
            sleep(2)
            continue
        if not resp.ok:
            if attempt == 2:
                log("Failed to get ESAAS channel mapping")
                return {}
            sleep(2)
            continue
        break
    data = resp.json()
    channel_map = {}
    for group in data.get('data', []):
        for ch in group.get('channelData', []):
            ch_no = ch.get('channelNumber', '')
            ch_id = ch.get('channelId', '')
            ch_name = ch.get('channelName', '')
            if ch_no:
                channel_map[ch_no] = {'channelId': ch_id, 'channelName': ch_name}
    log(f"ESAAS channel map: {len(channel_map)} channels")
    return channel_map


def fetch_epg_for_channel(session, esaas_host, channel_id, start_date, end_date):
    for attempt in range(3):
        try:
            resp = session.post(
                f'http://{esaas_host}/esaas/v1/live/program',
                json={
                    "startTime": start_date,
                    "endTime": end_date,
                    "channelId": channel_id,
                    "payed": "true",
                },
                headers={'User-Agent': 'okhttp/3.10.0'},
                timeout=10,
            )
        except Exception as e:
            if attempt == 2:
                log(f"    Fetch failed after 3 attempts: {e}")
                return None
            sleep(2)
            continue
        if not resp.ok:
            if attempt == 2:
                return None
            sleep(2)
            continue
        break
    data = resp.json()
    all_programs = []
    for ch_entry in data.get('data', {}).get('channels', []):
        for day_entry in ch_entry.get('data', []):
            prog_list = day_entry.get('programs', [])
            if prog_list:
                date_str = day_entry.get('systemDate', '')
                all_programs.append((date_str, _json.dumps(prog_list, ensure_ascii=False)))
    return all_programs


def process(config_path=None, data_dir=None):
    if data_dir is None:
        data_dir = get_paths()
    if config_path is None:
        config_path = join(data_dir, 'config.yaml')
    if not isfile(config_path):
        log(f"Config not found: {config_path}")
        return
    cfg = load_config(config_path)

    login_cfg = cfg['login']
    epg_cfg = cfg['epg']
    config_channels = cfg.get('channels', [])

    server = login_cfg['server']
    userId = login_cfg['userId']
    password = login_cfg['password']
    stbId = login_cfg['stbId']
    mac = login_cfg['mac']
    ipaddr = login_cfg['ipaddr']
    headers = login_cfg['headers']
    igmp_cfg = login_cfg['igmp']

    session = Session()

    log("Connecting to EDS server...")
    resp = session.get(
        f'http://{server}/EDS/jsp/AuthenticationURL?UserID={userId}&Action=Login',
        headers=headers,
    )
    if not resp.ok:
        log("Failed to connect to EDS server")
        return

    epg_server = urlparse(resp.url).netloc
    log(f"EPG server: {epg_server}")

    log("Getting EncryptToken...")
    encryptToken = get_encrypt_token(session, epg_server, userId, headers)
    if not encryptToken:
        return

    log("Authenticating...")
    userToken = do_auth(session, epg_server, userId, password, stbId, mac, encryptToken, ipaddr, login_cfg, headers)
    if not userToken:
        return

    log(f"UserToken: {userToken}")

    log("Getting channel list...")
    all_channels = get_channel_list(session, epg_server, userId, userToken, login_cfg, headers)
    if not all_channels:
        return

    channels_txt_path = join(data_dir, 'channels.txt')
    write_channels_txt(all_channels, channels_txt_path)

    m3u_path = join(data_dir, 'iptv.m3u')
    generate_m3u(all_channels, config_channels, igmp_cfg, m3u_path)

    log("Getting ESAAS channel mapping...")
    esaas_host = epg_cfg['esaasHost'] if 'esaasHost' in epg_cfg else '139.215.93.40:3100'
    session.mount(f'http://{esaas_host}', CombinedSendAdapter())
    area_code = epg_cfg['areaCode']
    channel_map = get_esaas_channel_map(session, esaas_host, area_code)
    if not channel_map:
        return

    tz = timezone(timedelta(hours=8))
    today = datetime.now(tz)
    days_before = int(epg_cfg['daysBefore'])
    days_after = int(epg_cfg['daysAfter'])
    start_date = (today - timedelta(days=days_before)).strftime('%Y-%m-%d')
    end_date = (today + timedelta(days=days_after)).strftime('%Y-%m-%d')
    log(f"Fetching EPG from {start_date} to {end_date}...")

    from src.storage import Storage
    db_path = join(data_dir, 'epg.db')
    storage = Storage(db_path)

    ch_filter_map = {c['original']: c for c in config_channels} if config_channels else {}
    m3u_by_no = {}
    for ch in all_channels:
        ch_name = ch.get('ChannelName', '')
        if ch_filter_map and ch_name not in ch_filter_map:
            continue
        cfg_ch = ch_filter_map.get(ch_name)
        display = cfg_ch['name'] if cfg_ch else ch_name
        m3u_by_no[ch.get('UserChannelID', '')] = (display, ch_name, ch.get('ChannelID', ''))

    filtered_count = sum(1 for ch_no in channel_map if ch_no in m3u_by_no)
    selected_channels = []

    for i, (ch_no, info) in enumerate(channel_map.items(), 1):
        if ch_no not in m3u_by_no:
            continue
        display_name, m3u_name, ch_id = m3u_by_no[ch_no]

        selected_channels.append((ch_id, display_name))
        log(f"  [{len(selected_channels)}/{filtered_count}] {display_name}")

        day_data = fetch_epg_for_channel(session, esaas_host, info['channelId'], start_date, end_date)
        if day_data is None:
            log(f"    No EPG data")
            continue
        if not day_data:
            log(f"    No programs in range")
            continue

        for date_str, json_str in day_data:
            epg_date = datetime.strptime(date_str, '%Y-%m-%d')
            storage.save(ch_id, display_name, epg_date, json_str)

        sleep(0.1)

    if selected_channels:
        epg_path = join(data_dir, 'epg.xml')
        dt_start = today - timedelta(days=days_before)
        dt_end = today + timedelta(days=days_after)
        storage.epg_generator(epg_path, selected_channels, dt_start, dt_end)
        log(f"EPG XML saved: {epg_path}")
    else:
        log("No channels selected for EPG")


if __name__ == '__main__':
    process()
