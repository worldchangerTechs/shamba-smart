import type { HTMLAttributes, PropsWithChildren } from 'react'

export function Card({ children, className = '', ...props }: PropsWithChildren<HTMLAttributes<HTMLDivElement>>) {
  return <div className={`rounded-2xl bg-white shadow-soft border border-[rgba(23,20,10,0.12)] ${className}`} {...props}>{children}</div>
}
