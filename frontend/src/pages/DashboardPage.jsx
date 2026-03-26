import { useNavigate } from 'react-router-dom'
import AdminMenu from '../components/AdminMenu'

/* ── Mock Data ── */
const DATA = {
    kpis: [
        { label: '检验报告', value: '1,284', unit: '份', trend: '+12.3%', color: '#3B82F6' },
        { label: '送检物品', value: '3,672', unit: '件', trend: '+8.7%', color: '#8B5CF6' },
        { label: '送检人员', value: '89', unit: '人', trend: '+3.4%', color: '#06B6D4' },
        { label: '涉及国标', value: '156', unit: '项', trend: '+5.1%', color: '#10B981' },
    ],
    categories: [
        { name: '肉制品', count: 342, pct: 22 },
        { name: '乳制品', count: 287, pct: 18 },
        { name: '饮料', count: 231, pct: 15 },
        { name: '调味品', count: 198, pct: 13 },
        { name: '糕点', count: 176, pct: 11 },
        { name: '食用油', count: 143, pct: 9 },
        { name: '其他', count: 295, pct: 12 },
    ],
    submitters: [
        { name: '张伟', dept: '质检部', count: 142 },
        { name: '李娟', dept: '监管科', count: 118 },
        { name: '王明', dept: '抽检组', count: 97 },
        { name: '陈芳', dept: '检验室', count: 83 },
        { name: '刘洋', dept: '质检部', count: 71 },
    ],
    standards: [
        { code: 'GB 2762', name: '食品中污染物限量', count: 89 },
        { code: 'GB 2763', name: '农药最大残留限量', count: 76 },
        { code: 'GB 23200', name: '农药残留检测方法', count: 65 },
        { code: 'GB 5009', name: '食品理化检验方法', count: 54 },
        { code: 'GB 7718', name: '预包装食品标签通则', count: 43 },
    ],
    trend: [
        { month: '9月', count: 87 },
        { month: '10月', count: 124 },
        { month: '11月', count: 98 },
        { month: '12月', count: 145 },
        { month: '1月', count: 112 },
        { month: '2月', count: 156 },
        { month: '3月', count: 189 },
    ],
}

const PALETTE = ['#3B82F6', '#8B5CF6', '#06B6D4', '#10B981', '#F59E0B', '#EF4444', '#64748B']

/* ── Donut Chart ── */
function DonutChart({ data }) {
    const total = data.reduce((s, d) => s + d.count, 0)
    const cx = 84, cy = 84, r = 62

    const toRad = (deg) => (deg * Math.PI) / 180
    const polarXY = (angle, radius) => ({
        x: cx + radius * Math.cos(toRad(angle)),
        y: cy + radius * Math.sin(toRad(angle)),
    })

    let cursor = -90
    const slices = data.map((d, i) => {
        const sweep = (d.count / total) * 359.99
        const start = cursor
        cursor += sweep
        const s = polarXY(start, r)
        const e = polarXY(start + sweep, r)
        const large = sweep > 180 ? 1 : 0
        return {
            ...d,
            color: PALETTE[i],
            d: `M ${s.x} ${s.y} A ${r} ${r} 0 ${large} 1 ${e.x} ${e.y}`,
        }
    })

    return (
        <div className="donut-wrap">
            <svg viewBox="0 0 168 168" width="168" height="168" style={{ flexShrink: 0 }}>
                {slices.map((sl, i) => (
                    <path key={i} d={sl.d} fill="none" stroke={sl.color} strokeWidth="20" strokeLinecap="butt" />
                ))}
                <text x={cx} y={cy - 7} textAnchor="middle" fill="#F1F5F9" fontSize="22" fontWeight="700">
                    {total.toLocaleString()}
                </text>
                <text x={cx} y={cy + 13} textAnchor="middle" fill="#64748B" fontSize="10">
                    送检物品总计
                </text>
            </svg>
            <div className="donut-legend">
                {data.map((d, i) => (
                    <div key={i} className="donut-legend-row">
                        <span className="donut-dot" style={{ background: PALETTE[i] }} />
                        <span className="donut-name">{d.name}</span>
                        <span className="donut-pct">{d.pct}%</span>
                    </div>
                ))}
            </div>
        </div>
    )
}

/* ── Bar Chart ── */
function BarChart({ data }) {
    const max = Math.max(...data.map(d => d.count))
    const W = 52
    const H = 110
    const total = data.length

    return (
        <div className="bar-chart-outer">
            <svg viewBox={`0 0 ${total * W} ${H + 28}`} width="100%" height={H + 28}>
                <defs>
                    <linearGradient id="bGrad" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="#3B82F6" stopOpacity="0.95" />
                        <stop offset="100%" stopColor="#3B82F6" stopOpacity="0.35" />
                    </linearGradient>
                </defs>
                {data.map((d, i) => {
                    const bH = Math.max(4, (d.count / max) * H)
                    const x = i * W + 6
                    const y = H - bH
                    return (
                        <g key={i}>
                            <rect x={x} y={y} width={40} height={bH} fill="url(#bGrad)" rx="4" />
                            <text x={x + 20} y={H + 16} textAnchor="middle" fill="#475569" fontSize="10">{d.month}</text>
                            <text x={x + 20} y={y - 5} textAnchor="middle" fill="#64748B" fontSize="9">{d.count}</text>
                        </g>
                    )
                })}
            </svg>
            <div className="bar-footer">
                <span>最近7个月送检报告数量</span>
                <span className="bar-peak-label">峰值 189份（3月）</span>
            </div>
        </div>
    )
}

/* ── Rank List ── */
function RankList({ items, maxKey = 'count', accentColor = '#3B82F6', codeKey }) {
    const max = Math.max(...items.map(d => d.count))
    return (
        <div className="rank-list">
            {items.map((item, i) => (
                <div key={i} className="rank-row">
                    <span className="rank-num" style={{ color: i < 3 ? accentColor : '#475569' }}>{i + 1}</span>
                    <div className="rank-body">
                        <div className="rank-label">
                            {codeKey && <span className="rank-code-tag" style={{ borderColor: accentColor + '40', color: accentColor }}>{item[codeKey]}</span>}
                            <span className="rank-name">{item.name}</span>
                            {item.dept && <span className="rank-tag">{item.dept}</span>}
                        </div>
                        <div className="rank-bar-bg">
                            <div className="rank-bar-fg" style={{ width: `${(item.count / max) * 100}%`, background: i < 3 ? accentColor : '#334155' }} />
                        </div>
                    </div>
                    <span className="rank-val">{item.count}</span>
                </div>
            ))}
        </div>
    )
}

/* ── Main Dashboard ── */
export default function DashboardPage() {
    const navigate = useNavigate()
    const dateStr = new Date().toLocaleDateString('zh-CN', { year: 'numeric', month: 'long', day: 'numeric' })

    return (
        <div className="dash-page">
            {/* Header */}
            <header className="dash-header">
                <div className="dash-header-left">
                    <button className="dash-back-btn" onClick={() => navigate(-1)}>
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                            <polyline points="15 18 9 12 15 6" />
                        </svg>
                    </button>
                    <div className="dash-badge">SafeFood AI Auditor</div>
                    <div className="dash-divider" />
                    <h1 className="dash-title">驾驶舱</h1>
                    <span className="dash-subtitle">统计分析仪表盘 · 模拟数据</span>
                </div>
                <div className="dash-header-right">
                    <div className="dash-live">
                        <span className="dash-live-dot" />
                        <span>实时数据 · {dateStr}</span>
                    </div>
                    <AdminMenu />
                </div>
            </header>

            <div className="dash-body">
                {/* KPI Row */}
                <div className="dash-kpi-row">
                    {DATA.kpis.map((k, i) => (
                        <div key={i} className="dash-kpi-card">
                            <div className="kpi-indicator" style={{ background: k.color + '22', borderColor: k.color + '44' }}>
                                <span style={{ color: k.color, fontSize: 10, fontWeight: 700 }}>▲ {k.trend}</span>
                            </div>
                            <div className="kpi-value">
                                {k.value}
                                <span className="kpi-unit">{k.unit}</span>
                            </div>
                            <div className="kpi-label">{k.label}</div>
                            <div className="kpi-bar" style={{ background: k.color + '18' }}>
                                <div className="kpi-bar-fill" style={{ background: k.color, width: '68%' }} />
                            </div>
                        </div>
                    ))}
                </div>

                {/* Row 1: Donut + Bar */}
                <div className="dash-row">
                    <div className="dash-card" style={{ flex: '0 0 400px' }}>
                        <div className="dash-card-hd">
                            <span className="dash-card-title">品类分布</span>
                            <span className="dash-card-sub">按送检物品分类统计</span>
                        </div>
                        <DonutChart data={DATA.categories} />
                    </div>
                    <div className="dash-card" style={{ flex: 1 }}>
                        <div className="dash-card-hd">
                            <span className="dash-card-title">月度送检趋势</span>
                            <span className="dash-card-sub">近7个月报告数量变化</span>
                        </div>
                        <BarChart data={DATA.trend} />
                    </div>
                </div>

                {/* Row 2: Submitters + Standards */}
                <div className="dash-row">
                    <div className="dash-card" style={{ flex: 1 }}>
                        <div className="dash-card-hd">
                            <span className="dash-card-title">送检人排行</span>
                            <span className="dash-card-sub">TOP 5</span>
                        </div>
                        <RankList items={DATA.submitters} accentColor="#3B82F6" />
                    </div>
                    <div className="dash-card" style={{ flex: 1 }}>
                        <div className="dash-card-hd">
                            <span className="dash-card-title">高频涉及国标</span>
                            <span className="dash-card-sub">TOP 5</span>
                        </div>
                        <RankList items={DATA.standards} accentColor="#06B6D4" codeKey="code" />
                    </div>
                </div>
            </div>
        </div>
    )
}
