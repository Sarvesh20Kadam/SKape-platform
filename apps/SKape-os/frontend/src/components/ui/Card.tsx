import type { ReactNode } from "react";

type CardProps = {
  children: ReactNode;
};

function Card({ children }: CardProps) {
  return (
    <div className="rounded-2xl border border-zinc-800 bg-zinc-900 p-10 shadow-2xl">
      {children}
    </div>
  );
}

export default Card;