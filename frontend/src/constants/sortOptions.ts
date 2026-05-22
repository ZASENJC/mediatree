export interface SortOption {
  key: string
  label: string
}

/** 通用排序选项（含发行日期） */
export const LIBRARY_SORT_OPTIONS: SortOption[] = [
  { key: 'created_desc', label: '最近添加' },
  { key: 'created_asc', label: '最早添加' },
  { key: 'name', label: '名称' },
  { key: 'release_date_desc', label: '发行日期新到旧' },
  { key: 'release_date_asc', label: '发行日期旧到新' },
  { key: 'random', label: '随机' },
]

/** 收藏页排序（不含发行日期） */
export const FAVORITES_SORT_OPTIONS: SortOption[] = LIBRARY_SORT_OPTIONS.filter(
  o => o.key !== 'release_date_desc' && o.key !== 'release_date_asc',
)

/** 浏览页排序（文件夹名称 label） */
export const BROWSE_SORT_OPTIONS: SortOption[] = LIBRARY_SORT_OPTIONS.map(o =>
  o.key === 'name' ? { ...o, label: '文件夹名称' } : o,
)
