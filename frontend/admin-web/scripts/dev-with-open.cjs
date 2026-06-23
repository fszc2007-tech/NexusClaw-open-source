/**
 * 启动 Umi dev 并在本机服务可用时，用系统默认浏览器打开 /login。
 * 避免在编辑器内嵌预览（chrome-error://）里继续导航导致的跨域报错。
 *
 * 设置 OPEN_LOGIN=0 可关闭自动打开浏览器。
 */
const { spawn } = require('child_process');
const http = require('http');
const path = require('path');

const PORT = String(process.env.PORT || '8001').trim();
const LOGIN_URL = `http://127.0.0.1:${PORT}/login`;
const ROOT_URL = `http://127.0.0.1:${PORT}/`;

const skipOpen = process.env.OPEN_LOGIN === '0';

function openInSystemBrowser(url) {
  if (process.platform === 'darwin') {
    spawn('open', [url], { detached: true, stdio: 'ignore' }).unref();
    return;
  }
  if (process.platform === 'win32') {
    spawn('cmd', ['/c', 'start', '', url], { detached: true, stdio: 'ignore', shell: true }).unref();
    return;
  }
  spawn('xdg-open', [url], { detached: true, stdio: 'ignore' }).unref();
}

function probeOnce() {
  return new Promise((resolve) => {
    const req = http.get(ROOT_URL, (res) => {
      res.resume();
      resolve(true);
    });
    req.on('error', () => resolve(false));
    req.setTimeout(1500, () => {
      req.destroy();
      resolve(false);
    });
  });
}

async function waitForServer() {
  const maxAttempts = 90;
  for (let i = 0; i < maxAttempts; i += 1) {
    if (await probeOnce()) {
      return true;
    }
    await new Promise((r) => setTimeout(r, 600));
  }
  return false;
}

function main() {
  const rootDir = path.join(__dirname, '..');
  const env = {
    ...process.env,
    PORT,
    /** 与 .umirc devServer.host 一致，保证绑定在可被 127.0.0.1 访问的接口上 */
    HOST: process.env.HOST || '0.0.0.0',
  };

  const cmd = process.platform === 'win32' ? 'pnpm.cmd exec max dev' : 'pnpm exec max dev';
  const child = spawn(cmd, {
    cwd: rootDir,
    env,
    stdio: 'inherit',
    shell: true,
  });

  let opened = false;
  const tryOpen = async () => {
    if (skipOpen || opened) {
      return;
    }
    const ok = await waitForServer();
    if (ok && !opened) {
      opened = true;
      console.log(`[dev-with-open] opening system browser: ${LOGIN_URL}`);
      openInSystemBrowser(LOGIN_URL);
    } else if (!ok && !skipOpen) {
      console.warn(
        `[dev-with-open] dev server did not respond on ${ROOT_URL} — check terminal for compile errors (e.g. EMFILE).`,
      );
    }
  };

  void tryOpen();

  child.on('exit', (code, signal) => {
    if (signal) {
      process.exit(1);
    }
    process.exit(code ?? 0);
  });

  child.on('error', (err) => {
    console.error('[dev-with-open] failed to spawn max dev:', err);
    process.exit(1);
  });
}

main();
