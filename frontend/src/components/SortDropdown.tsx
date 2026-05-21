interface SortOption {
  key: string
  label: string
}

interface Props {
  options: SortOption[]
  current: string
  onChange: (key: string) => void
}

export default function SortDropdown({ options, current, onChange }: Props) {
  return (
    <select
      value={current}
      onChange={e => onChange(e.target.value)}
      className="glass-input cursor-pointer appearance-none px-3 py-1.5 text-center text-xs text-gray-300"
      style={{ textAlignLast: 'center' }}
    >
      {options.map(opt => (
        <option key={opt.key} value={opt.key}>{opt.label}</option>
      ))}
    </select>
  )
}
