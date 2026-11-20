"""Black-box regression tests for the repository or an installed prefix."""
import http.server
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import threading
import time
import unittest

BIN = Path(sys.argv.pop(1)).resolve()
STUB = Path(__file__).with_name('fake-codex').resolve()
DONE = 'unique first reply\nwrote the file'
AUTH = 'Need help: please enter the PIN, then tell me to continue.\n  \n'  # a question is still `done`


def real(p):
    return os.path.realpath(p)


class Handler(http.server.BaseHTTPRequestHandler):
    def receive(self):
        code = int(self.path[1:])
        body = self.rfile.read(int(self.headers.get('Content-Length', 0)))
        self.server.calls.append((self.command, code, json.loads(body) if body else {}))
        self.send_response(code, 'fixture')
        if 300 <= code < 400:
            self.send_header('Location', f'http://localhost:{self.server.server_port}/200')
        self.end_headers()

    do_POST = do_GET = receive

    def log_message(self, *args):
        pass


class Runs(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name).resolve()
        self.work = self.root / 'work'
        self.work.mkdir()
        self.task = self.root / 'task with spaces'
        self.task.write_text('snapshot me')
        self.trace = self.root / 'trace'
        self.trace.touch()
        self.home = self.root / 'config'
        (self.home / 'webhooks').mkdir(parents=True)
        self.server = http.server.HTTPServer(('127.0.0.1', 0), Handler)
        self.server.calls = []
        threading.Thread(target=self.server.serve_forever, kwargs={'poll_interval': 0.02}, daemon=True).start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.endpoint(200)
        self.env = {k: v for k, v in os.environ.items() if not k.startswith(('RELAYBOT_', 'GIT_'))}
        self.env.update(HOME=str(self.root), RELAYBOT_CODEX_BIN=str(STUB), RELAYBOT_CLAUDE_BIN=str(STUB.with_name("fake-claude")),
                        TRACE=str(self.trace),
                        WORK=str(self.work),
                        RELAYBOT_HOME=str(self.home), RELAYBOT_RUN_ROOT=str(self.root / 'runs'),
                        RELAYBOT_DEFAULT_WORKDIR=str(self.root / 'codex-for-grok'))

    def endpoint(self, code):
        cfg = dict(url=f'http://127.0.0.1:{self.server.server_port}/{code}', key='synthetic-test-value', bot='test')
        (self.home / 'webhooks/test.json').write_text(json.dumps(cfg))

    def records(self):
        return [json.loads(x) for x in self.trace.read_text().splitlines()]

    def launch(self, backend='exec', task=None, resume=False, work=None, **cfg):
        cfg.setdefault('reply', DONE)
        env = dict(self.env, FIXTURE=json.dumps(cfg), RELAYBOT_FORCE_EXEC='' if backend == 'app' else '1')
        runner = 'claude-run' if backend == 'claude' else 'codex-run'
        args = [str(BIN / runner), 'test', str(work or self.work), str(task or self.task)]
        if resume:
            args.append('resume')
        return subprocess.Popen(args, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    def finish(self, proc, status, rc=0, delivered=True):
        out, err = proc.communicate(timeout=20)
        self.assertEqual(proc.returncode, rc, out + err)
        m = re.fullmatch(r'run_dir=(.+) exit=(\d+) session=(\S*) status=(\w+)', out.splitlines()[-1])
        self.assertIsNotNone(m, out)
        run, exit_code, sid, actual = m.groups()
        run = Path(run)
        self.assertEqual((int(exit_code), actual), (rc, status))
        self.assertEqual((run / 'exit').read_text().strip(), str(rc))
        self.assertEqual(json.loads((run / 'status.json').read_text())['status'], status)
        if delivered:
            self.assertEqual([c[2]['event'] for c in self.server.calls], [status])
        if self.server.calls:
            self.payload = self.server.calls[-1][2]
            self.message = self.payload['message']
        self.transport_calls = [(m, c) for m, c, _ in self.server.calls]
        self.server.calls.clear()
        return run

    def reject(self, proc):
        out, err = proc.communicate(timeout=10)
        self.assertNotEqual(proc.returncode, 0, out)
        self.assertTrue(err.strip(), 'no diagnostic')
        return err

    def test_statuses(self):
        legacy = 'old session text\nGROKBOT_STATUS: needs_auth enter PIN'
        for backend in ('exec', 'app'):
            for cfg, status, rc, reason in [
                (dict(), 'done', 0, 'unique first reply'),
                (dict(reply=AUTH), 'done', 0, 'enter the PIN'),        # questions are read from the reply
                (dict(reply=legacy), 'done', 0, 'enter PIN'),          # reply text is never parsed
                (dict(pause='needs_auth'), 'needs_auth', 0, 'explicit reason'),
                (dict(pause='blocked'), 'blocked', 0, 'explicit reason'),  # older sessions only
                (dict(early_done=True), 'done', 0, 'unique first reply'),
                (dict(reply=None), 'failed', 1, 'no reply'),
            ]:
                with self.subTest(backend=backend, cfg=cfg):
                    run = self.finish(self.launch(backend, **cfg), status, rc)
                    self.assertIn(reason.lower(), self.message.lower())
                    reply = cfg.get('reply', DONE) or ''
                    self.assertEqual(self.payload['reply'], reply)
                    self.assertEqual(self.payload['reply_file'], str(run / 'last.md') if reply else None)
                    self.assertEqual((self.payload['exit_code'], self.payload['session_id']), (rc, 'session-a'))
                    self.assertFalse(self.payload['reply_truncated'])
                    if cfg.get('early_done'):
                        self.assertTrue(any(r.get('premature_rc') for r in self.records()))
        self.finish(self.launch(pause='needs_auth', rc=7), 'failed', 7)
        run = self.finish(self.launch('app', approval=True), 'needs_auth')
        self.assertIn('approve this', (run / 'status.json').read_text())
        self.assertIn('approve this', self.message)
        self.finish(self.launch(reply='x' * 9000), 'done')
        self.assertEqual((len(self.payload['reply']), self.payload['reply_truncated']), (8000, True))

    def test_claude_pause_and_resume(self):
        self.task.write_bytes("  --flag $HOME\r\n修复\r\n\n".encode())
        for case, reason in [('permission', 'echo test'), ('question', 'Which format? (JSON, Text)')]:
            run = self.finish(self.launch('claude', case=case), 'needs_auth')
            self.assertTrue(run.name.startswith('claude-run-'))
            self.assertEqual(run.stat().st_mode & 0o777, 0o700)
            sid = self.payload['session_id']
            self.assertIn('claude --resume ' + sid, self.message)
            self.assertIn(reason, self.message)
            self.assertEqual((self.payload['exit_code'], self.payload['reply'], self.payload['reply_file']),
                             (0, '', None))
            self.assertEqual((run / 'prompt.md').read_bytes(), self.task.read_bytes())
            self.assertEqual(self.records()[-1], dict(cwd=str(self.work), resume=None,
                                                      input=self.task.read_bytes().decode()))
            follow = run / 'followup.md'
            follow.write_text('  继续')
            self.reject(self.launch(task=follow, resume=True))
            reply = '好' * 8001
            self.assertEqual(self.finish(self.launch('claude', task=follow, resume=True, reply=reply), 'done'), run)
            self.assertEqual(self.records()[-1], dict(cwd=str(self.work), resume=sid, input='  继续'))
            self.assertEqual(self.payload['session_id'], sid)
            self.assertEqual(self.payload['reply'], reply[:8000])
            self.assertTrue(self.payload['reply_truncated'])
            self.assertEqual(Path(self.payload['reply_file']).read_text(), reply)
            mismatch = 'bbbbbbbb-bbbb-4bbb-bbbb-bbbbbbbbbbbb'
            self.finish(self.launch('claude', task=follow, resume=True, result_sid=mismatch), 'failed', 1)
            self.assertEqual((self.payload['session_id'], self.payload['reply_file']), (sid, None))
            self.assertEqual(len((run / 'notified.jsonl').read_text().splitlines()), 3)
            (run / 'session').write_text('latest')
            self.reject(self.launch('claude', task=follow, resume=True))

    def test_claude_results(self):
        for cfg, status, rc in [
            (dict(reply=AUTH), 'done', 0),  # a natural-language question is still a final reply
            (dict(case='denied'), 'needs_auth', 0),
            (dict(error='authentication_failed', is_error=True, rc=1), 'needs_auth', 0),
            (dict(subtype='error_during_execution', is_error=True), 'failed', 1),
            (dict(is_error=True), 'failed', 1),
            (dict(reply=None), 'failed', 1),
            (dict(case='eof'), 'failed', 1),
            (dict(case='eof', rc=97), 'failed', 97),  # no Codex fallback
            (dict(case='broken'), 'failed', 1),
        ]:
            with self.subTest(cfg=cfg):
                self.finish(self.launch('claude', **cfg), status, rc)
                self.assertEqual(self.payload['exit_code'], rc)
                self.assertNotIn('codex resume', self.message)
        self.env['RELAYBOT_MAX_SECONDS'] = '0.4'
        self.finish(self.launch('claude', case='hang'), 'failed', 1)
        self.assertIn('RELAYBOT_MAX_SECONDS', self.message)
        self.env['RELAYBOT_CLAUDE_BIN'] = str(self.root / 'missing')
        self.finish(self.launch('claude'), 'failed', 1)
        self.assertIsNone(self.payload['session_id'])

    def test_claude_discovery_and_delivery(self):
        stub = self.env.pop('RELAYBOT_CLAUDE_BIN')
        local = self.root / '.local/bin/claude'
        local.parent.mkdir(parents=True)
        local.symlink_to(stub)
        # Test discovery with no system Claude on PATH. Pin the stub before launching.
        import shutil
        path = self.root / 'path'
        path.mkdir()
        for name in ('bash', 'dirname'):
            (path / name).symlink_to(shutil.which(name))
        argv = [BIN / 'claude-run', '--print-claude-bin']
        found = subprocess.check_output(argv, env=dict(self.env, PATH=str(path)), text=True).strip()
        self.assertEqual(found, str(local))
        self.env['RELAYBOT_CLAUDE_BIN'] = found
        self.env['RELAYBOT_MODEL'] = 'codex-only-test-model'
        self.endpoint(307)
        run = self.finish(self.launch('claude', work='-'), 'done', delivered=False)
        self.assertEqual(self.transport_calls, [('POST', 307)])
        self.assertEqual(self.records()[0]['cwd'], self.env['RELAYBOT_DEFAULT_WORKDIR'])
        queued = json.loads((self.home / 'outbox.jsonl').read_text())
        self.assertEqual(queued['run_id'], run.name)
        self.assertEqual(queued['reply'], DONE)
        self.assertEqual(len(self.records()), 1)
        (self.home / 'config.env').write_text('RELAYBOT_CLAUDE_BIN=' + stub + '\n')
        del self.env['RELAYBOT_CLAUDE_BIN']
        self.assertEqual(subprocess.check_output(argv, env=self.env, text=True).strip(), stub)
        self.env['RELAYBOT_CLAUDE_BIN'] = str(local)
        self.assertEqual(subprocess.check_output(argv, env=self.env, text=True).strip(), str(local))

    def test_setup_checks_both_clis_and_one_shared_webhook(self):
        (self.home / 'config.env').write_text('RELAYBOT_EXTRA_PATH=' + str(STUB.parent) + '\n')
        codex_ok = (0, 'Logged in using ChatGPT')
        codex_out = (1, 'Not logged in')
        claude_ok = (0, dict(loggedIn=True, authMethod='oauth_token', email='private-fixture@example.invalid'))
        claude_out = (1, dict(loggedIn=False))
        for codex, claude, results in [
            (codex_ok, claude_ok, ('Codex signed in', 'Claude Code signed in')),
            (None, claude_ok, ('Codex unavailable', 'Claude Code signed in')),
            (codex_ok, None, ('Codex signed in', 'Claude Code unavailable')),
            (codex_out, claude_ok, ('Codex signed out', 'Claude Code signed in')),
            (codex_ok, claude_out, ('Codex signed in', 'Claude Code signed out')),
            (codex_ok, (0, dict(authMethod='oauth_token')), ('Codex signed in', 'Claude Code signed in')),
            (codex_ok, (0, dict(authMethod='none')), ('Codex signed in', 'Claude Code signed out')),
            (codex_ok, (0, dict(loggedIn=False, authMethod='api_key')), ('Codex signed in', 'Claude Code signed out')),
            ((0, 'unexpected output'), (1, dict(authMethod='api_key')), ('Codex login unverified', 'Claude Code login unverified')),
            (codex_ok, (0, {}), ('Codex signed in', 'Claude Code login unverified')),
            ((1, 'private-fixture error'), (1, {}), ('Codex login unverified', 'Claude Code login unverified')),
        ]:
            with self.subTest(results=results):
                env = dict(self.env, FIXTURE=json.dumps(dict(codex_status=codex, claude_status=claude)))
                missing = str(self.root / 'missing')
                env['RELAYBOT_CODEX_BIN'] = 'fake-codex' if codex else missing
                env['RELAYBOT_CLAUDE_BIN'] = 'fake-claude' if claude else missing
                proc = subprocess.run([BIN / 'relaybot-doctor', '--webhook-test', 'test'], env=env,
                                      capture_output=True, text=True, timeout=20)
                self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
                for status in results:
                    self.assertIn(status, proc.stdout)
                self.assertNotIn('private-fixture', proc.stdout + proc.stderr)
                self.assertNotIn('synthetic-test-value', proc.stdout + proc.stderr)
                self.assertIn('sent 200', proc.stdout)
                self.assertEqual([c[2]['event'] for c in self.server.calls], ['test'])
                self.server.calls.clear()
                expected = []
                if codex:
                    expected.append(['login', 'status'])
                if claude:
                    expected.append(['auth', 'status', '--json'])
                self.assertCountEqual([r['argv'] for r in self.records()], expected)
                self.trace.write_text('')

        self.endpoint(503)
        env = dict(self.env, FIXTURE=json.dumps(dict(codex_status=codex_ok, claude_status=claude_ok)))
        proc = subprocess.run([BIN / 'relaybot-doctor', '--webhook-test', 'test'], env=env,
                              capture_output=True, text=True, timeout=20)
        self.assertNotEqual(proc.returncode, 0, proc.stdout)
        self.assertIn('queued: HTTP 503', proc.stdout)
        self.assertEqual([c[2]['event'] for c in self.server.calls], ['test'])

    def test_prompt_is_task_verbatim(self):
        for backend in ('exec', 'app'):
            self.trace.write_text('')
            run = self.finish(self.launch(backend), 'done')
            self.assertEqual([r['input'] for r in self.records() if 'turn' in r], ['snapshot me'])
            self.assertEqual((run / 'prompt.md').read_text(), 'snapshot me')
            argv = ' '.join(' '.join(r['argv']) for r in self.records() if 'argv' in r)
            self.assertNotIn('hooks', argv)

    def test_exact_resume_and_fresh_output(self):
        for backend, fallback in [('exec', False), ('app', False), ('app', True)]:
            a = self.finish(self.launch(backend, sid='session-a'), 'done')
            self.finish(self.launch(backend, sid='session-b'), 'done')
            follow = a / 'followup.md'
            follow.write_text('second turn')
            self.trace.write_text('')
            self.finish(self.launch(backend, task=follow, resume=True, reply=None, fallback=fallback), 'failed', 1)
            self.assertFalse((a / 'last.md').exists())
            self.assertTrue(any(p.read_text() == DONE for p in a.rglob('*.md')))
            self.assertEqual([r['turn'] for r in self.records() if 'turn' in r], ['session-a'])
            self.assertNotIn(DONE.splitlines()[0], self.message)
            self.finish(self.launch(backend, task=follow, resume=True, reply=AUTH), 'done')
            self.assertEqual((a / 'last.md').read_text(), AUTH)
            (a / 'session').write_text('unknown\n')
            self.finish(self.launch(backend, task=follow, resume=True), 'failed', 7 if backend == 'exec' else 1)
            for content in ('  \n', None):
                if content is None:
                    (a / 'session').unlink()
                else:
                    (a / 'session').write_text(content)
                self.trace.write_text('')
                self.reject(self.launch(backend, task=follow, resume=True))
                self.assertEqual(self.records(), [])

    def test_inputs_and_permissions(self):
        run = self.finish(self.launch(), 'done')
        self.assertEqual(run.stat().st_mode & 0o777, 0o700)
        self.assertEqual((self.work / 'source.txt').stat().st_mode & 0o777, 0o644)
        self.assertIn('snapshot me', (run / 'prompt.md').read_text())
        run.chmod(0o755)
        follow = run / 'followup.md'
        for resume, task in [(False, self.root / 'missing'), (False, self.work), (True, follow)]:
            self.trace.write_text('')
            before = [(run / n).read_bytes() for n in ('session', 'pause', 'last.md')]
            self.reject(self.launch(task=task, resume=resume))
            self.assertEqual(self.records(), [])
            self.assertEqual(before, [(run / n).read_bytes() for n in ('session', 'pause', 'last.md')])
        follow.write_text('continue')
        follow.chmod(0)
        if not os.access(follow, os.R_OK):
            self.reject(self.launch(task=follow, resume=True))
            self.assertEqual(self.records(), [])
        follow.chmod(0o600)
        self.finish(self.launch(task=follow, resume=True), 'done')
        self.assertEqual(run.stat().st_mode & 0o777, 0o700)
        self.root.chmod(0o755)
        self.reject(self.launch(task=self.task, resume=True))
        self.assertEqual(self.root.stat().st_mode & 0o777, 0o755)
        del self.env['RELAYBOT_RUN_ROOT']
        run = self.finish(self.launch(), 'done')
        import shutil
        self.addCleanup(shutil.rmtree, run)
        self.assertEqual(run.stat().st_mode & 0o777, 0o700)

    def test_legacy_resume(self):
        run = self.root / 'codex-run-20260101-120000'
        run.mkdir(mode=0o755)
        for name, text in {'task.md': 'original', 'prompt.md': 'old prompt', 'pause': 'p123',
                           'session': 'legacy-id', 'last.md': DONE, 'followup.md': 'approved'}.items():
            (run / name).write_text(text)
        (run / 'log.txt').write_text('session id: earlier-log-header\n')
        self.finish(self.launch(task=run / 'followup.md', resume=True, reply=AUTH), 'done')
        self.assertEqual(run.stat().st_mode & 0o777, 0o700)
        self.assertEqual((run / 'session').read_text(), 'legacy-id')
        self.assertEqual((run / 'last.md').read_text(), AUTH)

    def test_snapshot_read_failure(self):
        run = self.finish(self.launch(), 'done')
        follow = run / 'followup.md'
        follow.write_text('input exists at preflight')
        # Inject a read error after the first bytes of a regular file.
        cat = self.root / 'cat'
        cat.write_text('#!/bin/sh\nif [ "$1" = "$FAIL_INPUT" ]; then echo partial; exit 1; fi\nexec /bin/cat "$@"\n')
        cat.chmod(0o755)
        self.env.update(PATH=str(self.root) + ':' + self.env['PATH'], FAIL_INPUT=str(follow))
        self.trace.write_text('')
        before = [(run / n).read_bytes() for n in ('pause', 'last.md', 'session', 'exit')]
        self.reject(self.launch(task=follow, resume=True))
        self.assertEqual(self.records(), [])
        self.assertEqual(before, [(run / n).read_bytes() for n in ('pause', 'last.md', 'session', 'exit')])

    def test_only_current_final_answer(self):
        for cfg in (dict(reply=DONE, phase='commentary'), dict(reply=DONE, reply_turn='previous')):
            run = self.finish(self.launch('app', **cfg), 'failed', 1)
            self.assertFalse((run / 'last.md').exists())

    def test_concurrent_resume(self):
        run = self.finish(self.launch(), 'done')
        follow = run / 'followup.md'
        follow.write_text('continue')
        gate = self.root / 'gate'
        proc = self.launch('app', task=follow, resume=True, hold=str(gate), reply=AUTH)
        try:
            for _ in range(250):
                if gate.exists() or proc.poll() is not None:
                    break
                time.sleep(0.02)
            self.assertTrue(gate.exists())
            self.assertFalse((run / 'last.md').exists())
            pause = (run / 'pause').read_bytes()
            self.trace.write_text('')
            self.reject(self.launch(task=follow, resume=True))
            self.assertEqual((run / 'pause').read_bytes(), pause)
            self.assertEqual(self.records(), [])
        finally:
            if gate.exists():
                gate.unlink()
            self.finish(proc, 'done')

    def test_projects(self):
        subprocess.run(['git', 'init', '-q', str(self.work)], check=True)
        alias = self.root / 'alias'
        alias.symlink_to(self.work)
        fallback = self.root / 'codex-for-grok'
        subprocess.run(['git', 'init', '-q', str(fallback)], check=True)
        sub = self.work / 'sub'
        sub.mkdir()
        existing = {'id': 'matched', 'name': 'work', 'roots': [{'path': str(self.work)}]}
        default = {'id': 'default', 'roots': [{'path': str(fallback)}]}
        for wd, projects, error, creates, expected in [
            (alias, [default], False, True, 'created'), (self.work, [default], True, True, 'default'),
            (self.work, [default, existing], False, False, 'matched'), (sub, [default], False, False, 'default'),
            (self.root, [default], False, False, 'default'), (fallback, [], False, False, None),
        ]:
            self.trace.write_text('')
            self.finish(self.launch('app', work=wd, projects=projects, create_error=error), 'done')
            requests = {r['method']: r['params'] for r in self.records() if 'method' in r}
            self.assertEqual('project/create' in requests, creates)
            if creates:
                self.assertEqual(requests['project/create'], dict(name='work', roots=[dict(path=str(self.work))],
                                                                 idempotencyKey='relaybot:' + str(self.work)))
            self.assertEqual(requests['thread/start'].get('projectId'), expected)

        del self.env['RELAYBOT_DEFAULT_WORKDIR']
        grok_project = {'id': 'grok', 'roots': [{'path': str(self.root / 'Documents/codex-for-grok')}]}
        self.trace.write_text('')
        self.finish(self.launch('app', work=sub, projects=[grok_project]), 'done')
        self.assertEqual([r['params'].get('projectId') for r in self.records() if r.get('method') == 'thread/start'],
                         ['grok'])

    def test_worktree_projects(self):
        main = self.root / 'repo'
        git = ['git', '-c', 'user.name=t', '-c', 'user.email=t@example.invalid', '-C', str(main)]
        subprocess.run(['git', 'init', '-q', str(main)], check=True)
        subprocess.run(git + ['commit', '-q', '--allow-empty', '-m', 'init'], check=True)
        linked = self.root / '_wt-feature'
        codex_wt = self.root / '.codex/worktrees/a1b2/repo'
        subprocess.run(git + ['worktree', 'add', '-q', str(linked)], check=True)
        subprocess.run(git + ['worktree', 'add', '-q', '--detach', str(codex_wt)], check=True)
        main_project = {'id': 'main', 'name': 'repo', 'roots': [{'path': str(main)}]}
        multi = {'id': 'multi', 'name': 'repo', 'roots': [{'path': str(main)}, {'path': str(self.work)}]}
        exact = {'id': 'exact', 'name': '_wt-feature', 'roots': [{'path': str(linked)}]}
        default = {'id': 'default', 'roots': [{'path': str(self.root / 'codex-for-grok')}]}
        for wd, projects, expected in [
            (linked, [default, multi, main_project], 'main'),       # linked worktree -> main repo's project
            (codex_wt, [default, main_project], 'main'),             # Codex-managed worktree, same rule
            (linked, [default, main_project, exact], 'exact'),       # exact root still wins
            (linked, [default], 'created'),                          # none: create for the main root
        ]:
            self.trace.write_text('')
            self.finish(self.launch('app', work=wd, projects=projects), 'done')
            requests = {r['method']: r['params'] for r in self.records() if 'method' in r}
            self.assertEqual(requests['thread/start'].get('projectId'), expected)
            self.assertEqual(real(requests['thread/start']['cwd']), str(wd))
            if expected == 'created':
                self.assertEqual(requests['project/create'], dict(name='repo', roots=[dict(path=str(main))],
                                                                 idempotencyKey='relaybot:' + str(main)))
            else:
                self.assertNotIn('project/create', requests)

    def test_transport(self):
        for code in (200, 301, 302, 303, 307, 308):
            self.endpoint(code)
            run = self.finish(self.launch(), 'done', delivered=False)
            # No fallback execution when transport failed.
            self.assertEqual(len([r for r in self.records() if 'turn' in r]), 1)
            self.trace.write_text('')
            self.assertEqual(self.transport_calls, [('POST', code)])
            queue = self.home / 'outbox.jsonl'
            if code == 200:
                self.assertFalse(queue.exists())
            else:
                records = [json.loads(x) for x in queue.read_text().splitlines()]
                self.assertEqual(len(records), 1)
                self.assertEqual(records[0]['event'], 'done')
                self.assertNotIn('synthetic-test-value', queue.read_text() + (run / 'log.txt').read_text())
                queue.unlink()


if __name__ == '__main__':
    os.umask(0o022)
    unittest.main(verbosity=2)
