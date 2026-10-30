"""Sanitized batch-report vocabulary and Los Angeles timestamps."""
from datetime import datetime
from zoneinfo import ZoneInfo

from gaswise.domain.pricing.collection_bases import BASE_CATALOG
from gaswise.domain.pricing.collection_errors import SAFE_CODES

LOCAL_ZONE = ZoneInfo('America/Los_Angeles')
DEFERRALS = {'source_budget_deferred', 'configuration_changed', 'service_shutdown', 'coverage_missing', 'pricing_egress_unavailable'} | {
    f'{source}_{suffix}' for source in ('gasbuddy', 'maps', 'waze') for suffix in (
        'mandatory_budget_reserved', 'background_daily_budget_exhausted', 'background_budget_exhausted',
        'request_budget_exhausted', 'background_wait_exhausted')}
LABELS = {
    'google_maps_web_unavailable': 'Google Maps 連線或服務暫時不可用',
    'waze_upstream_unavailable': 'Waze 連線不可用／逾時',
    'gasbuddy_http_api_rejected': 'GasBuddy API 回傳非成功狀態',
    'gasbuddy_http_bootstrap_rejected': 'GasBuddy 首頁回傳非成功狀態',
    'gasbuddy_http_unavailable': 'GasBuddy 連線不可用／逾時',
    'gasbuddy_http_schema_changed': 'GasBuddy 回應格式異常',
    'gasbuddy_http_query_rejected': 'GasBuddy GraphQL 回報錯誤',
    'gasbuddy_http_csrf_missing': 'GasBuddy 首頁缺少 CSRF',
    'gasbuddy_rate_limited': 'GasBuddy 來源限流',
    'gasbuddy_access_rejected_cooldown': 'GasBuddy 來源拒絕／驗證挑戰',
    'pricing_egress_unavailable': '出口代理暫時不可用',
    'unclassified': '未分類錯誤（已省略原始訊息）',
    'lease_expired': '程序未完成，任務租約已到期',
    'interrupted': '採集程序中斷',
    'service_shutdown': '服務重啟（部署），稍後自動重試',
}


def completion(error, diagnostic=None):
    if error is None:
        return 'success', None
    if error in DEFERRALS:
        return 'deferred', error
    if error in ('interrupted', 'lease_expired'):
        return 'interrupted', error
    code = diagnostic if diagnostic in SAFE_CODES or diagnostic in ('ValueError', 'TypeError', 'KeyError', 'TimeoutError') else 'unclassified'
    return 'failure', code


def safe_metrics(info):
    info = info or {}
    result = {}
    for name, low, high in (('http_status', 100, 599), ('egress_lane', 0, 2), ('http_requests', 0, 1000)):
        value = info.get(name)
        result[name] = value if type(value) is int and low <= value <= high else None
    result['http_requests'] = result['http_requests'] or 0
    result['phase'] = info.get('phase') if info.get('phase') in ('bootstrap', 'graphql', 'source_http', 'login') else None
    for name in ('canonical_count', 'new_canonical_count', 'located_count', 'priced_count',
                 'inventory_overlap_count'):
        value = info.get(name)
        result[name] = value if type(value) is int and 0 <= value <= 1000 else 0
    return result


def local_time(value):
    if value is None:
        return '時間未記錄'
    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace('Z', '+00:00'))
    return value.astimezone(LOCAL_ZONE).strftime('%Y-%m-%d %H:%M:%S %Z')


def failure_message(run):
    reason = run['reason'] or 'unclassified'
    heading = '🧪 GasWise 通知驗證（非實際來源事故）' if run['source'] == 'canary' else (
        '⚠️ GasWise 採集中斷' if run['outcome'] == 'interrupted' else '❌ GasWise 採集失敗')
    names = {row['id']: row['name'] for row in BASE_CATALOG['bases']}
    city = names.get(run['base'], run['base'])
    lines = [f"{heading} #run-{run['id']}",
             f"{run['source']} · {city} · {run['fuel']}",
             f"開始：{local_time(run['started_at'])}", f"結束：{local_time(run['finished_at'])}"]
    if run['started_at']:
        lines.append(f"耗時：{(run['finished_at'] - run['started_at']).total_seconds():.1f} 秒")
    lines.extend([f"原因：{LABELS.get(reason, reason)}", f"錯誤碼：{reason}"])
    if run.get('http_status') is not None:
        lines.append(f"HTTP：{run['http_status']}")
    elif reason in ('google_maps_web_unavailable', 'waze_upstream_unavailable'):
        lines.append('HTTP：未取得來源回應，不能據此判定封鎖')
    if run.get('phase'):
        lines.append(f"階段：{run['phase']}")
    if run.get('egress_lane') is not None:
        lines.append(f"出口：{run['egress_lane'] + 1}")
    lines.extend([f"HTTP 嘗試：{run['http_requests']}", f"最早可重試：{local_time(run.get('retry_at'))}"])
    return '\n'.join(lines)


def summary_message(report):
    totals = {key: sum(row['attempts'] for row in report['counts'] if row['outcome'] == key)
              for key in ('success', 'failure', 'deferred', 'interrupted')}
    lines = ['📊 GasWise 採集批次摘要', f"{local_time(report['start'])} ～ {local_time(report['end'])}",
             f"成功 {totals['success']}｜失敗 {totals['failure']}｜延後 {totals['deferred']}｜中斷 {totals['interrupted']}"]
    for source in sorted({row['source'] for row in report['counts']}):
        rows = [row for row in report['counts'] if row['source'] == source]
        success = sum(row['attempts'] for row in rows if row['outcome'] == 'success')
        failed = sum(row['attempts'] for row in rows if row['outcome'] == 'failure')
        quotes = sum(row['quotes'] for row in rows if row['outcome'] == 'success')
        lines.append(f'{source}：成功 {success}／失敗 {failed}，回傳油價 {quotes} 筆')
    if report.get('lanes'):
        lines.append('各出口統計（成功率以成功＋來源失敗任務計算）：')
        pairs = sorted({(row['source'], row['egress_lane']) for row in report['lanes']})
        for source, lane in pairs:
            rows = [row for row in report['lanes'] if row['source'] == source and row['egress_lane'] == lane]
            success = sum(row['attempts'] for row in rows if row['outcome'] == 'success')
            failed = sum(row['attempts'] for row in rows if row['outcome'] == 'failure')
            requests = sum(row['http_requests'] for row in rows)
            quotes = sum(row['quotes'] for row in rows if row['outcome'] == 'success')
            rate = f'{success / (success + failed):.0%}' if success + failed else '—'
            lines.append(f'出口{lane + 1} {source}：成功率 {rate}，HTTP {requests} 次，回傳 {quotes} 筆')
    if report['reasons']:
        lines.append('失敗／中斷原因統計：')
        for row in report['reasons'][:8]:
            lines.append(f"• {row['source']} · {row['reason']} (HTTP {row.get('http_status') or '—'})：{row['attempts']} 次，最近 {local_time(row['last_at'])}")
    lines.append('回傳筆數跨任務未去重；內部額度延後不算來源失敗。')
    return '\n'.join(lines)[:3800]
