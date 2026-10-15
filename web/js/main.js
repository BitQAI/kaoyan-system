import { get, post, flushPending } from './api.js';
import { loadContent, state } from './state.js';
import { renderToday } from './today.js';
import { renderListen } from './player.js';
import { renderLook } from './look.js';
import { renderTest } from './quiz.js';
import { renderMemo } from './memo.js';
import { initAI } from './ai.js';
import { renderMe } from './me.js';
import './exam.js';

const TABS = ['today', 'listen', 'look', 'test', 'me'];

function show(id) { document.getElementById(id).classList.remove('hidden'); }
function hide(id) { document.getElementById(id).classList.add('hidden'); }

export function kyGo(tab) {
  document.querySelectorAll('.screen').forEach((s) => s.classList.remove('on'));
  document.getElementById('s-' + tab).classList.add('on');
  document.querySelectorAll('.tabbar button').forEach((b) => b.classList.remove('on'));
  const btn = document.querySelector(`.tabbar button[data-tab="${tab}"]`);
  if (btn) btn.classList.add('on');
  window.scrollTo({ top: 0, behavior: 'smooth' });
  document.dispatchEvent(new CustomEvent('ky-tab', { detail: tab }));
  if (tab === 'today') renderToday();
  if (tab === 'listen') renderListen();
  if (tab === 'look') renderLook();
  if (tab === 'test') renderTest();
  if (tab === 'me') renderMe();
  if (tab === 'memo') renderMemo();
}
window.kyGo = kyGo;

async function enterApp() {
  hide('login-screen');
  show('app');
  try {
    await loadContent();
  } catch (e) {
    document.getElementById('boot-error').style.display = 'block';
    document.getElementById('boot-error-msg').textContent = '内容加载失败：' + e.message;
    return;
  }
  audioCacheGC();
  await renderToday();
}

const AUDIO_VER_LS = 'ky_audio_ver';

/** 音频离线缓存版本治理：content 版本变化 → 清理旧缓存并提示重下。 */
async function audioCacheGC() {
  const ver = (state.content && state.content.version) || 'v1';
  const prev = localStorage.getItem(AUDIO_VER_LS);
  if (prev && prev !== ver) {
    for (const k of await caches.keys()) {
      if (k.startsWith('ky-audio-')) await caches.delete(k);
    }
    localStorage.removeItem('ky_audio_chaps');
  }
  localStorage.setItem(AUDIO_VER_LS, ver);
}

async function boot() {
  window.addEventListener('ky-unauth', () => {
    hide('app');
    show('login-screen');
    document.getElementById('login-err').textContent = '登录已过期，请重新输入密码';
  });
  document.getElementById('login-btn').addEventListener('click', async () => {
    const pw = document.getElementById('login-pw').value;
    const err = document.getElementById('login-err');
    err.textContent = '';
    try {
      await post('/api/login', { password: pw });
      await enterApp();
    } catch (e) {
      err.textContent = e.message === 'http_401' ? '密码不对' : '登录失败：' + e.message;
    }
  });
  try {
    await get('/api/me');
    await enterApp();
    flushPending();                 // 上线后补发离线期间的评分
  } catch (e) {
    hide('app');
    show('login-screen');
  }
  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('/sw.js').catch(() => {});
  }
  initAI();
}

boot();
