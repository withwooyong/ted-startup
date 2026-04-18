// 모든 포트폴리오 API 는 관리자 키 보호 — Next.js Route Handler 를 경유해
// 서버 측에서 ADMIN_API_KEY 를 부착한다. 클라이언트 번들엔 키 없음.
import type {
  Account,
  AccountCreateRequest,
  Holding,
  PerformanceReport,
  SignalAlignmentReport,
  Snapshot,
  SyncResult,
  Transaction,
  TransactionCreateRequest,
} from '@/types/portfolio';

const ADMIN_BASE = '/api/admin';

async function call<T>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  const res = await fetch(`${ADMIN_BASE}${path}`, {
    ...init,
    cache: 'no-store',
    headers: {
      'Content-Type': 'application/json',
      ...(init?.headers ?? {}),
    },
  });
  if (!res.ok) {
    const body = (await res.json().catch(() => ({}))) as { message?: string; detail?: string };
    const msg = body.message || body.detail || `API Error: ${res.status}`;
    const err = new Error(msg) as Error & { status?: number };
    err.status = res.status;
    throw err;
  }
  return (await res.json()) as T;
}

export async function listAccounts(): Promise<Account[]> {
  return call<Account[]>('/portfolio/accounts');
}

export async function createAccount(body: AccountCreateRequest): Promise<Account> {
  return call<Account>('/portfolio/accounts', {
    method: 'POST',
    body: JSON.stringify(body),
  });
}

export async function listHoldings(accountId: number): Promise<Holding[]> {
  return call<Holding[]>(`/portfolio/accounts/${accountId}/holdings`);
}

export async function listTransactions(accountId: number, limit = 50): Promise<Transaction[]> {
  return call<Transaction[]>(`/portfolio/accounts/${accountId}/transactions?limit=${limit}`);
}

export async function createTransaction(
  accountId: number,
  body: TransactionCreateRequest,
): Promise<Transaction> {
  return call<Transaction>(`/portfolio/accounts/${accountId}/transactions`, {
    method: 'POST',
    body: JSON.stringify(body),
  });
}

export async function createSnapshot(accountId: number, asof?: string): Promise<Snapshot> {
  const q = asof ? `?asof=${encodeURIComponent(asof)}` : '';
  return call<Snapshot>(`/portfolio/accounts/${accountId}/snapshot${q}`, {
    method: 'POST',
  });
}

export async function getPerformance(
  accountId: number,
  start?: string,
  end?: string,
): Promise<PerformanceReport> {
  const qp = new URLSearchParams();
  if (start) qp.set('start', start);
  if (end) qp.set('end', end);
  const q = qp.toString();
  return call<PerformanceReport>(
    `/portfolio/accounts/${accountId}/performance${q ? `?${q}` : ''}`,
  );
}

export async function syncFromKis(accountId: number): Promise<SyncResult> {
  return call<SyncResult>(`/portfolio/accounts/${accountId}/sync`, {
    method: 'POST',
  });
}

export async function getSignalAlignment(
  accountId: number,
  opts?: { since?: string; until?: string; min_score?: number },
): Promise<SignalAlignmentReport> {
  const qp = new URLSearchParams();
  if (opts?.since) qp.set('since', opts.since);
  if (opts?.until) qp.set('until', opts.until);
  if (opts?.min_score !== undefined) qp.set('min_score', String(opts.min_score));
  const q = qp.toString();
  return call<SignalAlignmentReport>(
    `/portfolio/accounts/${accountId}/signal-alignment${q ? `?${q}` : ''}`,
  );
}
