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
      className="px-3 py-1.5 bg-dark-700 border border-dark-600 rounded text-xs text-gray-300 focus:outline-none focus:border-blue-500 appearance-none cursor-pointer"
    >
      {options.map(opt => (
        <option key={opt.key} value={opt.key}>{opt.label}</option>
      ))}
    </select>
  )
}
