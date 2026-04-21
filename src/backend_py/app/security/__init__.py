"""보안 프리미티브 — 도메인 중립 암호화/검증 유틸.

의존: stdlib + `cryptography` 만. 다른 application/ adapter 레이어에서
자유롭게 import 가능해야 하므로 순환 방지를 위해 이 패키지는 아무것도 선제 import 안 함.
"""
from __future__ import annotations
