import { useEffect } from 'react'
import { useApi } from '../lib/useApi'
import { when } from '../lib/format'
import type { Home } from '../lib/types'

export default function About() {
  const { data } = useApi<Home>('/api/v4/home')
  useEffect(() => { document.title = '数据说明 | AI 订阅比价' }, [])
  return (
    <article className="prose">
      <h1 className="page-h">数据说明</h1>
      <h2>价格从哪里来</h2>
      <p>程序每天读取店铺公开的商品页，记录商品标题、价格、库存和读取时间。没有读到价格的商品不显示价格，也不用别处的数字代替。{data ? `最近一次更新是 ${when(data.updated_at, true)}（北京时间）。` : ''}</p>
      <h2>怎么比</h2>
      <p>同一个工具下，期限、额度、套餐、区域和交付方式不同的商品分开比，不会把月卡和年卡放在一起排价格。规格信息不完整的商品只和标题完全相同的商品比。首页卡片显示的是入门月付规格的最低价，已售罄的商品不计入。</p>
      <h2>店铺链接</h2>
      <p>点击“去店铺”会在新标签页打开店铺页面。店铺都是第三方，购买前请自行核对商品页上的价格、库存和售后说明。</p>
      <h2>免责声明</h2>
      <p>所有店铺均为非官方渠道，购买或代充可能违反官方服务协议。本站只整理公开信息，不参与交易，不担保价格、库存、账号可用性和售后。</p>
      <h2>图标</h2>
      <p>商品图标来自开源图标库 lobe-icons（MIT 许可）和 simple-icons（CC0），Muse 和 Midjourney 的图形取自各自官方来源，详见项目里的 logos/README.md。商标归各自所有者，本站与这些公司没有关联。</p>
    </article>
  )
}
