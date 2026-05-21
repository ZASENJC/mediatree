export function WatchedBadge({ watched }: { watched: boolean }) {
  if (!watched) return null
  return (
    <span className="absolute left-2 top-2 z-20 flex h-7 w-7 items-center justify-center rounded-full border border-apple-mint/40 bg-apple-mint/80 text-white shadow-glow backdrop-blur-xl" title="已看">
      <svg className="h-4 w-4 drop-shadow" viewBox="0 0 24 24" fill="currentColor">
        <path d="M14.4 6L14 4H5v17h2v-7h5.6l.4 2h7V6z" />
      </svg>
    </span>
  )
}
