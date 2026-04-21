// 모든 포트폴리오 API 는 관리자 키 보호 — Next.js Route Handler 를 경유해
// 서버 측에서 ADMIN_API_KEY 를 부착한다. 클라이언트 번들엔 키 없음.
import { ADMIN_BASE, adminCall as call } from '@/lib/api/admin';
import type {
  Account,
  AccountCreateRequest,
  BrokerageCredentialRequest,
  BrokerageCredentialResponse,
  ExcelImportResult,
  Holding,
  PerformanceReport,
  SignalAlignmentReport,
  Snapshot,
  SyncResult,
  Transaction,
  TransactionCreateRequest,
} from '@/types/portfolio';

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

export async function importExcelTransactions(
  accountId: number,
  file: File,
): Promise<ExcelImportResult> {
  // multipart 업로드는 JSON 공통 헬퍼(adminCall) 를 쓸 수 없다 — Content-Type 을
  // 브라우저가 boundary 포함해 자동 생성하도록 두고, 릴레이(/api/admin/…) 가
  // 바이너리를 그대로 백엔드로 forward 한다.
  const formData = new FormData();
  formData.append('file', file);
  const res = await fetch(
    `${ADMIN_BASE}/portfolio/accounts/${accountId}/import/excel`,
    {
      method: 'POST',
      body: formData,
      cache: 'no-store',
    },
  );
  if (!res.ok) {
    const body = (await res.json().catch(() => ({}))) as {
      message?: string;
      detail?: string;
    };
    const msg = body.message || body.detail || `API Error: ${res.status}`;
    const err = new Error(msg) as Error & { status?: number };
    err.status = res.status;
    throw err;
  }
  return (await res.json()) as ExcelImportResult;
}

// ---------- Brokerage Credentials (P15 / KIS sync PR 4) ----------

export async function getCredential(
  accountId: number,
): Promise<BrokerageCredentialResponse> {
  return call<BrokerageCredentialResponse>(
    `/portfolio/accounts/${accountId}/credentials`,
  );
}

export async function createCredential(
  accountId: number,
  body: BrokerageCredentialRequest,
): Promise<BrokerageCredentialResponse> {
  return call<BrokerageCredentialResponse>(
    `/portfolio/accounts/${accountId}/credentials`,
    { method: 'POST', body: JSON.stringify(body) },
  );
}

export async function replaceCredential(
  accountId: number,
  body: BrokerageCredentialRequest,
): Promise<BrokerageCredentialResponse> {
  return call<BrokerageCredentialResponse>(
    `/portfolio/accounts/${accountId}/credentials`,
    { method: 'PUT', body: JSON.stringify(body) },
  );
}

export async function deleteCredential(accountId: number): Promise<void> {
  // adminCall 은 JSON 바디를 기대하지만 204 에서는 본문이 없어 파싱 실패 가능. 직접 fetch 경유.
  const res = await fetch(`${ADMIN_BASE}/portfolio/accounts/${accountId}/credentials`, {
    method: 'DELETE',
    cache: 'no-store',
  });
  if (!res.ok) {
    const body = (await res.json().catch(() => ({}))) as { detail?: string };
    const msg = body.detail ?? `API Error: ${res.status}`;
    const err = new Error(msg) as Error & { status?: number };
    err.status = res.status;
    throw err;
  }
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
