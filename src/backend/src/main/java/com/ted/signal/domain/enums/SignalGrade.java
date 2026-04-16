package com.ted.signal.domain.enums;

public enum SignalGrade {
    A, B, C, D;

    public static SignalGrade fromScore(int score) {
        if (score >= 80) return A;
        if (score >= 60) return B;
        if (score >= 40) return C;
        return D;
    }
}
