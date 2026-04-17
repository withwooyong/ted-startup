package com.ted.signal.application.port.out;

import com.ted.signal.domain.model.NotificationPreference;
import org.springframework.data.jpa.repository.JpaRepository;

public interface NotificationPreferenceRepository extends JpaRepository<NotificationPreference, Long> {
}
