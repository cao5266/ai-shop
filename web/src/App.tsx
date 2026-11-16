import { useEffect, useRef } from 'react'
import { Route, Routes, useLocation } from 'react-router-dom'
import { SiteFooter, SiteHeader } from './components/SiteChrome'
import { NotFound } from './components/Bits'
import Home from './pages/Home'
import ToolPage from './pages/ToolPage'
import Shops from './pages/Shops'
import ShopPage from './pages/ShopPage'
import About from './pages/About'

export default function App() {
  const { pathname } = useLocation()
  const first = useRef(true)
  useEffect(() => {
    window.scrollTo(0, 0)
    // 单页应用切换路由后，把焦点移到正文，键盘和读屏用户才知道页面变了
    if (first.current) first.current = false
    else document.getElementById('main')?.focus({ preventScroll: true })
  }, [pathname])
  return (
    <div className="flex min-h-screen flex-col">
      <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:top-3 focus:left-4 focus:z-50 focus:rounded-lg focus:bg-foreground focus:px-4 focus:py-2 focus:text-background">跳到正文</a>
      <SiteHeader />
      <main id="main" tabIndex={-1} className="mx-auto w-full max-w-[1200px] flex-1 animate-in fade-in px-4 pb-20 duration-150 motion-reduce:animate-none sm:px-6">
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/tool/:name" element={<ToolPage />} />
          <Route path="/shops" element={<Shops />} />
          <Route path="/shop/:id" element={<ShopPage />} />
          <Route path="/about" element={<About />} />
          <Route path="*" element={<NotFound />} />
        </Routes>
      </main>
      <SiteFooter />
    </div>
  )
}
