// 백엔드(FastAPI + Pydantic) 응답 키 규약에 따라 snake_case 를 그대로 사용.
// 기존 signal.ts 는 camelCase 라 불일치가 있으나, 본 도메인(P14)부터는 runtime 전송
// 포맷과 타입을 일치시켜 변환 레이어를 제거한다.

export type BrokerCode = 'manual' | 'kis' | 'kiwoom';
export type ConnectionType = 'manual' | 'kis_rest_mock';
export type TransactionType = 'BUY' | 'SELL';
export type TransactionSource = 'manual' | 'kis_sync';

export interface Account {
  id: number;
  account_alias: string;
  broker_code: BrokerCode;
  connection_type: ConnectionType;
  environment: 'mock' | 'real';
  is_active: boolean;
  created_at: string;
}

export interface AccountCreateRequest {
  account_alias: string;
  broker_code: BrokerCode;
  connection_type: ConnectionType;
  environment: 'mock';
}

export interface Holding {
  account_id: number;
  stock_id: number;
  stock_code: string | null;
  stock_name: string | null;
  quantity: number;
  avg_buy_price: string;
  first_bought_at: string;
  last_transacted_at: string | null;
}

export interface TransactionCreateRequest {
  stock_code: string;
  transaction_type: TransactionType;
  quantity: number;
  price: string;
  executed_at: string;
  memo?: string;
}

export interface Transaction {
  id: number;
  account_id: number;
  stock_id: number;
  transaction_type: TransactionType;
  quantity: number;
  price: string;
  executed_at: string;
  source: TransactionSource;
  memo: string | null;
  created_at: string;
}

export interface Snapshot {
  account_id: number;
  snapshot_date: string;
  total_value: string;
  total_cost: string;
  unrealized_pnl: string;
  realized_pnl: string;
  holdings_count: number;
}

export interface PerformanceReport {
  account_id: number;
  start_date: string;
  end_date: string;
  samples: number;
  total_return_pct: string | null;
  max_drawdown_pct: string | null;
  sharpe_ratio: string | null;
  first_value: string | null;
  last_value: string | null;
}

export interface SyncResult {
  account_id: number;
  connection_type: string;
  fetched_count: number;
  created_count: number;
  updated_count: number;
  unchanged_count: number;
  stock_created_count: number;
}

export interface AlignedSignalItem {
  signal_date: string;
  signal_type: string;
  score: number;
  grade: string;
}

export interface AlignedHoldingItem {
  stock_id: number;
  stock_code: string;
  stock_name: string;
  quantity: number;
  avg_buy_price: string;
  max_score: number;
  hit_count: number;
  signals: AlignedSignalItem[];
}

export interface SignalAlignmentReport {
  account_id: number;
  since: string;
  until: string;
  min_score: number;
  total_holdings: number;
  aligned_holdings: number;
  items: AlignedHoldingItem[];
}
