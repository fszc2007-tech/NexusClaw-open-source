/**
 * Umi dev 会调用 os.networkInterfaces() 取本机 IP；部分环境会抛错导致 max dev 退出。
 * 1) preset-umi：modifyAppData 里对 address.ip() try/catch。
 * 2) @umijs/utils getDevBanner：打印 Network 地址时再包一层 try/catch。
 */
const fs = require('fs');
const path = require('path');

const root = path.join(__dirname, '..');
const pnpmDir = path.join(root, 'node_modules', '.pnpm');

const PRESET_NEEDLE = `    memo.host = process.env.HOST || import_constants.DEFAULT_HOST;
    memo.ip = import_utils.address.ip();
    return memo;`;

const PRESET_REPLACEMENT = `    memo.host = process.env.HOST || import_constants.DEFAULT_HOST;
    try {
      memo.ip = import_utils.address.ip();
    } catch {
      memo.ip = process.env.UMI_DEV_IP || "127.0.0.1";
    }
    return memo;`;

function patchPresetDevJs(devJsPath) {
  let s = fs.readFileSync(devJsPath, 'utf8');
  if (!s.includes('memo.ip = import_utils.address.ip();')) {
    return false;
  }
  if (!s.includes(PRESET_NEEDLE)) {
    return false;
  }
  fs.writeFileSync(devJsPath, s.replace(PRESET_NEEDLE, PRESET_REPLACEMENT), 'utf8');
  return true;
}

/** getDevBanner.js 内：`const ip = import_address.default.ip();` */
const BANNER_OLD = '  const ip = import_address.default.ip();';
const BANNER_NEW = `  let ip;
  try {
    ip = import_address.default.ip();
  } catch {
    ip = process.env.UMI_DEV_IP || null;
  }`;

function patchGetDevBanner(bannerPath) {
  let s = fs.readFileSync(bannerPath, 'utf8');
  if (s.includes('try {\n    ip = import_address.default.ip();')) {
    return false;
  }
  if (!s.includes(BANNER_OLD)) {
    return false;
  }
  fs.writeFileSync(bannerPath, s.replace(BANNER_OLD, BANNER_NEW), 'utf8');
  return true;
}

function main() {
  if (!fs.existsSync(pnpmDir)) {
    return;
  }
  let count = 0;
  for (const name of fs.readdirSync(pnpmDir)) {
    if (name.startsWith('@umijs+preset-umi@')) {
      const devJs = path.join(
        pnpmDir,
        name,
        'node_modules',
        '@umijs',
        'preset-umi',
        'dist',
        'commands',
        'dev',
        'dev.js',
      );
      if (fs.existsSync(devJs) && patchPresetDevJs(devJs)) {
        count += 1;
        console.log(`[ensure-umi-dev-ip] patched ${path.relative(root, devJs)}`);
      }
    }
    if (name.startsWith('@umijs+utils@')) {
      const banner = path.join(pnpmDir, name, 'node_modules', '@umijs', 'utils', 'dist', 'getDevBanner.js');
      if (fs.existsSync(banner) && patchGetDevBanner(banner)) {
        count += 1;
        console.log(`[ensure-umi-dev-ip] patched ${path.relative(root, banner)}`);
      }
    }
  }
  if (count) {
    console.log(`[ensure-umi-dev-ip] ${count} file(s) updated`);
  }
}

main();
