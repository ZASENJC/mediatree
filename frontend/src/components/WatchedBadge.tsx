export function WatchedBadge({ watched }: { watched: boolean }) {
  if (!watched) return null
  return (
    <span className="absolute top-2 left-2 z-10 text-xs" title="已看">
      <svg className="w-4 h-4 text-green-400 drop-shadow-lg" viewBox="0 0 24 24" fill="currentColor">
        <path d="M14.4 6L14 4H5v17h2v-7h5.6l.4 2h7V6z" />
      </svg>
    </span>
  )
}
