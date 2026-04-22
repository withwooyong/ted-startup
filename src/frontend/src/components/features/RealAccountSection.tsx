'use client';

import { useCallback, useEffect, useState } from 'react';
import {
  createAccount,
  createCredential,
  deleteCredential,
  getCredential,
  listAccounts,
  replaceCredential,
  testKisConnection,
} from '@/lib/api/portfolio';
import type {
  Account,
  BrokerageCredentialRequest,
  BrokerageCredentialResponse,
} from '@/types/portfolio';

/**
 * KIS sync PR 4 — 실계정 추가 + 자격증명 등록.
 *
 * 2단계 온보딩 (docs/kis-real-account-sync-plan.md § 3.4):
 *   1) 계좌 별칭 + broker='kis' + connection='kis_rest_real' + env='real' 생성
 *   2) 자격증명(app_key/app_secret/계좌번호) 등록 — 서버에서 즉시 Fernet 암호화
 * 이 UI 자체는 외부 KIS API 호출을 일으키지 않는다 (PR 5 에서 "연결 테스트" 추가).
 *
 * 응답은 항상 마스킹 뷰(`••••XXXX`)만 보여주며 `app_secret` 은 조회 불가.
 */

type RealAccountRow = {
  account: Account;
  credential: BrokerageCredentialResponse | null;
};

const ACCOUNT_NO_PATTERN = /^\d{8}-\d{2}$/;
const APP_KEY_MIN = 16;
const APP_SECRET_MIN = 16;

function mapError(err: unknown, fallback: string): string {
  if (err && typeof err === 'object' && 'status' in err) {
    const status = (err as { status?: number }).status;
    const message = err instanceof Error ? err.message : '';
    if (status === 401) return '인증이 필요합니다. API Key를 확인해주세요.';
    if (status === 409) return message || '이미 자격증명이 등록된 계좌입니다.';
    if (status === 403) return message || '조합이 올바르지 않습니다 (kis_rest_real + real 필수).';
    if (status === 400) return message || '입력값이 올바르지 않습니다.';
    if (status === 404) return message || '대상을 찾을 수 없습니다.';
    if (status && status >= 500) return '서버 오류가 발생했습니다.';
    if (message) return message;
  }
  return fallback;
}

export function RealAccountSection(): React.JSX.Element {
  const [rows, setRows] = useState<RealAccountRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);

  const [showForm, setShowForm] = useState(false);
  const [alias, setAlias] = useState('');
  const [appKey, setAppKey] = useState('');
  const [appSecret, setAppSecret] = useState('');
  const [accountNo, setAccountNo] = useState('');
  const [pending, setPending] = useState(false);
  // 수정/삭제 진행 중인 account_id — 버튼 중복 클릭 방어용. null 이면 idle.
  const [actionPending, setActionPending] = useState<number | null>(null);

  const reload = useCallback(async () => {
    setLoading(true);
    try {
      const all = await listAccounts();
      const real = all.filter(a => a.connection_type === 'kis_rest_real');
      // N+1 하지만 실계정은 상한 한자리수 — 단순성 우선. 실패 시 null 로 폴백해
      // 목록 자체가 깨지지 않도록.
      const withCred = await Promise.all(
        real.map(async a => {
          try {
            const cred = await getCredential(a.id);
            return { account: a, credential: cred } satisfies RealAccountRow;
          } catch (err) {
            if (err && typeof err === 'object' && 'status' in err) {
              const status = (err as { status?: number }).status;
              if (status === 404) return { account: a, credential: null };
            }
            return { account: a, credential: null };
          }
        }),
      );
      setRows(withCred);
      setError(null);
    } catch (err) {
      setError(mapError(err, '계좌 목록을 불러오지 못했습니다.'));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void reload();
  }, [reload]);

  useEffect(() => {
    if (!toast) return;
    const timer = setTimeout(() => setToast(null), 2500);
    return () => clearTimeout(timer);
  }, [toast]);

  function resetForm() {
    setAlias('');
    setAppKey('');
    setAppSecret('');
    setAccountNo('');
  }

  const validate = (): string | null => {
    if (alias.trim().length === 0 || alias.length > 50) return '계좌 별칭은 1~50자로 입력해주세요.';
    if (appKey.length < APP_KEY_MIN) return `app_key 는 최소 ${APP_KEY_MIN}자 이상이어야 합니다.`;
    if (appSecret.length < APP_SECRET_MIN) return `app_secret 는 최소 ${APP_SECRET_MIN}자 이상이어야 합니다.`;
    if (!ACCOUNT_NO_PATTERN.test(accountNo)) return '계좌번호 형식이 올바르지 않습니다 (예: 12345678-01).';
    return null;
  };

  async function handleCreate() {
    const v = validate();
    if (v) {
      setToast(v);
      return;
    }
    setPending(true);
    // 폼 close + secret clear 는 API 성공 직후 즉시 수행한다. 이후의 `reload()` 는
    // 단순 목록 갱신이므로 실패하더라도 폼 상태·secret 에 영향 주지 않아야 한다.
    // (이전 구현은 reload 예외 시 폼이 닫히지 않은 채 pending 만 해제되는 불일치가 있었음.)
    try {
      const account = await createAccount({
        account_alias: alias.trim(),
        broker_code: 'kis',
        connection_type: 'kis_rest_real',
        environment: 'real',
      });
      const body: BrokerageCredentialRequest = {
        app_key: appKey,
        app_secret: appSecret,
        account_no: accountNo,
      };
      let credErrMessage: string | null = null;
      try {
        await createCredential(account.id, body);
      } catch (credErr) {
        // 계좌는 생성됐는데 credential 저장에 실패한 엣지 케이스 — 계좌만 남고
        // credential 은 없는 상태. 사용자가 목록의 "수정" 으로 재등록 가능.
        credErrMessage = `계좌는 생성됐으나 자격증명 등록 실패: ${mapError(credErr, '알 수 없는 오류')}. 목록에서 수정을 사용해주세요.`;
      }
      // API 호출 종료 — 폼 닫기 & secret state clear (이후 reload 예외와 무관).
      setShowForm(false);
      resetForm();
      setToast(credErrMessage ?? '실계정이 등록되었습니다.');
      try {
        await reload();
      } catch (reloadErr) {
        setToast(mapError(reloadErr, '목록 갱신 실패 — 새로고침해주세요.'));
      }
    } catch (err) {
      setToast(mapError(err, '등록에 실패했습니다.'));
    } finally {
      setPending(false);
    }
  }

  async function handleReplace(accountId: number) {
    if (actionPending !== null) return; // 다른 수정/삭제 진행 중
    const newKey = window.prompt('새 app_key 입력');
    if (newKey === null) return;
    const newSecret = window.prompt('새 app_secret 입력');
    if (newSecret === null) return;
    const newAccountNo = window.prompt('새 계좌번호 입력 (12345678-01)');
    if (newAccountNo === null) return;
    if (
      newKey.length < APP_KEY_MIN ||
      newSecret.length < APP_SECRET_MIN ||
      !ACCOUNT_NO_PATTERN.test(newAccountNo)
    ) {
      setToast('입력 형식이 올바르지 않습니다.');
      return;
    }
    setActionPending(accountId);
    try {
      const body: BrokerageCredentialRequest = {
        app_key: newKey,
        app_secret: newSecret,
        account_no: newAccountNo,
      };
      // PUT 먼저 시도 → credential 미등록(404) 이면 POST 로 폴백.
      // 폴백 POST 가 409 를 반환하는 경우(다른 탭에서 선행 등록) PUT 으로 재시도.
      try {
        await replaceCredential(accountId, body);
      } catch (putErr) {
        const status =
          putErr && typeof putErr === 'object' && 'status' in putErr
            ? (putErr as { status?: number }).status
            : undefined;
        if (status === 404) {
          try {
            await createCredential(accountId, body);
          } catch (postErr) {
            const postStatus =
              postErr && typeof postErr === 'object' && 'status' in postErr
                ? (postErr as { status?: number }).status
                : undefined;
            if (postStatus === 409) {
              // race: 선행 등록이 PUT 404 ~ POST 사이에 일어남 → 최종 PUT 한번 더.
              await replaceCredential(accountId, body);
            } else {
              throw postErr;
            }
          }
        } else {
          throw putErr;
        }
      }
      setToast('자격증명을 교체했습니다.');
      await reload();
    } catch (err) {
      setToast(mapError(err, '교체에 실패했습니다.'));
    } finally {
      setActionPending(null);
    }
  }

  async function handleTestConnection(accountId: number) {
    if (actionPending !== null) return;
    setActionPending(accountId);
    try {
      // BE 는 성공 시 `{ ok: true }` 만 반환. 실패는 HTTP 예외로 전파.
      await testKisConnection(accountId);
      setToast('연결 성공 — KIS 토큰 발급 확인됨');
    } catch (err) {
      // 502 는 KIS 업스트림 오류 — 자격증명 거부와 일시 장애를 단일 코드로 구분 못 함.
      // 중립적 표현으로 양쪽 원인 모두 커버하며 구체적 행동 지침은 강요하지 않음.
      const status =
        err && typeof err === 'object' && 'status' in err
          ? (err as { status?: number }).status
          : undefined;
      if (status === 502) {
        setToast('연결 실패 — KIS 업스트림 오류. 잠시 후 재시도하거나 자격증명을 확인해주세요.');
      } else {
        setToast(mapError(err, '연결 테스트에 실패했습니다.'));
      }
    } finally {
      setActionPending(null);
    }
  }

  async function handleDelete(accountId: number, accountAlias: string) {
    if (actionPending !== null) return;
    if (!window.confirm(`"${accountAlias}" 의 자격증명을 삭제하시겠습니까? 실 sync 는 더 이상 동작하지 않습니다.`)) {
      return;
    }
    setActionPending(accountId);
    try {
      await deleteCredential(accountId);
      setToast('자격증명을 삭제했습니다.');
      await reload();
    } catch (err) {
      setToast(mapError(err, '삭제에 실패했습니다.'));
    } finally {
      setActionPending(null);
    }
  }

  return (
    <section aria-labelledby="real-account-heading" className="mb-6 pt-6 border-t border-white/[0.06]">
      <div className="flex items-baseline justify-between mb-3">
        <h2
          id="real-account-heading"
          className="text-sm font-medium text-[#6B7A90] uppercase tracking-wider"
        >
          실계좌 연동 (KIS)
        </h2>
        <button
          type="button"
          onClick={() => {
            // 함수형 업데이터 안에서 "현재 열림" 여부를 판정해 stale closure 를 피함.
            // React 18+ batching 에서 `if (showForm)` 이 외부 closure 의 예전 값을 읽는 이슈 방지.
            setShowForm(prev => {
              if (prev) resetForm();
              return !prev;
            });
          }}
          className="text-xs text-[#6395FF] hover:underline focus:outline-none focus-visible:ring-2 focus-visible:ring-[#6395FF]/50 rounded"
        >
          {showForm ? '취소' : '+ 추가'}
        </button>
      </div>
      <p className="text-xs text-[#6B7A90] mb-3">
        한국투자증권 OpenAPI 자격증명을 등록합니다. 등록 시 즉시 암호화되어 저장되며 `app_secret` 은 다시 조회할 수 없습니다.
        실제 API 호출은 다음 단계(&ldquo;연결 테스트&rdquo;)에서 시작됩니다.
      </p>

      {loading && (
        <div
          className="h-16 bg-[#131720] rounded-[14px] animate-pulse"
          aria-busy="true"
          aria-live="polite"
        />
      )}

      {!loading && error && (
        <div className="text-xs text-[#FF4D6A] mb-3">{error}</div>
      )}

      {!loading && !error && rows.length === 0 && !showForm && (
        <div className="text-xs text-[#6B7A90] bg-[#131720] border border-white/[0.06] rounded-[14px] px-4 py-3">
          등록된 실계좌가 없습니다. 우측 상단 &ldquo;+ 추가&rdquo; 로 시작하세요.
        </div>
      )}

      {!loading && rows.length > 0 && (
        <ul className="space-y-2 mb-3">
          {rows.map(({ account, credential }) => (
            <li
              key={account.id}
              data-testid="real-account-row"
              className="flex flex-col gap-3 px-4 py-3 rounded-[14px] bg-[#131720] border border-white/[0.06] sm:flex-row sm:items-center sm:justify-between"
            >
              <div className="min-w-0 flex-1">
                <div className="text-sm text-[#E8ECF1] font-medium truncate">{account.account_alias}</div>
                {credential ? (
                  <div className="text-xs text-[#6B7A90] mt-1 font-[family-name:var(--font-mono)] break-all">
                    app_key {credential.app_key_masked} · 계좌 {credential.account_no_masked}
                  </div>
                ) : (
                  <div className="text-xs text-[#FF4D6A] mt-1">자격증명 미등록 — 수정으로 입력해주세요</div>
                )}
              </div>
              <div className="flex flex-wrap gap-2 sm:shrink-0 sm:flex-nowrap">
                {credential && (
                  <button
                    type="button"
                    onClick={() => void handleTestConnection(account.id)}
                    disabled={actionPending !== null}
                    aria-disabled={actionPending !== null}
                    className="px-3 py-1.5 rounded-lg text-xs bg-[#1A1F2E] border border-white/10 text-[#65D6A1] hover:border-[#65D6A1]/40 disabled:opacity-40 disabled:cursor-not-allowed focus:outline-none focus-visible:ring-2 focus-visible:ring-[#65D6A1]/50"
                    title="KIS OAuth 토큰 발급만 시도 (잔고 영향 없음)"
                  >
                    {actionPending === account.id ? '연결중…' : '연결 테스트'}
                  </button>
                )}
                <button
                  type="button"
                  onClick={() => void handleReplace(account.id)}
                  disabled={actionPending !== null}
                  aria-disabled={actionPending !== null}
                  className="px-3 py-1.5 rounded-lg text-xs bg-[#1A1F2E] border border-white/10 text-[#E8ECF1] hover:border-[#6395FF]/40 disabled:opacity-40 disabled:cursor-not-allowed focus:outline-none focus-visible:ring-2 focus-visible:ring-[#6395FF]/50"
                >
                  수정
                </button>
                {credential && (
                  <button
                    type="button"
                    onClick={() => void handleDelete(account.id, account.account_alias)}
                    disabled={actionPending !== null}
                    aria-disabled={actionPending !== null}
                    className="px-3 py-1.5 rounded-lg text-xs bg-[#1A1F2E] border border-white/10 text-[#FF4D6A] hover:border-[#FF4D6A]/40 disabled:opacity-40 disabled:cursor-not-allowed focus:outline-none focus-visible:ring-2 focus-visible:ring-[#FF4D6A]/50"
                  >
                    삭제
                  </button>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}

      {showForm && (
        <form
          onSubmit={e => {
            e.preventDefault();
            void handleCreate();
          }}
          className="p-4 rounded-[14px] bg-[#131720] border border-white/[0.06] space-y-3"
        >
          <Field label="계좌 별칭" htmlFor="ra-alias">
            <input
              id="ra-alias"
              type="text"
              value={alias}
              onChange={e => setAlias(e.target.value)}
              maxLength={50}
              placeholder="예: KIS 실계좌"
              className="w-full px-3 py-2 rounded-lg bg-[#0A0D13] border border-white/10 text-sm text-[#E8ECF1] placeholder-[#3D4A5C] focus:outline-none focus-visible:ring-2 focus-visible:ring-[#6395FF]/50"
              autoComplete="off"
              required
            />
          </Field>
          <Field label="App Key" htmlFor="ra-appkey">
            <input
              id="ra-appkey"
              type="password"
              value={appKey}
              onChange={e => setAppKey(e.target.value)}
              placeholder="KIS에서 발급받은 App Key"
              className="w-full px-3 py-2 rounded-lg bg-[#0A0D13] border border-white/10 text-sm text-[#E8ECF1] placeholder-[#3D4A5C] focus:outline-none focus-visible:ring-2 focus-visible:ring-[#6395FF]/50 font-[family-name:var(--font-mono)]"
              autoComplete="off"
              required
            />
          </Field>
          <Field label="App Secret" htmlFor="ra-appsecret">
            <input
              id="ra-appsecret"
              type="password"
              value={appSecret}
              onChange={e => setAppSecret(e.target.value)}
              placeholder="KIS에서 발급받은 App Secret"
              className="w-full px-3 py-2 rounded-lg bg-[#0A0D13] border border-white/10 text-sm text-[#E8ECF1] placeholder-[#3D4A5C] focus:outline-none focus-visible:ring-2 focus-visible:ring-[#6395FF]/50 font-[family-name:var(--font-mono)]"
              autoComplete="off"
              required
            />
          </Field>
          <Field label="계좌번호" htmlFor="ra-accno" hint="형식: 12345678-01">
            <input
              id="ra-accno"
              type="text"
              value={accountNo}
              onChange={e => setAccountNo(e.target.value)}
              placeholder="12345678-01"
              pattern="^\d{8}-\d{2}$"
              className="w-full px-3 py-2 rounded-lg bg-[#0A0D13] border border-white/10 text-sm text-[#E8ECF1] placeholder-[#3D4A5C] focus:outline-none focus-visible:ring-2 focus-visible:ring-[#6395FF]/50 font-[family-name:var(--font-mono)]"
              autoComplete="off"
              required
            />
          </Field>
          <div className="flex items-center justify-end gap-2 pt-1">
            <button
              type="button"
              onClick={() => {
                setShowForm(false);
                resetForm();
              }}
              className="px-4 py-2 rounded-lg text-sm bg-[#1A1F2E] border border-white/10 text-[#E8ECF1] focus:outline-none focus-visible:ring-2 focus-visible:ring-[#6395FF]/50"
            >
              취소
            </button>
            <button
              type="submit"
              disabled={pending}
              className="px-5 py-2 rounded-lg bg-[#6395FF] text-white text-sm font-medium disabled:opacity-40 disabled:cursor-not-allowed focus:outline-none focus-visible:ring-2 focus-visible:ring-[#6395FF]/50"
            >
              {pending ? '등록 중…' : '등록'}
            </button>
          </div>
        </form>
      )}

      {toast && (
        <div
          role="status"
          aria-live="polite"
          className="fixed bottom-6 left-1/2 -translate-x-1/2 px-4 py-2 rounded-lg bg-[#1A1F2E] border border-white/10 text-sm text-[#E8ECF1] shadow-xl z-50 max-w-md text-center"
        >
          {toast}
        </div>
      )}
    </section>
  );
}

function Field({
  label,
  htmlFor,
  hint,
  children,
}: {
  label: string;
  htmlFor: string;
  hint?: string;
  children: React.ReactNode;
}): React.JSX.Element {
  return (
    <label htmlFor={htmlFor} className="block">
      <span className="block text-xs text-[#6B7A90] mb-1">
        {label}
        {hint && <span className="ml-2 text-[#3D4A5C]">{hint}</span>}
      </span>
      {children}
    </label>
  );
}
