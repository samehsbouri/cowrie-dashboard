import os
import json
from flask import Flask, render_template, jsonify, send_file
from datetime import datetime

app = Flask(__name__)

LOGS_DIR = os.environ.get('LOGS_DIR', '/cowrie/logs')
STATE_DIR = os.environ.get('STATE_DIR', '/cowrie/var/lib/cowrie')


@app.route('/api/debug')
def debug_paths():
    return jsonify({
        'LOGS_DIR': LOGS_DIR,
        'STATE_DIR': STATE_DIR,
        'logs_exists': os.path.exists(LOGS_DIR),
        'state_exists': os.path.exists(STATE_DIR),
        'cowrie_json_exists': os.path.exists(os.path.join(LOGS_DIR, 'cowrie.json')),
        'logs_dir_contents': os.listdir(LOGS_DIR) if os.path.exists(LOGS_DIR) else [],
    })


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/sessions')
def get_sessions():
    json_file = os.path.join(LOGS_DIR, 'cowrie.json')
    sessions = []
    
    if os.path.exists(json_file):
        with open(json_file, 'r') as f:
            for line in f:
                try:
                    entry = json.loads(line.strip())
                    if entry.get('eventId') == 'cowrie.session.connect':
                        sessions.append({
                            'session': entry.get('session'),
                            'timestamp': entry.get('timestamp'),
                            'src_ip': entry.get('src_ip'),
                            'dst_ip': entry.get('dst_ip'),
                            'dst_port': entry.get('dst_port'),
                            'protocol': entry.get('protocol', 'ssh'),
                            'hassh': entry.get('hassh'),
                            'ssh_version': entry.get('ssh_version'),
                        })
                    elif entry.get('eventId') == 'cowrie.login.success':
                        sid = entry.get('session')
                        for s in sessions:
                            if s['session'] == sid:
                                s['username'] = entry.get('username')
                                s['password'] = entry.get('password')
                    elif entry.get('eventId') == 'cowrie.session.closed':
                        sid = entry.get('session')
                        for s in sessions:
                            if s['session'] == sid:
                                s['duration'] = entry.get('duration')
                                s['closed'] = True
                except json.JSONDecodeError:
                    continue
    
    sessions.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
    return jsonify(sessions)


@app.route('/api/session/<session_id>')
def get_session(session_id):
    json_file = os.path.join(LOGS_DIR, 'cowrie.json')
    commands = []
    tty_file = None
    
    if os.path.exists(json_file):
        with open(json_file, 'r') as f:
            for line in f:
                try:
                    entry = json.loads(line.strip())
                    if entry.get('session') == session_id:
                        event = entry.get('eventId', '')
                        if event == 'cowrie.command.input':
                            commands.append({
                                'timestamp': entry.get('timestamp'),
                                'input': entry.get('input'),
                            })
                        elif event == 'cowrie.command.success':
                            commands.append({
                                'timestamp': entry.get('timestamp'),
                                'output': entry.get('output', ''),
                                'success': True,
                            })
                        elif event == 'cowrie.session.closed':
                            tty_file = entry.get('ttylog')
                except json.JSONDecodeError:
                    continue
    
    commands.sort(key=lambda x: x.get('timestamp', ''))
    return jsonify({
        'session_id': session_id,
        'commands': commands,
        'tty_file': tty_file
    })


@app.route('/api/downloads')
def get_downloads():
    downloads_dir = os.path.join(STATE_DIR, 'downloads')
    downloads = []
    
    if os.path.exists(downloads_dir):
        for f in os.listdir(downloads_dir):
            filepath = os.path.join(downloads_dir, f)
            if os.path.isfile(filepath):
                stat = os.stat(filepath)
                downloads.append({
                    'filename': f,
                    'size': stat.st_size,
                    'timestamp': datetime.fromtimestamp(stat.st_mtime).isoformat()
                })
    
    downloads.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
    return jsonify(downloads)


@app.route('/api/download/<filename>')
def download_file(filename):
    downloads_dir = os.path.join(STATE_DIR, 'downloads')
    filepath = os.path.join(downloads_dir, filename)
    if os.path.exists(filepath):
        return send_file(filepath, as_attachment=True)
    return jsonify({'error': 'File not found'}), 404


@app.route('/api/tty/<session_id>')
def get_tty(session_id):
    tty_dir = os.path.join(STATE_DIR, 'tty')
    
    if os.path.exists(tty_dir):
        for f in os.listdir(tty_dir):
            if session_id in f:
                filepath = os.path.join(tty_dir, f)
                with open(filepath, 'r') as fp:
                    return jsonify(json.load(fp))
    
    json_file = os.path.join(LOGS_DIR, 'cowrie.json')
    if os.path.exists(json_file):
        with open(json_file, 'r') as f:
            for line in f:
                try:
                    entry = json.loads(line.strip())
                    if entry.get('session') == session_id and entry.get('eventId') == 'cowrie.session.closed':
                        tty_path = entry.get('ttylog')
                        if tty_path and os.path.exists(tty_path):
                            with open(tty_path, 'r') as fp:
                                return jsonify(json.load(fp))
                except json.JSONDecodeError:
                    continue
    
    return jsonify({'error': 'TTY log not found'}), 404


@app.route('/api/stats')
def get_stats():
    json_file = os.path.join(LOGS_DIR, 'cowrie.json')
    
    total_sessions = 0
    unique_ips = set()
    total_commands = 0
    downloads_count = 0
    
    downloads_dir = os.path.join(STATE_DIR, 'downloads')
    if os.path.exists(downloads_dir):
        downloads_count = len([f for f in os.listdir(downloads_dir) if os.path.isfile(os.path.join(downloads_dir, f))])
    
    if os.path.exists(json_file):
        with open(json_file, 'r') as f:
            for line in f:
                try:
                    entry = json.loads(line.strip())
                    event = entry.get('eventId', '')
                    if event == 'cowrie.session.connect':
                        total_sessions += 1
                        if entry.get('src_ip'):
                            unique_ips.add(entry.get('src_ip'))
                    elif event == 'cowrie.command.input':
                        total_commands += 1
                except json.JSONDecodeError:
                    continue
    
    return jsonify({
        'total_sessions': total_sessions,
        'unique_ips': len(unique_ips),
        'total_commands': total_commands,
        'downloads': downloads_count
    })


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8443, ssl_context=('cert.pem', 'key.pem'))