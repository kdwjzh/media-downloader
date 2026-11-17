/** Three stacked record sleeves above an empty screen, drawn with CSS. Decorative and static. */
export function Sleeves() {
  return (
    <div aria-hidden="true" className="relative mb-4 h-20 w-28">
      <div className="absolute top-2 left-0 size-16 -rotate-6 rounded-md bg-accent-soft" />
      <div className="absolute top-0 left-6 size-16 rotate-3 rounded-md bg-highlight" />
      <div className="absolute top-3 left-12 size-16 rounded-md bg-accent" />
    </div>
  )
}
