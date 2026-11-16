import { useEffect, useRef } from 'react'
import { Route, Routes, useLocation } from 'react-router-dom'
import { Footer, Header } from './components/Chrome'
import Home from './pages/Home'
import ToolPage from './pages/ToolPage'
import Shops from './pages/Shops'
import ShopPage from './pages/ShopPage'
import About from './pages/About'
import { NotFound } from './components/Bits'

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
    <>
      <a className="skip" href="#main">跳到正文</a>
      <Header />
      <main id="main" tabIndex={-1} className="wrap page">
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/tool/:name" element={<ToolPage />} />
          <Route path="/shops" element={<Shops />} />
          <Route path="/shop/:id" element={<ShopPage />} />
          <Route path="/about" element={<About />} />
          <Route path="*" element={<NotFound />} />
        </Routes>
      </main>
      <Footer />
    </>
  )
}
