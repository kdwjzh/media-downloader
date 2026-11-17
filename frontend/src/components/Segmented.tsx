import { useId } from 'react'

interface Props<T extends string | number> {
  /** Id of the visible label. */
  labelledBy: string
  options: readonly { value: T; label: string; disabled?: boolean }[]
  value: T
  onChange: (value: T) => void
}

/** Side-by-side radio buttons, the chosen one filled (MASTER: inputs). Native radios: Tab
 *  enters at the chosen one, arrow keys move and choose. */
export function Segmented<T extends string | number>({ labelledBy, options, value, onChange }: Props<T>) {
  const name = useId()
  return (
    <div role="radiogroup" aria-labelledby={labelledBy} className="flex h-9 items-center rounded-lg border border-border bg-surface p-0.5">
      {options.map((o) => (
        <label key={o.value} className="cursor-pointer has-disabled:cursor-not-allowed has-disabled:opacity-45">
          <input
            type="radio"
            name={name}
            className="peer sr-only"
            checked={value === o.value}
            disabled={o.disabled}
            onChange={() => onChange(o.value)}
          />
          <span className="flex h-7.5 min-w-12 items-center justify-center rounded-md px-3 tabular-nums transition-colors duration-150 peer-checked:bg-accent peer-checked:text-on-accent peer-focus-visible:outline-2 peer-focus-visible:outline-offset-2 peer-focus-visible:outline-accent peer-not-checked:peer-enabled:hover:bg-accent-soft">
            {o.label}
          </span>
        </label>
      ))}
    </div>
  )
}
