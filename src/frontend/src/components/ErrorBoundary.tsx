'use client';

import { Component, ReactNode } from 'react';

type Props = {
  children: ReactNode;
  fallback?: ReactNode;
  /** 값이 바뀌면 에러 상태를 자동 리셋 — 상위 상태 변경 후 재시도용 */
  resetKeys?: ReadonlyArray<unknown>;
  onReset?: () => void;
};

type State = {
  hasError: boolean;
  error: Error | null;
};

function keysChanged(prev: ReadonlyArray<unknown> = [], next: ReadonlyArray<unknown> = []) {
  if (prev.length !== next.length) return true;
  return prev.some((v, i) => !Object.is(v, next[i]));
}

export default class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false, error: null };

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: { componentStack?: string | null }) {
    console.error('[ErrorBoundary]', error, info.componentStack);
  }

  componentDidUpdate(prevProps: Props) {
    if (this.state.hasError && keysChanged(prevProps.resetKeys, this.props.resetKeys)) {
      this.setState({ hasError: false, error: null });
    }
  }

  private reset = () => {
    this.setState({ hasError: false, error: null });
    this.props.onReset?.();
  };

  render() {
    if (!this.state.hasError) return this.props.children;
    if (this.props.fallback) return this.props.fallback;

    return (
      <div
        role="alert"
        className="bg-[#131720] border border-[#FF4D6A]/20 rounded-[14px] p-6 text-center"
      >
        <div className="text-2xl mb-2 opacity-60" aria-hidden="true">⚠</div>
        <p className="text-[#E8ECF1] mb-1">차트를 렌더링할 수 없어요</p>
        <p className="text-[#6B7A90] text-sm mb-4">
          새로고침하거나 기간을 변경해 보세요
        </p>
        <button
          type="button"
          onClick={this.reset}
          className="px-4 py-2 rounded-lg bg-[#6395FF] text-white text-sm hover:bg-[#6395FF]/90 transition-colors"
        >
          다시 시도
        </button>
      </div>
    );
  }
}
