import type { ButtonHTMLAttributes } from 'react'

const base =
  'inline-flex shrink-0 cursor-pointer items-center justify-center gap-1 whitespace-nowrap transition-colors duration-150 disabled:cursor-not-allowed disabled:opacity-45'

const variants = {
  primary:
    'h-9 min-w-16 rounded-full bg-accent px-5 font-display font-semibold text-on-accent enabled:hover:bg-accent-hover',
  secondary:
    'h-8 min-w-16 rounded-lg border border-border bg-surface px-3 text-text enabled:hover:bg-accent-soft',
  text: 'h-8 rounded-lg px-2 text-accent enabled:hover:bg-accent-soft',
  icon: 'size-7 rounded-lg text-text-muted enabled:hover:bg-accent-soft enabled:hover:text-text',
}

interface Props extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: keyof typeof variants
}

export function Button({ variant = 'secondary', className = '', ...props }: Props) {
  return <button type="button" className={`${base} ${variants[variant]} ${className}`} {...props} />
}
