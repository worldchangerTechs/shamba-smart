import type { ButtonHTMLAttributes, PropsWithChildren } from 'react'
import { IconLoader as LoaderCircle } from '../icons'

type ButtonVariant = 'primary' | 'secondary' | 'ghost'
interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant
  loading?: boolean
}

export function Button({
  children,
  variant = 'primary',
  loading = false,
  className = '',
  disabled,
  ...props
}: PropsWithChildren<ButtonProps>) {
  return (
    <button
      className={`button button-${variant} ${className}`}
      disabled={disabled || loading}
      {...props}
    >
      {loading && <LoaderCircle className="h-4 w-4 animate-spin motion-safe:animate-spin" aria-hidden />}
      {children}
    </button>
  )
}
