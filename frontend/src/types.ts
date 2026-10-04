export interface Issue {
  id: number;
  kind: string;
  detail: string;
  expected: number | null;
  parsed: number | null;
}

export interface Adjustment {
  id: number;
  date: string;
  description: string;
  amount: number;
  direction: "cargo" | "abono";
  note: string | null;
}

export interface Checkpoint {
  page: number;
  kind: string;
  printed: number | null;
  computed: number | null;
  difference: number | null;
  detail: string;
}

export interface StatementReport {
  status: string;
  background: string;
  year: number;
  month: number;
  month_name: string;
  expected_cargo: number | null;
  expected_abono: number | null;
  expected_net: number | null;
  computed_net: number;
  differences: { kind: string; expected: number | null; parsed: number | null; detail: string }[];
  missing_rows: { kind: string; expected: number | null; parsed: number | null; detail: string }[];
  checkpoints: Checkpoint[];
  warnings: string[];
  fidelity_warnings: string[];
}

export interface Statement {
  id: number;
  bank: string;
  file_name: string;
  pages: number;
  uploaded_at: string;
  status: string;
  error: string | null;
  progress_stage: string;
  progress_percent: number;
  started_at: string | null;
  finished_at: string | null;
  queue_position?: number | null;
  holder: string | null;
  account_number: string | null;
  period_start: string | null;
  period_end: string | null;
  saldo_inicio: number | null;
  saldo_final: number | null;
  total_cargo: number;
  total_abono: number;
  total_igtf: number;
  transaction_count: number;
  annex_count: number;
  pos_count: number;
  report?: StatementReport | null;
  issues?: Issue[];
  adjustments?: Adjustment[];
}

export interface Operation {
  id: number;
  statement_id: number;
  date: string;
  date_iso: string | null;
  number: string | null;
  description: string;
  cargo: number;
  abono: number;
  igtf: number;
  amount: number;
  direction: "cargo" | "abono";
  method: string;
  category: string;
  counterpart: string | null;
  counterpart_account: string | null;
  counterpart_bank: string | null;
  reference: string | null;
  concept: string | null;
  occurred_at: string | null;
  phone: string | null;
  balance_printed: number | null;
  balance_computed: number | null;
}

export interface OperationPage {
  total: number;
  page: number;
  page_size: number;
  items: Operation[];
}

export interface GroupedStat {
  label: string;
  count: number;
  cargo: number;
  abono: number;
}

export interface TopStat {
  label: string;
  count: number;
  total: number;
}

export interface MonthlyStat {
  statement_id: number;
  period_start: string | null;
  period_end: string | null;
  cargo: number;
  abono: number;
  saldo_inicio: number | null;
  saldo_final: number | null;
  count: number;
  status: string;
}

export interface Summary {
  total_cargo: number;
  total_abono: number;
  total_igtf: number;
  count: number;
  net: number;
  by_method: GroupedStat[];
  by_category: GroupedStat[];
  top_counterparts: { cargo: TopStat[]; abono: TopStat[] };
  top_concepts: { cargo: TopStat[]; abono: TopStat[] };
  adjustments: { cargo: number; abono: number };
  monthly: MonthlyStat[];
}

export interface Rule {
  id: number;
  pattern: string;
  category: string;
  priority: number;
}

export interface Bank {
  id: string;
  name: string;
  status: string;
}

export interface DuplicateOperation {
  id: number;
  statement_id: number;
  statement_file: string;
  date: string;
  description: string;
  counterpart: string | null;
}

export interface DuplicateGroup {
  amount: number;
  date_iso: string | null;
  direction: "cargo" | "abono";
  reference: string | null;
  counterpart_account: string | null;
  count: number;
  statement_count: number;
  operations: DuplicateOperation[];
}
