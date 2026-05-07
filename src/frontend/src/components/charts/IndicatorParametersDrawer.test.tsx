import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import IndicatorParametersDrawer from './IndicatorParametersDrawer';
import {
  DEFAULT_PARAMS,
  DEFAULT_PREFS,
  type IndicatorPrefs,
} from '@/lib/hooks/useIndicatorPreferences';

function clone<T>(v: T): T {
  return JSON.parse(JSON.stringify(v));
}

function renderDrawer(overrides?: Partial<IndicatorPrefs>) {
  const prefs: IndicatorPrefs = clone(DEFAULT_PREFS);
  Object.assign(prefs, overrides);
  const onClose = vi.fn();
  const onSave = vi.fn();
  const utils = render(
    <IndicatorParametersDrawer
      open
      prefs={prefs}
      onClose={onClose}
      onSave={onSave}
    />,
  );
  return { ...utils, onClose, onSave, prefs };
}

describe('IndicatorParametersDrawer', () => {
  it('open=false 면 아무 것도 렌더하지 않는다', () => {
    const { container } = render(
      <IndicatorParametersDrawer
        open={false}
        prefs={clone(DEFAULT_PREFS)}
        onClose={vi.fn()}
        onSave={vi.fn()}
      />,
    );
    expect(container.firstChild).toBeNull();
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  it('dialog 역할 + aria-modal + 제목 연결을 노출한다', () => {
    renderDrawer();
    const dialog = screen.getByRole('dialog');
    expect(dialog).toHaveAttribute('aria-modal', 'true');
    const titleId = dialog.getAttribute('aria-labelledby');
    expect(titleId).toBeTruthy();
    expect(document.getElementById(titleId as string)).toHaveTextContent(
      '지표 파라미터 설정',
    );
  });

  it('현재 prefs.params 값을 초기값으로 표시한다', () => {
    renderDrawer();
    expect(screen.getByLabelText('MA #1 기간')).toHaveValue(DEFAULT_PARAMS.ma[0]);
    expect(screen.getByLabelText('MA #4 기간')).toHaveValue(DEFAULT_PARAMS.ma[3]);
    // "기간" 라벨은 RSI/BB 두 섹션에 있으므로 getAllByLabelText 로 순서 검증.
    const periodInputs = screen.getAllByLabelText('기간');
    expect(periodInputs).toHaveLength(2);
    expect(periodInputs[0]).toHaveValue(DEFAULT_PARAMS.rsi.period);
    expect(periodInputs[1]).toHaveValue(DEFAULT_PARAMS.bb.period);
    expect(screen.getByLabelText('과매수')).toHaveValue(DEFAULT_PARAMS.rsi.overbought);
    expect(screen.getByLabelText('Fast')).toHaveValue(DEFAULT_PARAMS.macd.fast);
    expect(screen.getByLabelText('Slow')).toHaveValue(DEFAULT_PARAMS.macd.slow);
    expect(screen.getByLabelText('k (표준편차 배수)')).toHaveValue(DEFAULT_PARAMS.bb.k);
  });

  it('유효 입력 후 저장하면 onSave(새 params) + onClose 가 호출된다', async () => {
    const user = userEvent.setup();
    const { onSave, onClose } = renderDrawer();

    const ma1 = screen.getByLabelText('MA #1 기간');
    await user.clear(ma1);
    await user.type(ma1, '7');

    const bbK = screen.getByLabelText('k (표준편차 배수)');
    await user.clear(bbK);
    await user.type(bbK, '2.5');

    await user.click(screen.getByRole('button', { name: '저장' }));

    expect(onSave).toHaveBeenCalledTimes(1);
    const saved = onSave.mock.calls[0][0];
    expect(saved.ma[0]).toBe(7);
    expect(saved.bb.k).toBeCloseTo(2.5, 5);
    // 나머지 값은 DEFAULT 그대로
    expect(saved.ma[1]).toBe(DEFAULT_PARAMS.ma[1]);
    expect(saved.rsi.period).toBe(DEFAULT_PARAMS.rsi.period);
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('MA 값이 2 미만이면 저장 버튼이 disabled 되고 aria-invalid 가 true', async () => {
    const user = userEvent.setup();
    const { onSave } = renderDrawer();

    const ma1 = screen.getByLabelText('MA #1 기간');
    await user.clear(ma1);
    await user.type(ma1, '1');

    expect(ma1).toHaveAttribute('aria-invalid', 'true');
    const save = screen.getByRole('button', { name: '저장' });
    expect(save).toBeDisabled();

    // disabled 저장 시도 — click 은 무시됨
    await user.click(save);
    expect(onSave).not.toHaveBeenCalled();

    // 에러 메시지 노출
    expect(screen.getAllByText('2 이상의 정수').length).toBeGreaterThan(0);
  });

  it('RSI overbought <= oversold 면 교차검증 에러', async () => {
    const user = userEvent.setup();
    renderDrawer();

    const overbought = screen.getByLabelText('과매수');
    const oversold = screen.getByLabelText('과매도');
    await user.clear(overbought);
    await user.type(overbought, '30');
    await user.clear(oversold);
    await user.type(oversold, '40');

    expect(screen.getByText('과매수 > 과매도 필요')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '저장' })).toBeDisabled();
  });

  it('MACD fast >= slow 면 교차검증 에러', async () => {
    const user = userEvent.setup();
    renderDrawer();

    const fast = screen.getByLabelText('Fast');
    await user.clear(fast);
    await user.type(fast, '30');

    expect(screen.getByText('fast < slow 필요')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '저장' })).toBeDisabled();
  });

  it('ESC 누르면 onClose 가 호출된다 (save 없이)', async () => {
    const user = userEvent.setup();
    const { onClose, onSave } = renderDrawer();

    await user.keyboard('{Escape}');
    expect(onClose).toHaveBeenCalledTimes(1);
    expect(onSave).not.toHaveBeenCalled();
  });

  it('취소 버튼은 onClose 만 호출하고 onSave 는 호출하지 않는다', async () => {
    const user = userEvent.setup();
    const { onClose, onSave } = renderDrawer();

    await user.click(screen.getByRole('button', { name: '취소' }));
    expect(onClose).toHaveBeenCalledTimes(1);
    expect(onSave).not.toHaveBeenCalled();
  });

  it('기본값 복원 → 편집값이 DEFAULT_PARAMS 로 되돌아간다', async () => {
    const user = userEvent.setup();
    renderDrawer();

    const ma1 = screen.getByLabelText('MA #1 기간');
    await user.clear(ma1);
    await user.type(ma1, '99');
    expect(ma1).toHaveValue(99);

    await user.click(screen.getByRole('button', { name: '기본값 복원' }));
    expect(ma1).toHaveValue(DEFAULT_PARAMS.ma[0]);
    expect(screen.getByLabelText('k (표준편차 배수)')).toHaveValue(DEFAULT_PARAMS.bb.k);
  });

  it('open 상태에서 Tab focus trap 이 마지막→첫 요소로 순환한다', async () => {
    const user = userEvent.setup();
    renderDrawer();

    // open 후 첫 focusable 은 backdrop 버튼(tabIndex=-1)이 아니라 첫 input (MA #1)
    const ma1 = screen.getByLabelText('MA #1 기간') as HTMLInputElement;
    // 첫 포커스 — useEffect 에서 focus 적용됨
    await new Promise(r => setTimeout(r, 0));
    expect(document.activeElement).toBe(ma1);

    // 마지막 focusable (저장 버튼) 로 이동 후 Tab → 첫 요소로 순환
    const save = screen.getByRole('button', { name: '저장' }) as HTMLButtonElement;
    save.focus();
    expect(document.activeElement).toBe(save);
    await user.tab();
    expect(document.activeElement).toBe(ma1);

    // Shift+Tab 역방향 순환
    await user.tab({ shift: true });
    expect(document.activeElement).toBe(save);
  });

  it('backdrop 클릭 시 onClose 호출', async () => {
    const user = userEvent.setup();
    const { onClose } = renderDrawer();
    await user.click(screen.getByRole('button', { name: '닫기' }));
    expect(onClose).toHaveBeenCalledTimes(1);
  });
});
