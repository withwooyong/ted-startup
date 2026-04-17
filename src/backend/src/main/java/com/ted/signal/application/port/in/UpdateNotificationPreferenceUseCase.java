package com.ted.signal.application.port.in;

import com.ted.signal.application.port.in.GetNotificationPreferenceUseCase.NotificationPreferenceView;
import com.ted.signal.domain.enums.SignalType;
import com.ted.signal.domain.model.DomainError;
import com.ted.signal.domain.model.DomainException;

import java.util.ArrayList;
import java.util.List;

public interface UpdateNotificationPreferenceUseCase {

    NotificationPreferenceView update(UpdateCommand command);

    /**
     * 알림 설정 업데이트 명령. 생성 시점에 도메인 규칙(신호 타입 화이트리스트, 점수 범위, 배열 크기)을
     * 검증한다. 사용자 입력은 에러 메시지에 반사하지 않도록 고정 reason 사용.
     */
    record UpdateCommand(
            boolean dailySummaryEnabled,
            boolean urgentAlertEnabled,
            boolean batchFailureEnabled,
            boolean weeklyReportEnabled,
            int minScore,
            List<String> signalTypes
    ) {
        private static final int MIN_SCORE_LOWER = 0;
        private static final int MIN_SCORE_UPPER = 100;
        private static final int SIGNAL_TYPES_MAX = SignalType.values().length;

        public UpdateCommand {
            if (minScore < MIN_SCORE_LOWER || minScore > MIN_SCORE_UPPER) {
                throw new DomainException(new DomainError.InvalidParameter(
                        "minScore", "0~100 범위여야 합니다"));
            }
            if (signalTypes == null || signalTypes.isEmpty()) {
                throw new DomainException(new DomainError.InvalidParameter(
                        "signalTypes", "최소 한 개 이상 선택해야 합니다"));
            }
            if (signalTypes.size() > SIGNAL_TYPES_MAX) {
                throw new DomainException(new DomainError.InvalidParameter(
                        "signalTypes", "허용된 타입 수를 초과했습니다"));
            }
            var validated = new ArrayList<String>(signalTypes.size());
            for (String raw : signalTypes) {
                try {
                    SignalType.valueOf(raw);
                    validated.add(raw);
                } catch (IllegalArgumentException | NullPointerException ex) {
                    throw new DomainException(new DomainError.InvalidParameter(
                            "signalTypes", "허용되지 않는 시그널 타입이 포함되어 있습니다"));
                }
            }
            signalTypes = List.copyOf(validated);
        }
    }
}
