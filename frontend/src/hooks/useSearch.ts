import { useState, useEffect, useRef } from 'react'
import { api, Movie } from '../api'

export function useSearch() {
  const [searchQuery, setSearchQuery] = useState('')
  const [searchResults, setSearchResults] = useState<Movie[]>([])
  const [searchTotal, setSearchTotal] = useState(0)
  const [searchLoading, setSearchLoading] = useState(false)
  const [searchOpen, setSearchOpen] = useState(false)
  const abortRef = useRef(false)

  useEffect(() => {
    if (!searchQuery.trim()) {
      setSearchResults([])
      setSearchTotal(0)
      setSearchOpen(false)
      return
    }
    abortRef.current = false
    const timer = setTimeout(async () => {
      setSearchLoading(true)
      setSearchOpen(true)
      try {
        const data = await api.search(searchQuery.trim())
        if (abortRef.current) return
        setSearchResults(data.movies)
        setSearchTotal(data.total)
      } catch {
        if (abortRef.current) return
        setSearchResults([])
        setSearchTotal(0)
      }
      if (!abortRef.current) setSearchLoading(false)
    }, 300)
    return () => {
      clearTimeout(timer)
      abortRef.current = true
    }
  }, [searchQuery])

  const closeSearch = () => setSearchOpen(false)
  const clearSearch = () => {
    setSearchQuery('')
    setSearchResults([])
  }

  return {
    searchQuery,
    setSearchQuery,
    searchResults,
    searchTotal,
    searchLoading,
    searchOpen,
    closeSearch,
    clearSearch,
  }
}
