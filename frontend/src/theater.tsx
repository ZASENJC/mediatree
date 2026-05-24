import { createContext, useContext, useState, type ReactNode } from 'react'

interface TheaterContextValue {
  theaterMode: boolean
  setTheaterMode: (value: boolean) => void
}

const TheaterContext = createContext<TheaterContextValue>({
  theaterMode: false,
  setTheaterMode: () => {},
})

export function TheaterProvider({ children }: { children: ReactNode }) {
  const [theaterMode, setTheaterMode] = useState(false)
  return (
    <TheaterContext.Provider value={{ theaterMode, setTheaterMode }}>
      {children}
    </TheaterContext.Provider>
  )
}

export function useTheater() {
  return useContext(TheaterContext)
}
