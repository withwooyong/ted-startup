'use client';

import { useRef, useState } from 'react';
import { importExcelTransactions } from '@/lib/api/portfolio';
import type { ExcelImportResult } from '@/types/portfolio';

const MAX_CLIENT_BYTES = 10 * 1024 * 1024; // 10MB — 서버와 동일

interface Props {
  accountId: number;
  onSuccess?: (result: ExcelImportResult) => void;
}

export function ExcelImportPanel({ accountId, onSuccess }: Props): React.JSX.Element {
  const [file, setFile] = useState<File | null>(null);
  const [pending, setPending] = useState(false);
  const [result, setResult] = useState<ExcelImportResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  function clearAll() {
    setFile(null);
    setResult(null);
    setError(null);
    if (inputRef.current) inputRef.current.value = '';
  }

  async function handleUpload() {
    if (!file) return;
    setPending(true);
    setError(null);
    setResult(null);
    try {
      const res = await importExcelTransactions(accountId, file);
      setResult(res);
      onSuccess?.(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setPending(false);
    }
  }

  return (
    <section
      aria-labelledby="excel-import-title"
      className="mb-5 bg-[#131720]/85 border border-white/[0.06] rounded-[14px] p-4 sm:p-5"
    >
      <div className="flex items-baseline justify-between mb-3">
        <h2
          id="excel-import-title"
          className="text-sm font-medium text-[#6B7A90] uppercase tracking-wider"
        >
          거래내역 엑셀 가져오기
        </h2>
        <span className="text-xs text-[#7A8699]">KIS 체결내역 .xlsx</span>
      </div>

      <div className="flex flex-col sm:flex-row gap-2 sm:items-center">
        <label className="flex-1">
          <span className="sr-only">엑셀 파일 선택</span>
          <input
            ref={inputRef}
            type="file"
            accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            disabled={pending}
            onChange={e => {
              const chosen = e.target.files?.[0] ?? null;
              if (chosen && chosen.size > MAX_CLIENT_BYTES) {
                setError(`파일 크기가 10MB 를 초과합니다: ${Math.round(chosen.size / 1024 / 1024)}MB`);
                setFile(null);
                return;
              }
              setFile(chosen);
              setError(null);
              setResult(null);
            }}
            className="block w-full text-sm text-[#E8ECF1] file:mr-3 file:py-1.5 file:px-3 file:rounded-md file:border-0 file:text-sm file:font-medium file:bg-[#6395FF]/10 file:text-[#B0CAFF] file:cursor-pointer hover:file:bg-[#6395FF]/20 focus:outline-none"
          />
        </label>
        <button
          type="button"
          onClick={handleUpload}
          disabled={!file || pending}
          className="px-4 py-2 rounded-lg bg-[#6395FF] text-white text-sm font-medium shadow-[0_2px_8px_rgba(99,149,255,0.3)] disabled:opacity-40 disabled:cursor-not-allowed focus:outline-none focus-visible:ring-2 focus-visible:ring-[#6395FF]/50"
        >
          {pending ? '업로드 중…' : '가져오기'}
        </button>
        {(file || result || error) && !pending && (
          <button
            type="button"
            onClick={clearAll}
            className="px-3 py-2 rounded-lg text-sm text-[#6B7A90] hover:text-[#E8ECF1] border border-white/[0.06]"
          >
            초기화
          </button>
        )}
      </div>

      {error && (
        <p role="alert" className="mt-3 text-sm text-[#FFB1BE]">
          가져오기 실패: {error}
        </p>
      )}

      {result && (
        <div role="status" className="mt-3 text-sm text-[#B0CAFF] space-y-1">
          <p>
            총 {result.total_rows}행 · 신규 {result.imported} · 중복 스킵 {result.skipped_duplicates} ·
            신규 종목 {result.stock_created_count}
          </p>
          {result.errors.length > 0 && (
            <details className="text-xs text-[#FFB1BE]">
              <summary className="cursor-pointer">
                실패한 행 {result.errors.length}건 펼치기
              </summary>
              <ul className="mt-1 pl-4 list-disc">
                {result.errors.slice(0, 20).map((e, i) => (
                  <li key={`${e.row}-${i}`}>
                    row {e.row}: {e.reason}
                  </li>
                ))}
                {result.errors.length > 20 && (
                  <li>… (총 {result.errors.length}건 중 20건만 표시)</li>
                )}
              </ul>
            </details>
          )}
        </div>
      )}
    </section>
  );
}
