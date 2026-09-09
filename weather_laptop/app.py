"""One local observer/simulator process and a read-only dashboard."""
import argparse
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import threading
import time
from .core import DEFAULTS, Feed, Journal, validate_event, wallet
from .independent import Independent
from .contracts import contract_from_rules


@contextmanager
def lock(path):
    handle = path.open('a+b')
    handle.seek(0, 2)
    if not handle.tell():
        handle.write(b'0'); handle.flush()
    handle.seek(0)
    try:
        if os.name == 'nt':
            import msvcrt
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        handle.close()
        raise RuntimeError('Already running for this data directory') from None
    try:
        yield
    finally:
        handle.close()


def cycle(journal, feed, now):
    rows = feed.activity()
    fresh = journal.observe(rows, now)
    for identity, row in fresh:
        try:
            validate_event(row, now)
            if now - float(row['timestamp']) > 120:
                raise ValueError('Activity arrived too late; not replayed')
            market = feed.market(row)
            try:
                contract = contract_from_rules(market)
                row['station_day'] = contract['station'] + ':' + contract['date']
            except ValueError:
                pass
            book = feed.book(row)
            journal.evaluate(identity, row, book, time.time())
        except ValueError as exc:
            journal.reject(identity, str(exc))
        except Exception as exc:
            journal.reject(identity, 'Source unavailable: ' + type(exc).__name__)
    return {'page_full': len(rows) == 100, 'new_events': len(fresh),
            'coverage': 'Latest 100 activity records; intervening history may be incomplete'}


def run(config, root, port, once=False):
    root.mkdir(parents=True, exist_ok=True)
    with lock(root / 'process.lock'):
        journal = Journal(root / 'paper.sqlite', config)
        feed = Feed(config['source_wallet'])
        independent = Independent()
        # Abandoned observations are evidence, never delayed entry opportunities.
        journal.db.execute("UPDATE events SET state='interrupted',reason='Not replayed after restart' WHERE state='observed'")
        state = {'mode': 'paper', 'orders_enabled': False, 'status': 'starting', 'at': None}
        state_lock = threading.Lock()
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path == '/api/status':
                    with state_lock:
                        content = json.dumps(state).encode()
                    kind = 'application/json'
                elif self.path in ('/', '/bots'):
                    content = Path(__file__).with_name('index.html').read_bytes()
                    kind = 'text/html; charset=utf-8'
                else:
                    self.send_error(404); return
                self.send_response(200)
                self.send_header('Content-Type', kind)
                self.send_header('Cache-Control', 'no-store')
                self.send_header('X-Content-Type-Options', 'nosniff')
                self.end_headers(); self.wfile.write(content)
            def log_message(self, *_):
                pass
        server = None
        try:
            if not once:
                server = ThreadingHTTPServer(('127.0.0.1', port), Handler)
                threading.Thread(target=server.serve_forever, daemon=True).start()
                print(f'Paper observer and simulator: http://127.0.0.1:{port}/', flush=True)
            while not (root / 'STOP').exists():
                extra = {}
                error = None
                try:
                    extra = cycle(journal, feed, time.time())
                except Exception as exc:
                    error = type(exc).__name__
                if not (root / 'STOP').exists():
                    try:
                        extra['independent'] = independent.cycle(journal)
                    except Exception as exc:
                        extra['independent'] = {'at':time.time(),'status':'source_error','error':type(exc).__name__,'decisions':[]}
                with state_lock:
                    state.clear()
                    state.update(journal.snapshot(), at=time.time(), status='source_error' if error else 'observing', error=error, **extra)
                    temporary = root / 'status.tmp'
                    temporary.write_text(json.dumps(state, indent=2), encoding='utf-8')
                    temporary.replace(root / 'status.json')
                if once:
                    print(json.dumps(state, indent=2)); break
                for _ in range(config['poll_seconds']):
                    if (root / 'STOP').exists():
                        break
                    time.sleep(1)
        finally:
            if server:
                server.shutdown(); server.server_close()
            journal.db.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--configure', action='store_true')
    parser.add_argument('--config', type=Path, default=Path('config.json'))
    parser.add_argument('--root', type=Path, default=Path('data/paper-v1'))
    parser.add_argument('--port', type=int, default=8090)
    parser.add_argument('--once', action='store_true')
    args = parser.parse_args()
    if args.configure:
        if args.config.exists():
            raise SystemExit('Configuration already exists. Edit it locally and use a new data directory for changes.')
        config = dict(DEFAULTS, source_wallet=wallet(input('Public source wallet address (no private key): ').strip()))
        args.config.write_text(json.dumps(config, indent=2), encoding='utf-8')
        print('Saved local configuration. No account credentials are required for paper mode.')
        return
    config = json.loads(args.config.read_text(encoding='utf-8'))
    wallet(config['source_wallet'])
    if config != dict(DEFAULTS, source_wallet=config['source_wallet']):
        raise SystemExit('This release uses the documented fixed experiment settings.')
    run(config, args.root, args.port, args.once)


if __name__ == '__main__':
    main()
