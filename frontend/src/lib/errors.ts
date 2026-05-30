export function extractErrorMessage(err: unknown, fallback: string): string {
  if (typeof err !== "object" || err === null) return fallback;

  const axiosErr = err as {
    message?: string;
    code?: string;
    response?: { data?: { detail?: unknown; message?: unknown } };
  };

  const detail = axiosErr.response?.data?.detail ?? axiosErr.response?.data?.message;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    const message = detail.map(formatValidationIssue).filter(Boolean).join("；");
    if (message) return message;
  }
  if (detail && typeof detail === "object") return JSON.stringify(detail);

  if (axiosErr.code === "ERR_NETWORK") {
    return "无法连接后端服务，请确认后端已启动，或检查 API 地址配置";
  }
  if (axiosErr.message) return axiosErr.message;
  return fallback;
}

function formatValidationIssue(issue: unknown): string {
  if (typeof issue === "string") return issue;
  if (!issue || typeof issue !== "object") return String(issue);

  const item = issue as { loc?: unknown[]; msg?: string };
  const loc = Array.isArray(item.loc)
    ? item.loc.filter((part) => part !== "body").join(".")
    : "";
  return loc ? `${loc}: ${item.msg || "参数错误"}` : item.msg || "参数错误";
}
