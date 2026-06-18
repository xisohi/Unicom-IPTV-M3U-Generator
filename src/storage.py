import sqlite3
import json as _json
from hashlib import md5
from os.path import isfile
from json import loads as json_loads
from datetime import datetime
from xml.etree.ElementTree import Element, SubElement, ElementTree


def pretty_xml(element, indent, newline, level=0):
    if element:
        if element.text is None or element.text.isspace():
            element.text = newline + indent * (level + 1)
        else:
            element.text = newline + indent * (
                level + 1
            ) + element.text.strip() + newline + indent * (level + 1)
    temp = list(element)
    for i, subelement in enumerate(temp):
        if i < len(temp) - 1:
            subelement.tail = newline + indent * (level + 1)
        else:
            subelement.tail = newline + indent * level
        pretty_xml(subelement, indent, newline, level + 1)


class Storage:
    def __init__(self, file_path):
        if not isfile(file_path):
            with sqlite3.connect(file_path) as conn:
                c = conn.cursor()
                c.executescript('''
CREATE TABLE overview(
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    channel_id      TEXT    NOT NULL,
    channel_name    TEXT    NOT NULL,
    date            TEXT    NOT NULL,
    hash            TEXT    NOT NULL
);

CREATE TABLE programme(
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    overview_id     INTEGER NOT NULL,
    channel_id      TEXT    NOT NULL,
    title           TEXT    NOT NULL,
    start           TEXT    NOT NULL,
    stop            TEXT    NOT NULL,
    FOREIGN KEY (overview_id) REFERENCES overview(id)
);

CREATE UNIQUE INDEX idx_channel_date ON overview (channel_id, date);
                ''')
                conn.commit()

        self.__file = file_path

    def save(self, channel_id, channel_name, epg_date, json_str):
        programs = json_loads(json_str)
        normalized = sorted(
            [(p['startTime'], p['endTime'], p['text']) for p in programs
             if all(k in p for k in ('startTime', 'endTime', 'text'))]
        )
        hash_val = md5(_json.dumps(normalized, ensure_ascii=False).encode()).hexdigest()

        with sqlite3.connect(self.__file) as conn:
            c = conn.cursor()
            date_str = epg_date.strftime('%Y-%m-%d')

            result = c.execute(
                'SELECT id, hash FROM overview WHERE date=? AND channel_id=?',
                (date_str, channel_id)
            ).fetchone()

            if result:
                oid, old_hash = result
                if hash_val == old_hash:
                    print(f"    {date_str[5:]} Up to date")
                    return
                c.execute('UPDATE overview SET hash=? WHERE id=?', (hash_val, oid))
                c.execute('DELETE FROM programme WHERE overview_id=?', (oid,))
                print(f"    {date_str[5:]} Updated")
            else:
                c.execute(
                    'INSERT INTO overview (channel_id, channel_name, date, hash) VALUES (?,?,?,?)',
                    (channel_id, channel_name, date_str, hash_val)
                )
                conn.commit()
                result = c.execute(
                    'SELECT id FROM overview WHERE date=? AND channel_id=?',
                    (date_str, channel_id)
                ).fetchone()
                oid = result[0] if result else None
                if oid is None:
                    return
                print(f"    {date_str[5:]} Cached")

            insert_list = []
            for start_time, end_time, title in normalized:
                insert_list.append((oid, channel_id, title, start_time, end_time))

            c.executemany(
                'INSERT INTO programme (overview_id, channel_id, title, start, stop) VALUES (?,?,?,?,?)',
                insert_list
            )
            conn.commit()

    def epg_generator(self, file_path, channels, start, end):
        start_date = start.strftime('%Y-%m-%d')
        end_date = end.strftime('%Y-%m-%d')

        root = Element('tv')
        root.attrib['generator-info-name'] = 'stbmock'

        with sqlite3.connect(self.__file) as conn:
            c = conn.cursor()

            for ch_id, ch_name in channels:
                ch_elem = SubElement(root, 'channel')
                ch_elem.attrib['id'] = ch_id
                dn = SubElement(ch_elem, 'display-name')
                dn.attrib['lang'] = 'zh'
                dn.text = ch_name

                rows = c.execute(
                    'SELECT id FROM overview WHERE date>=? AND date<? AND channel_id=? ORDER BY date',
                    (start_date, end_date, ch_id)
                ).fetchall()

                for row in rows:
                    oid = row[0]
                    progs = c.execute(
                        'SELECT title, start, stop FROM programme WHERE overview_id=? ORDER BY start',
                        (oid,)
                    ).fetchall()

                    for title, prog_start, prog_stop in progs:
                        try:
                            dt_start = datetime.strptime(prog_start, '%Y-%m-%d %H:%M:%S')
                            dt_stop = datetime.strptime(prog_stop, '%Y-%m-%d %H:%M:%S')
                        except ValueError:
                            continue

                        pe = SubElement(root, 'programme')
                        pe.attrib['start'] = dt_start.strftime('%Y%m%d%H%M%S') + ' +0800'
                        pe.attrib['stop'] = dt_stop.strftime('%Y%m%d%H%M%S') + ' +0800'
                        pe.attrib['channel'] = ch_id
                        te = SubElement(pe, 'title')
                        te.attrib['lang'] = 'zh'
                        te.text = title
                        SubElement(pe, 'desc').attrib['lang'] = 'zh'

        pretty_xml(root, '  ', '\n')
        tree = ElementTree(root)
        tree.write(file_path, encoding='utf-8', xml_declaration=True)
