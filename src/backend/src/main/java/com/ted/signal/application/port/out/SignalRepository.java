package com.ted.signal.application.port.out;

import com.ted.signal.domain.enums.SignalType;
import com.ted.signal.domain.model.Signal;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import java.time.LocalDate;
import java.util.List;

public interface SignalRepository extends JpaRepository<Signal, Long> {

    List<Signal> findBySignalDateOrderByScoreDesc(LocalDate date);

    @Query("""
            SELECT s FROM Signal s
            JOIN FETCH s.stock
            WHERE s.signalDate = :date
            ORDER BY s.score DESC
            """)
    List<Signal> findBySignalDateWithStockOrderByScoreDesc(@Param("date") LocalDate date);

    @Query("""
            SELECT s FROM Signal s
            JOIN FETCH s.stock st
            WHERE s.signalDate = :date
              AND (:type IS NULL OR s.signalType = :type)
            ORDER BY s.score DESC
            """)
    List<Signal> findByDateAndType(
            @Param("date") LocalDate date,
            @Param("type") SignalType type);

    List<Signal> findByStockIdAndSignalDateBetweenOrderBySignalDateDesc(
            Long stockId, LocalDate from, LocalDate to);

    boolean existsByStockIdAndSignalDateAndSignalType(Long stockId, LocalDate date, SignalType type);

    @Query("""
            SELECT s FROM Signal s
            JOIN FETCH s.stock
            WHERE s.signalDate BETWEEN :from AND :to
            ORDER BY s.signalDate ASC
            """)
    List<Signal> findBySignalDateBetweenWithStock(
            @Param("from") LocalDate from,
            @Param("to") LocalDate to);
}
