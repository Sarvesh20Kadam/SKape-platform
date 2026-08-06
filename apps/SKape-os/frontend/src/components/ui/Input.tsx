import type { InputHTMLAttributes } from "react";

type InputProps = InputHTMLAttributes<HTMLInputElement> & {
  label: string;
};

function Input({
  label,
  className = "",
  ...props
}: InputProps) {
  return (
    <div className="space-y-2">
      <label className="block text-sm text-zinc-400">
        {label}
      </label>

      <input
        className={`
          w-full
          rounded-xl
          border
          border-zinc-700
          bg-zinc-800
          px-4
          py-3
          text-white
          outline-none
          transition
          focus:border-emerald-500
          focus:ring-2
          focus:ring-emerald-500/20
          ${className}
        `}
        {...props}
      />
    </div>
  );
}

export default Input;