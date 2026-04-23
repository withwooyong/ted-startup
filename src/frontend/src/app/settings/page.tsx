'use client';

import { useEffect, useState } from 'react';
import {
  getNotificationPreferences,
  updateNotificationPreferences,
} from '@/lib/api/client';
import { RealAccountSection } from '@/components/features/RealAccountSection';
import {
  NOTIFICATION_CHANNEL_LABELS,
  type NotificationPreference,
  type NotificationPreferenceUpdate,
} from '@/types/notification';
import { SIGNAL_TYPE_LABELS, type SignalType } from '@/types/signal';

const SIGNAL_TYPES: SignalType[] = ['RAPID_DECLINE', 'TREND_REVERSAL', 'SHORT_SQUEEZE'];
const CHANNEL_KEYS = [
  'daily_summary_enabled',
  'urgent_alert_enabled',
  'batch_failure_enabled',
  'weekly_report_enabled',
] as const;
type ChannelKey = (typeof CHANNEL_KEYS)[number];

function friendlyError(err: unknown): string {
  if (err && typeof err === 'object' && 'status' in err) {
    const status = (err as { status?: number }).status;
    if (status === 401) return '인증이 필요합니다. API Key를 확인해주세요.';
    if (status === 400) return '입력값이 올바르지 않습니다.';
    if (status && status >= 500) return '서버 오류가 발생했습니다. 잠시 후 다시 시도해주세요.';
  }
  return '저장에 실패했습니다.';
}

export default function SettingsPage() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [toast, setToast] = useState<string | null>(null);

  const [form, setForm] = useState<NotificationPreferenceUpdate>({
    daily_summary_enabled: true,
    urgent_alert_enabled: true,
    batch_failure_enabled: true,
    weekly_report_enabled: true,
    min_score: 60,
    signal_types: [...SIGNAL_TYPES],
  });
  const [updatedAt, setUpdatedAt] = useState<string | null>(null);

  useEffect(() => {
    getNotificationPreferences()
      .then((pref: NotificationPreference) => {
        setForm({
          daily_summary_enabled: pref.daily_summary_enabled,
          urgent_alert_enabled: pref.urgent_alert_enabled,
          batch_failure_enabled: pref.batch_failure_enabled,
          weekly_report_enabled: pref.weekly_report_enabled,
          min_score: pref.min_score,
          signal_types: pref.signal_types,
        });
        setUpdatedAt(pref.updated_at);
        setLoading(false);
      })
      .catch((err: unknown) => {
        setError(friendlyError(err));
        setLoading(false);
      });
  }, []);

  useEffect(() => {
    if (!toast) return;
    const timer = setTimeout(() => setToast(null), 2500);
    return () => clearTimeout(timer);
  }, [toast]);

  const toggleChannel = (key: ChannelKey) =>
    setForm(prev => ({ ...prev, [key]: !prev[key] }));

  const toggleSignalType = (type: SignalType) =>
    setForm(prev => ({
      ...prev,
      signal_types: prev.signal_types.includes(type)
        ? prev.signal_types.filter(t => t !== type)
        : [...prev.signal_types, type],
    }));

  const handleSave = async () => {
    if (form.signal_types.length === 0) {
      setToast('최소 한 개의 시그널 타입을 선택해주세요');
      return;
    }
    setSaving(true);
    try {
      const result = await updateNotificationPreferences(form);
      setUpdatedAt(result.updated_at);
      setToast('저장되었습니다');
    } catch (err) {
      setToast(friendlyError(err));
    } finally {
      setSaving(false);
    }
  };

  return (
    <main className="max-w-3xl mx-auto px-4 sm:px-5 py-5 sm:py-7">
      <header className="mb-6">
        <h1 className="font-[family-name:var(--font-display)] text-xl sm:text-2xl font-semibold text-[#E8ECF1]">
          알림 설정
        </h1>
        <p className="text-sm text-[#6B7A90] mt-1">
          텔레그램 채널로 받을 알림 종류와 필터 조건을 선택합니다.
        </p>
      </header>

      {loading && (
        <div className="space-y-3" aria-busy="true" aria-live="polite">
          {[1, 2, 3].map(i => (
            <div key={i} className="h-24 bg-[#131720] rounded-[14px] animate-pulse" />
          ))}
        </div>
      )}

      {error && (
        <div className="text-center py-10">
          <p className="text-[#FF4D6A] mb-4">{error}</p>
          <button
            type="button"
            onClick={() => window.location.reload()}
            className="px-4 py-2 rounded-lg bg-[#6395FF] text-white text-sm focus-visible:ring-2 focus-visible:ring-[#6395FF]/50 focus:outline-none"
          >
            다시 시도
          </button>
        </div>
      )}

      {!loading && !error && (
        <>
          {/* 채널 토글 */}
          <section aria-labelledby="channel-heading" className="mb-6">
            <h2 id="channel-heading" className="text-sm font-medium text-[#6B7A90] mb-3 uppercase tracking-wider">
              알림 종류
            </h2>
            <ul className="space-y-2">
              {CHANNEL_KEYS.map(key => {
                const { title, desc } = NOTIFICATION_CHANNEL_LABELS[key];
                const active = form[key];
                return (
                  <li key={key}>
                    <button
                      type="button"
                      role="switch"
                      aria-checked={active}
                      onClick={() => toggleChannel(key)}
                      className="w-full flex items-center justify-between gap-3 px-4 py-3 rounded-[14px] bg-[#131720] border border-white/[0.06] hover:border-[#6395FF]/30 transition-colors text-left focus:outline-none focus-visible:ring-2 focus-visible:ring-[#6395FF]/50"
                    >
                      <span className="min-w-0 flex-1">
                        <span className="block text-sm text-[#E8ECF1] font-medium">{title}</span>
                        <span className="block text-xs text-[#6B7A90] mt-0.5">{desc}</span>
                      </span>
                      <span
                        aria-hidden="true"
                        className={`relative shrink-0 w-10 h-6 rounded-full transition-colors ${
                          active ? 'bg-[#6395FF]' : 'bg-[#3D4A5C]'
                        }`}
                      >
                        <span
                          className={`absolute top-0.5 left-0.5 w-5 h-5 rounded-full bg-white transition-transform ${
                            active ? 'translate-x-4' : 'translate-x-0'
                          }`}
                        />
                      </span>
                    </button>
                  </li>
                );
              })}
            </ul>
          </section>

          {/* 시그널 타입 필터 */}
          <section aria-labelledby="types-heading" className="mb-6">
            <h2 id="types-heading" className="text-sm font-medium text-[#6B7A90] mb-3 uppercase tracking-wider">
              시그널 타입 필터
            </h2>
            <div
              role="group"
              aria-label="알림 대상 시그널 타입"
              className="flex flex-wrap gap-2"
            >
              {SIGNAL_TYPES.map(type => {
                const active = form.signal_types.includes(type);
                return (
                  <button
                    key={type}
                    type="button"
                    aria-pressed={active}
                    onClick={() => toggleSignalType(type)}
                    className={`px-4 py-2 rounded-lg text-sm font-medium border transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-[#6395FF]/50 ${
                      active
                        ? 'bg-[#6395FF]/10 border-[#6395FF]/40 text-[#E8ECF1]'
                        : 'bg-[#131720] border-white/[0.06] text-[#6B7A90] hover:text-[#E8ECF1]'
                    }`}
                  >
                    {SIGNAL_TYPE_LABELS[type]}
                  </button>
                );
              })}
            </div>
            {form.signal_types.length === 0 && (
              <p className="text-xs text-[#FF4D6A] mt-2">최소 한 개의 타입을 선택해주세요</p>
            )}
          </section>

          {/* 최소 스코어 슬라이더 */}
          <section aria-labelledby="score-heading" className="mb-6">
            <div className="flex items-baseline justify-between mb-3">
              <h2 id="score-heading" className="text-sm font-medium text-[#6B7A90] uppercase tracking-wider">
                최소 스코어
              </h2>
              <span className="font-[family-name:var(--font-mono)] text-lg text-[#E8ECF1]">
                {form.min_score}
              </span>
            </div>
            <label className="block">
              <span className="sr-only">최소 스코어 (0-100)</span>
              <input
                type="range"
                min={0}
                max={100}
                step={5}
                value={form.min_score}
                onChange={e =>
                  setForm(prev => ({ ...prev, min_score: Number(e.target.value) }))
                }
                className="w-full accent-[#6395FF] focus-visible:outline-2 focus-visible:outline-[#6395FF]/50"
              />
            </label>
            <p className="text-xs text-[#6B7A90] mt-2">
              이 스코어 미만 시그널은 일일 요약에서 제외됩니다. (긴급 알림 A등급은 항상 발송)
            </p>
          </section>

          {/* 저장 + 메타 */}
          <div className="flex items-center justify-between gap-3 pt-4 border-t border-white/[0.06]">
            <span className="text-xs text-[#7A8699]">
              {updatedAt
                ? `최근 업데이트: ${new Date(updatedAt).toLocaleString('ko-KR')}`
                : '—'}
            </span>
            <button
              type="button"
              onClick={handleSave}
              disabled={saving || form.signal_types.length === 0}
              className="px-5 py-2 rounded-lg bg-[#6395FF] text-white text-sm font-medium shadow-[0_2px_8px_rgba(99,149,255,0.3)] disabled:opacity-40 disabled:cursor-not-allowed focus:outline-none focus-visible:ring-2 focus-visible:ring-[#6395FF]/50"
            >
              {saving ? '저장 중…' : '저장'}
            </button>
          </div>

          {toast && (
            <div
              role="status"
              aria-live="polite"
              className="fixed bottom-6 left-1/2 -translate-x-1/2 px-4 py-2 rounded-lg bg-[#1A1F2E] border border-white/10 text-sm text-[#E8ECF1] shadow-xl"
            >
              {toast}
            </div>
          )}

          <RealAccountSection />
        </>
      )}
    </main>
  );
}
