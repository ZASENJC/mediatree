import { useEffect, useMemo, useState } from 'react'

export interface FolderLogo {
  url: string
  width?: number | null
  height?: number | null
  language?: string | null
}

function logoLanguage(logo: FolderLogo) {
  return (logo.language || '').toLowerCase().split('-')[0]
}

function logoArea(logo: FolderLogo) {
  return (logo.width || 0) * (logo.height || 0)
}

export function buildFolderLogoQueue(logos: FolderLogo[]) {
  const languagePriority = { zh: 0, en: 1 } as const
  const seen = new Set<string>()

  return logos
    .filter(logo => logo.url && logoLanguage(logo) in languagePriority)
    .sort((left, right) => {
      const languageDifference = languagePriority[logoLanguage(left) as keyof typeof languagePriority]
        - languagePriority[logoLanguage(right) as keyof typeof languagePriority]
      return languageDifference || logoArea(right) - logoArea(left)
    })
    .filter(logo => {
      if (seen.has(logo.url)) return false
      seen.add(logo.url)
      return true
    })
}

export function findAvailableFolderLogo(logos: FolderLogo[], failedUrls: ReadonlySet<string>) {
  return logos.find(logo => !failedUrls.has(logo.url))
}

interface FolderTitleProps {
  title: string
  logos: FolderLogo[]
  hasBackdrop: boolean
}

export default function FolderTitle({ title, logos, hasBackdrop }: FolderTitleProps) {
  const logoQueue = useMemo(() => buildFolderLogoQueue(logos), [logos])
  const logoQueueKey = logoQueue.map(logo => logo.url).join('|')
  const [failedUrls, setFailedUrls] = useState<Set<string>>(() => new Set())

  useEffect(() => {
    setFailedUrls(new Set())
  }, [logoQueueKey])

  const activeLogo = findAvailableFolderLogo(logoQueue, failedUrls)
  const textClassName = hasBackdrop
    ? 'max-w-4xl break-words text-4xl font-bold tracking-tight text-white drop-shadow-2xl sm:text-6xl'
    : 'break-words text-3xl font-bold tracking-tight text-white sm:text-4xl'

  if (!activeLogo) {
    return <h1 className={textClassName}>{title}</h1>
  }

  const frameClassName = hasBackdrop
    ? 'flex h-24 w-[82vw] max-w-2xl items-end sm:h-36'
    : 'flex h-20 w-[78vw] max-w-xl items-end sm:h-28'

  return (
    <h1 className={frameClassName} aria-label={title}>
      <img
        key={activeLogo.url}
        src={activeLogo.url}
        alt=""
        aria-hidden="true"
        className="block max-h-full max-w-full object-contain object-left-bottom drop-shadow-[0_4px_18px_rgba(0,0,0,0.75)]"
        onError={() => {
          setFailedUrls(current => new Set(current).add(activeLogo.url))
        }}
      />
    </h1>
  )
}
