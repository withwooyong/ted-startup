package com.ted.signal.application.service;

import com.ted.signal.application.port.in.GetNotificationPreferenceUseCase;
import com.ted.signal.application.port.in.UpdateNotificationPreferenceUseCase;
import com.ted.signal.application.port.out.NotificationPreferenceRepository;
import com.ted.signal.domain.model.NotificationPreference;
import lombok.RequiredArgsConstructor;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
@RequiredArgsConstructor
@Transactional(readOnly = true)
public class NotificationPreferenceService
        implements GetNotificationPreferenceUseCase, UpdateNotificationPreferenceUseCase {

    private final NotificationPreferenceRepository repository;

    @Override
    public NotificationPreferenceView get() {
        return toView(loadOrCreate());
    }

    @Override
    @Transactional
    public NotificationPreferenceView update(UpdateCommand command) {
        var preference = loadOrCreate();
        preference.update(
                command.dailySummaryEnabled(),
                command.urgentAlertEnabled(),
                command.batchFailureEnabled(),
                command.weeklyReportEnabled(),
                command.minScore(),
                command.signalTypes()
        );
        return toView(repository.save(preference));
    }

    /**
     * 알림 필터링 용도로 TelegramNotificationService가 직접 조회할 때 사용.
     * 레코드 없으면 기본값(모두 enabled)을 메모리상으로만 반환 (쓰기 없음).
     */
    @Transactional(readOnly = true)
    public NotificationPreference getPreferenceForFiltering() {
        return repository.findById(NotificationPreference.SINGLETON_ID)
                .orElseGet(NotificationPreference::createDefault);
    }

    /**
     * 싱글톤 row 지연 생성. 동시 최초 요청에서 두 번째 save가 PK 충돌로 실패하면
     * 재조회로 recover하여 경합을 멱등 처리한다.
     */
    @Transactional
    NotificationPreference loadOrCreate() {
        var existing = repository.findById(NotificationPreference.SINGLETON_ID);
        if (existing.isPresent()) return existing.get();
        try {
            return repository.save(NotificationPreference.createDefault());
        } catch (DataIntegrityViolationException concurrentInsert) {
            return repository.findById(NotificationPreference.SINGLETON_ID)
                    .orElseThrow(() -> new IllegalStateException(
                            "동시 삽입 경합 후에도 싱글톤 row를 찾을 수 없습니다", concurrentInsert));
        }
    }

    private NotificationPreferenceView toView(NotificationPreference p) {
        return new NotificationPreferenceView(
                p.getDailySummaryEnabled(),
                p.getUrgentAlertEnabled(),
                p.getBatchFailureEnabled(),
                p.getWeeklyReportEnabled(),
                p.getMinScore(),
                p.getSignalTypes(),
                p.getUpdatedAt()
        );
    }
}
