import type {
  Bank,
  OperationPage,
  Rule,
  Statement,
  Summary,
} from "./types";

async function request<T>(url: string, options?: RequestInit): Promise<T> {
  const response = await fetch(url, options);
  if (!response.ok) {
    let detail = `Error ${response.status}`;
    try {
      const payload = await response.json();
      detail =
        typeof payload.detail === "string"
          ? payload.detail
          : payload.detail?.message ?? JSON.stringify(payload.detail ?? payload);
    } catch {
      /* respuesta sin JSON */
    }
    throw new Error(detail);
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

export const api = {
  statements: () => request<Statement[]>("/api/statements"),
  statement: (id: number) => request<Statement>(`/api/statements/${id}`),
  upload: (file: File) => {
    const data = new FormData();
    data.append("file", file);
    return request<Statement>("/api/statements", { method: "POST", body: data });
  },
  deleteStatement: (id: number) =>
    request<void>(`/api/statements/${id}`, { method: "DELETE" }),
  addAdjustment: (
    id: number,
    payload: { date: string; description: string; amount: number; direction: string; note?: string },
  ) =>
    request(`/api/statements/${id}/adjustments`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }),
  deleteAdjustment: (id: number, adjustmentId: number) =>
    request<void>(`/api/statements/${id}/adjustments/${adjustmentId}`, { method: "DELETE" }),
  operations: (params: URLSearchParams) =>
    request<OperationPage>(`/api/operations?${params.toString()}`),
  summary: (statementId?: number) =>
    request<Summary>(`/api/stats/summary${statementId ? `?statement_id=${statementId}` : ""}`),
  biggest: (statementId?: number) =>
    request<import("./types").Operation[]>(
      `/api/stats/biggest${statementId ? `?statement_id=${statementId}` : ""}`,
    ),
  rules: () => request<Rule[]>("/api/rules"),
  createRule: (payload: { pattern: string; category: string; priority: number }) =>
    request<Rule>("/api/rules", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }),
  deleteRule: (id: number) => request<void>(`/api/rules/${id}`, { method: "DELETE" }),
  banks: () => request<Bank[]>("/api/banks"),
  categories: () => request<{ categories: string[] }>("/api/categories"),
};

export function exportUrl(params: URLSearchParams): string {
  const copy = new URLSearchParams(params);
  copy.delete("page");
  copy.delete("page_size");
  return `/api/export.csv?${copy.toString()}`;
}
