interface BadgeProps {
  text: string;
  variant?: "default" | "success" | "warning" | "danger" | "info";
  size?: "sm" | "md";
}

const variants = {
  default: "bg-gray-800 text-gray-300",
  success: "bg-green-900 text-green-300",
  warning: "bg-yellow-900 text-yellow-300",
  danger: "bg-red-900 text-red-300",
  info: "bg-blue-900 text-blue-300",
};

export default function Badge({ text, variant = "default", size = "sm" }: BadgeProps) {
  const sizeClass = size === "sm" ? "px-2 py-0.5 text-xs" : "px-3 py-1 text-sm";
  return (
    <span role="status" className={`rounded-full ${sizeClass} ${variants[variant]}`}>
      {text}
    </span>
  );
}
