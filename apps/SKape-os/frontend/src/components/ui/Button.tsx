import type { ButtonHTMLAttributes } from "react";

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement>;

function Button({
  children,
  className = "",
  ...props
}: ButtonProps) {
  return (
    <button
      className={`
        w-full
        rounded-xl
        bg-emerald-600
        px-4
        py-3
        font-semibold
        text-white
        transition-all
        duration-200
        hover:bg-emerald-500
        hover:scale-[1.01]
        active:scale-[0.99]
        disabled:cursor-not-allowed
        disabled:opacity-50
        ${className}
      `}
      {...props}
    >
      {children}
    </button>
  );
}

export default Button;