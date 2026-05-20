"use client";

import { useEffect } from "react";

interface ModalProps {
  open: boolean;
  onClose: () => void;
  title: string;
  children: React.ReactNode;
  maxWidth?: string;
}

export default function Modal({ open, onClose, title, children, maxWidth = "max-w-2xl" }: ModalProps) {
  useEffect(() => {
    const handleEsc = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    if (open) window.addEventListener("keydown", handleEsc);
    return () => window.removeEventListener("keydown", handleEsc);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div role="dialog" aria-modal="true" className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm animate-fade-in" onClick={onClose}>
      <div
        className={`bg-surface-raised border border-border rounded-2xl p-6 ${maxWidth} w-full mx-4 max-h-[80vh] overflow-y-auto shadow-2xl shadow-black/50 animate-slide-up`}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex justify-between items-center mb-4">
          <h3 className="text-xl font-bold">{title}</h3>
          <button onClick={onClose} aria-label="关闭" className="w-8 h-8 rounded-lg flex items-center justify-center text-gray-400 hover:text-white hover:bg-surface-overlay transition-colors text-xl">&times;</button>
        </div>
        {children}
      </div>
    </div>
  );
}
