export default function ScanToast({ status, done, total }: { status: string; done: number; total: number }) {
  const pct = total > 0 ? Math.max(4, Math.min(100, (done / total) * 100)) : 100
  const complete = status.includes('完成')
  return (
    <div className="fixed bottom-3 left-3 right-3 z-50 rounded-3xl border border-white/10 bg-black/60 p-4 shadow-glass backdrop-blur-2xl sm:bottom-4 sm:left-auto sm:right-4 sm:w-80">
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className={`text-sm font-medium ${complete ? 'text-green-300' : 'text-white'}`}>{status}</p>
          {!complete && total > 0 && <p className="mt-1 text-xs text-gray-500">{done}/{total}</p>}
        </div>
        {!complete && <div className="h-4 w-4 animate-spin rounded-full border-2 border-apple-blue border-t-transparent" />}
      </div>
      {!complete && (
        <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-white/10">
          <div className="h-full rounded-full bg-apple-blue transition-all duration-500" style={{ width: `${pct}%` }} />
        </div>
      )}
    </div>
  )
}
