const form = document.querySelector('#analyze-form');
const button = document.querySelector('#submit-btn');
const runState = document.querySelector('#run-state');
const empty = document.querySelector('#empty-state');
const results = document.querySelector('#results');
const liveLog = document.querySelector('#live-log');
const clearLog = document.querySelector('#clear-log');
const nodes = [...document.querySelectorAll('#pipeline [data-node]')];
let currentRunId = null;
let currentData = null;

function esc(value = '') { const div = document.createElement('div'); div.textContent = String(value); return div.innerHTML; }
function date(value) { if (!value) return '날짜 미제공'; const parsed = new Date(value); return Number.isNaN(parsed.getTime()) ? String(value) : parsed.toLocaleString('ko-KR'); }

function appendLog(message, kind = '') {
  if (!liveLog) return;
  const line = document.createElement('div');
  line.className = `log-line ${kind}`;
  line.textContent = `[${new Date().toLocaleTimeString('ko-KR')}] ${message}`;
  liveLog.appendChild(line);
  liveLog.scrollTop = liveLog.scrollHeight;
}

clearLog?.addEventListener('click', () => { liveLog.innerHTML = ''; appendLog('로그를 비웠습니다.', 'muted'); });

const nodeFromTrace = trace => {
  if (trace.startsWith('trend_discovery')) return 'trend';
  if (trace.startsWith('trend_normalizer')) return 'normalize';
  if (trace.startsWith('trend_analysis')) return 'analysis';
  if (trace.startsWith('research')) return 'research';
  if (trace.startsWith('fact_check')) return 'fact';
  if (trace.startsWith('threads_writer')) return 'writer';
  if (trace.startsWith('content_review')) return 'review';
  if (trace.startsWith('human_approval')) return 'approval';
  if (trace.startsWith('threads_publish')) return 'publish';
  return 'trend';
};

function describeTrace(trace) {
  const parts = String(trace).split(':');
  if (trace.startsWith('trend_discovery:')) return `트렌드 수집 완료 · ${parts.slice(1).join(' · ')}`;
  if (trace.startsWith('trend_normalizer:')) return `후보 정규화/병합 완료 · ${parts.slice(1).join(' · ')}`;
  if (trace.startsWith('trend_analysis:selected:')) return `최고 후보 선정 · ${parts[2]} · ${parts[3]}점`;
  if (trace.startsWith('trend_analysis:no_candidate')) return '분석 가능한 트렌드 후보가 없습니다.';
  if (trace.startsWith('research:')) return `근거 조사 완료 · ${parts.slice(1).join(' · ')}`;
  if (trace.startsWith('fact_check:')) return `팩트 체크 완료 · ${parts.slice(1).join(' · ')}`;
  if (trace.startsWith('threads_writer:')) return `Threads 초안 작성 완료 · ${parts.slice(1).join(' · ')}`;
  if (trace.startsWith('content_review:')) return `콘텐츠 검토 완료 · ${parts.slice(1).join(' · ')}`;
  if (trace.startsWith('human_approval:')) return '사용자 승인 대기 중입니다.';
  if (trace.startsWith('finalize:no_qualified_trend')) return '기준 점수 미달로 분석을 종료했습니다.';
  return trace.replaceAll('_', ' · ');
}

function setProgress(trace) {
  const activeIndex = nodes.findIndex(node => node.dataset.node === nodeFromTrace(trace));
  nodes.forEach((node, index) => {
    node.classList.toggle('active', index === activeIndex);
    node.classList.toggle('done', index < activeIndex);
  });
  const description = describeTrace(trace);
  runState.textContent = description;
  appendLog(description, trace.includes('failed') || trace.includes('error') ? 'error' : '');
}

function render(data) {
  const safe = {
    topic: '', trend_score: 0, trend_reason: '', trend_signals: [], verified_facts: [], sources: [],
    confidence: 0, hashtags: [], warnings: [], api_errors: [], available_sources: [], successful_sources: [],
    thread_post: null, review: null, status: 'failed', publish_status: 'not_ready', region: 'GLOBAL', language: 'ko',
    data_mode: 'live', ...data,
  };
  currentData = safe;
  currentRunId = safe.run_id || currentRunId;
  const facts = (safe.verified_facts || []).map(item => `<li>${esc(item)}</li>`).join('');
  const sources = (safe.sources || []).map(item => `<a class="source" href="${esc(item.url)}" target="_blank" rel="noopener"><b>${esc(item.title)}</b><small>${esc(item.type)} · ${esc(item.publisher || 'source')} · ${esc(date(item.published_at))}</small></a>`).join('');
  const signals = (safe.trend_signals || []).map(item => `<a class="signal" href="${esc(item.url)}" target="_blank" rel="noopener"><b>${esc(item.source)}</b><span>${Math.round(item.engagement || 0)} / 100</span><p>${esc(item.title)}</p><small>${esc(date(item.published_at))} · ${esc(JSON.stringify(item.raw_score || {}))}</small></a>`).join('');
  const warnings = (safe.warnings || []).map(item => `<span class="tag warning">${esc(item)}</span>`).join('');
  const apiErrors = (safe.api_errors || []).map(item => `<span class="tag warning">${esc(item.source)} · ${esc(item.reason)}</span>`).join('');
  const review = safe.review || {};
  const post = safe.thread_post || {};
  const canDecide = safe.status === 'awaiting_approval';
  const qualificationNote = safe.status === 'no_qualified_trend'
    ? `<article class="card full error-card"><h3>분석 가능한 트렌드 후보가 없습니다</h3><p>이번 수집에서 유효한 후보를 확보하지 못했습니다.</p><p>외부 API 상태를 확인하거나 잠시 후 다시 분석해 보세요.</p></article>`
    : '';
  const permalink = safe.threads_permalink ? `<a class="published-link" href="${esc(safe.threads_permalink)}" target="_blank" rel="noopener">게시물 열기 ↗</a>` : '';

  results.innerHTML = `
    <div class="result-hero"><div><small>${esc(safe.region)} → ${esc(safe.language)} · ${esc(String(safe.data_mode).toUpperCase())} · ${esc(safe.status)}</small><h3>${esc(safe.topic || '선정된 주제 없음')}</h3><p>${esc(safe.trend_reason)}</p></div><div class="score">${Math.round(safe.trend_score || 0)}</div></div>
    <div class="meta-row"><span class="tag">Confidence ${Math.round((safe.confidence || 0) * 100)}%</span><span class="tag">Publish · ${esc(safe.publish_status)}</span>${warnings}${apiErrors}</div>
    <div class="result-grid">${qualificationNote}
      <article class="card full"><h4>Trend signals</h4><p class="section-note">관심도 판단용 신호이며 Fact Source가 아닙니다.</p><div class="signal-grid">${signals || '<p>선정 Signal 없음</p>'}</div></article>
      <article class="card"><h4>Verified facts</h4><ul>${facts || '<li>검증 사실 없음</li>'}</ul></article>
      <article class="card"><h4>Fact sources</h4><p class="section-note">글의 사실 근거로 사용한 출처입니다.</p>${sources || '<p>수집 출처 없음</p>'}</article>
      <article class="card full thread-preview"><h4>Generated Threads post <span>${(post.full_text || '').length} / 500</span></h4><pre>${esc(post.full_text || '생성된 게시글이 없습니다.')}</pre>${permalink}</article>
      <article class="card review-card"><h4>Quality review</h4><div class="review-score">${Math.round((review.quality_score || 0) * 100)}</div><ul><li>${review.factually_grounded ? '✓' : '×'} Verified facts only</li><li>${review.source_supported ? '✓' : '×'} Source supported</li><li>${review.needs_revision ? '수정 필요' : '게시 품질 통과'}</li></ul></article>
      <article class="card"><h4>Review notes</h4><ul>${(review.issues || []).map(item => `<li>${esc(item)}</li>`).join('') || '<li>지적 사항 없음</li>'}</ul><p class="hashtags">${(safe.hashtags || []).map(esc).join(' ')}</p></article>
    </div>
    ${canDecide ? `<section class="approval-box"><div><small>HUMAN INTERRUPT</small><h4>게시 전 최종 승인이 필요합니다.</h4><p>Approve를 누르기 전에는 Threads API를 호출하지 않습니다.</p></div><div class="approval-actions"><button type="button" data-action="approve">Approve & Publish</button><button type="button" class="secondary" data-action="edit">Edit</button><button type="button" class="danger" data-action="reject">Reject</button></div><div class="edit-box" hidden><textarea maxlength="500">${esc(post.full_text || '')}</textarea><small><span class="edit-count">${(post.full_text || '').length}</span> / 500</small><button type="button" data-action="save-edit">Save Edit & Re-review</button></div></section>` : ''}`;
  empty.hidden = true;
  results.hidden = false;
  runState.textContent = `${safe.status} · ${safe.publish_status}`;
  appendLog(`결과 표시: ${safe.status} / ${safe.publish_status}`, safe.status === 'publish_failed' ? 'error' : 'success');
  bindApprovalActions();
}

function showError(error) {
  const message = error?.message || String(error);
  runState.textContent = '실행 실패';
  appendLog(message, 'error');
  empty.hidden = true;
  results.hidden = false;
  results.innerHTML = `<article class="card error-card"><h3>결과를 표시하는 중 오류가 발생했습니다</h3><p>${esc(message)}</p><p>LIVE AGENT LOG에서 마지막 실행 단계를 확인하세요.</p></article>`;
}

async function sendDecision(action, editedText) {
  if (!currentRunId) throw new Error('run_id가 없습니다. 먼저 Analyze Trend를 실행하세요.');
  runState.textContent = action === 'approve' ? 'Publishing…' : 'LangGraph 재개 중…';
  appendLog(`사용자 결정: ${action}`);
  results.querySelectorAll('button').forEach(btn => { btn.disabled = true; });
  const payload = { action };
  if (editedText !== undefined) payload.edited_text = editedText;
  const response = await fetch(`/api/runs/${encodeURIComponent(currentRunId)}/decision`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
  const data = await response.json();
  if (!response.ok) throw new Error(data.detail || `HTTP ${response.status}`);
  render(data);
}

function bindApprovalActions() {
  const approval = results.querySelector('.approval-box');
  if (!approval) return;
  approval.querySelector('[data-action="approve"]').addEventListener('click', () => sendDecision('approve').catch(showError));
  approval.querySelector('[data-action="reject"]').addEventListener('click', () => sendDecision('reject').catch(showError));
  const editBox = approval.querySelector('.edit-box');
  const textarea = editBox.querySelector('textarea');
  approval.querySelector('[data-action="edit"]').addEventListener('click', () => { editBox.hidden = !editBox.hidden; if (!editBox.hidden) textarea.focus(); });
  textarea.addEventListener('input', () => { editBox.querySelector('.edit-count').textContent = textarea.value.length; });
  approval.querySelector('[data-action="save-edit"]').addEventListener('click', () => sendDecision('edit', textarea.value).catch(showError));
}

function processStreamMessage(message) {
  if (message.event === 'run') { currentRunId = message.run_id; appendLog(`run 시작: ${currentRunId}`); }
  if (message.event === 'activity') appendLog(`${message.message} (${message.elapsed || 0}초)`);
  if (message.event === 'heartbeat') {
    runState.textContent = `처리 중 · ${message.elapsed || 0}초`;
    appendLog(`${message.message} 경과 ${message.elapsed || 0}초`, 'muted');
  }
  if (message.event === 'progress') setProgress(message.step || 'progress');
  if (message.event === 'complete') { appendLog('Graph 실행 완료', 'success'); render(message.result); }
  if (message.event === 'error') throw new Error(message.message || '서버 스트리밍 오류');
}

async function recoverRun(runId) {
  if (!runId) return false;
  appendLog('스트림 연결이 끝나 결과 상태를 복구하는 중입니다.', 'muted');
  for (let attempt = 0; attempt < 15; attempt += 1) {
    await new Promise(resolve => setTimeout(resolve, 2000));
    const response = await fetch(`/api/runs/${encodeURIComponent(runId)}`, { cache: 'no-store' });
    if (!response.ok) continue;
    const data = await response.json();
    if (data.status && data.status !== 'running') {
      appendLog('실행 상태 조회로 결과를 복구했습니다.', 'success');
      render(data);
      return true;
    }
  }
  return false;
}

form.addEventListener('submit', async event => {
  event.preventDefault();
  button.disabled = true; results.hidden = true; empty.hidden = false; nodes.forEach(node => { node.className = ''; });
  liveLog.innerHTML = ''; appendLog('분석 요청 전송'); runState.textContent = 'LangGraph 실행 중…';
  const fd = new FormData(form);
  const payload = { region: fd.get('region'), language: fd.get('language'), category: fd.get('category'), period: fd.get('period'), min_trend_score: Number(fd.get('min_trend_score')), content_style: fd.get('content_style'), auto_publish: fd.get('auto_publish') === 'on', demo_mode: fd.get('demo_mode') === 'on' };
  try {
    const response = await fetch('/api/analyze/stream', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
    if (!response.ok || !response.body) throw new Error(`HTTP ${response.status}`);
    const reader = response.body.getReader(); const decoder = new TextDecoder(); let buffer = ''; let completed = false;
    while (true) {
      const { value, done } = await reader.read();
      buffer += decoder.decode(value || new Uint8Array(), { stream: !done });
      const lines = buffer.split('\n'); buffer = lines.pop() || '';
      for (const line of lines) { if (!line.trim()) continue; const message = JSON.parse(line); processStreamMessage(message); if (message.event === 'complete') completed = true; }
      if (done) break;
    }
    if (buffer.trim()) { const message = JSON.parse(buffer); processStreamMessage(message); if (message.event === 'complete') completed = true; }
    if (!completed && !(await recoverRun(currentRunId))) {
      throw new Error('서버가 complete 이벤트를 보내지 않았습니다. LIVE AGENT LOG를 확인하세요.');
    }
  } catch (error) { showError(error); }
  finally { button.disabled = false; }
});

async function loadLatestScheduledResult() {
  try {
    const response = await fetch('/api/latest', { cache: 'no-store' });
    if (response.status === 404) return;
    if (!response.ok) throw new Error(`최근 분석 조회 실패: HTTP ${response.status}`);
    const data = await response.json();
    appendLog('저장된 최근 정기 분석 결과를 불러왔습니다.', 'success');
    render(data);
  } catch (error) {
    appendLog(error.message || String(error), 'error');
  }
}

loadLatestScheduledResult();
