import { forwardRef, type ButtonHTMLAttributes } from "react";
import { clsx } from "clsx";

type ButtonTone = "primary" | "secondary" | "quiet";

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  tone?: ButtonTone;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { className, tone = "primary", type = "button", ...props },
  ref,
) {
  return <button ref={ref} type={type} className={clsx("button", `button--${tone}`, className)} {...props} />;
});
