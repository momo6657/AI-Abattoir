export const AVATAR_COLORS = [
  "bg-blue-600", "bg-purple-600", "bg-green-600",
  "bg-red-600", "bg-yellow-600", "bg-pink-600",
  "bg-indigo-600", "bg-teal-600",
];

export function getAvatarLetter(name: string): string {
  return name.charAt(0).toUpperCase();
}

export function getAvatarBg(index: number): string {
  return AVATAR_COLORS[index % AVATAR_COLORS.length];
}

export function formatTime(dateStr: string): string {
  try {
    return new Date(dateStr).toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" });
  } catch {
    return "";
  }
}

export const STATUS_LABELS: Record<string, string> = {
  waiting: "等待中",
  active: "进行中",
  finished: "已结束",
  paused: "已暂停",
  in_progress: "进行中",
  voting: "投票中",
};

export function getStatusLabel(status: string): string {
  return STATUS_LABELS[status] || status;
}
