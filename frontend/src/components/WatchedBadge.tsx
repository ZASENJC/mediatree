export function WatchedBadge({ watched }: { watched: boolean }) {
  if (!watched) return null
  return (
    <span className="absolute top-2 left-2 z-20 flex h-6 w-6 items-center justify-center rounded-br-lg bg-green-500 text-white shadow-lg" title="已看">
      <svg className="w-4 h-4 drop-shadow" viewBox="0 0 24 24" fill="currentColor">
        <path d="M14.4 6L14 4H5v17h2v-7h5.6l.4 2h7V6z" />
      </svg>
    </span>
  )
}
