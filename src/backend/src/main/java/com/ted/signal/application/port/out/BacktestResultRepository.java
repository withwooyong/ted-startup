package com.ted.signal.application.port.out;

import com.ted.signal.domain.model.BacktestResult;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.Optional;

public interface BacktestResultRepository extends JpaRepository<BacktestResult, Long> {

    List<BacktestResult> findBySignalTypeOrderByCreatedAtDesc(String signalType);

    Optional<BacktestResult> findFirstBySignalTypeOrderByCreatedAtDesc(String signalType);

    List<BacktestResult> findTop20ByOrderByCreatedAtDesc();
}
