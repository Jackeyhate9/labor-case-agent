"use client";
import { clsx } from "clsx";
import { Check, CircleAlert, LoaderCircle, X } from "lucide-react";
export function Button({
  className,
  variant = "primary",
  busy,
  children,
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "danger" | "quiet";
  busy?: boolean;
}) {
  return (
    <button
      className={clsx("button", `button-${variant}`, className)}
      disabled={busy || props.disabled}
      {...props}
    >
      {busy && <LoaderCircle size={15} className="spin" />}
      {children}
    </button>
  );
}
export function Badge({
  status,
  children,
}: {
  status?: string;
  children: React.ReactNode;
}) {
  return (
    <span className={clsx("badge", status && `status-${status}`)}>
      {children}
    </span>
  );
}
export function Empty({
  title,
  body,
  action,
}: {
  title: string;
  body: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="empty">
      <div className="empty-mark">空</div>
      <h3>{title}</h3>
      <p>{body}</p>
      {action}
    </div>
  );
}
export function ErrorState({
  message,
  retry,
}: {
  message: string;
  retry?: () => void;
}) {
  return (
    <div className="notice danger">
      <CircleAlert size={18} />
      <div>
        <strong>数据未能载入</strong>
        <p>{message}</p>
      </div>
      {retry && (
        <Button variant="secondary" onClick={retry}>
          重试
        </Button>
      )}
    </div>
  );
}
export function StatusIcon({ status }: { status: string }) {
  return status === "passed" ? (
    <Check size={16} />
  ) : status === "failed" ? (
    <X size={16} />
  ) : (
    <CircleAlert size={16} />
  );
}
