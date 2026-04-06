import { useEffect, useState, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import AdminMenu from '../components/AdminMenu'

/* ───────── 指标比较工具函数 ───────── */
// 标准化字符串：去空格、全角数字、统一分隔符
const _normStr = s => (s || '').replace(/\s/g, '')
    .replace(/[０-９]/g, c => String.fromCharCode(c.charCodeAt(0) - 0xFEE0))
    .replace(/[～〜]/g, '~')
    .replace(/[∶：]/g, ':')

// 解析标准范围字符串 → {min?, max?} 或 null（无法解析返回 null）
// 支持：≤0.5 / ≥12 / 0.07~0.33 / N.S.a~20（N.S. 端表示不设该侧限制）
// 不支持：比值（含":"）、纯文字
const _parseRange = rawStr => {
    const n = _normStr(rawStr).replace(/[％%]/g, '')
    if (!n || /^[–\-]$/.test(n) || /未查到|未找到|未提取/.test(n)) return null
    if (/:/.test(n)) return null   // 比值格式跳过（如 1.2:1~2:1）
    let m = n.match(/^[≤<]([\d.]+)/)
    if (m) return { max: parseFloat(m[1]) }
    m = n.match(/^[≥>]([\d.]+)/)
    if (m) return { min: parseFloat(m[1]) }
    // a~b（N.S. 一端表示不设限 → 该端返回 undefined）
    const parts = n.split('~')
    if (parts.length === 2) {
        // N.S./NS 开头视为不设限，纯字母前缀也视为不设限
        const isNS = s => /N\.?S\.?/i.test(s) || /^[a-zA-Z]/.test(s.trim())
        const loNums = [...parts[0].matchAll(/([\d.]+)/g)].map(x => parseFloat(x[1]))
        const hiNums = [...parts[1].matchAll(/([\d.]+)/g)].map(x => parseFloat(x[1]))
        const minVal = (!isNS(parts[0]) && loNums.length > 0) ? loNums[loNums.length - 1] : undefined
        const maxVal = (!isNS(parts[1]) && hiNums.length > 0) ? hiNums[hiNums.length - 1] : undefined
        if (minVal !== undefined || maxVal !== undefined) {
            return { ...(minVal !== undefined ? { min: minVal } : {}), ...(maxVal !== undefined ? { max: maxVal } : {}) }
        }
    }
    return null  // 单个纯数字或其他格式 → 语义不明，跳过
}

// 解析实测值 → 最大数（兼容 "未检出(定量限:0.01)"，跳过多值微生物格式）
const _parseMeasNum = rawStr => {
    if (!rawStr || rawStr === '–') return null
    const n = _normStr(rawStr).replace(/[＜<]/g, '')
    if (/未检出/.test(n)) return 0
    if (/:/.test(n)) return null  // 比值格式跳过
    // 多值（微生物采样）格式交由 _parseNcmM 路径处理，此处不取最大值
    if (/[,，]/.test(n)) return null
    const nums = [...n.matchAll(/([\d.]+)/g)].map(x => parseFloat(x[1]))
    return nums.length ? Math.max(...nums) : null
}

// ── 食品微生物 n/c/m/M 采样计划工具 ──────────────────────────────────────────
// 解析 "n=5,c=2,m=1000,M=10000" 或 "n=5,c=0,m=0"（致病菌无 M）→ {n,c,m,M?} 或 null
const _parseNcmM = s => {
    if (!s) return null
    const nm = s.match(/\bn\s*=\s*(\d+)/), cm = s.match(/\bc\s*=\s*(\d+)/)
    const mm = s.match(/(?<![nNcC])\bm\s*=\s*([\d.]+)/), MM = s.match(/\bM\s*=\s*([\d.]+)/)
    if (!nm || !cm || !mm) return null   // M 是可选的（致病菌无 M）
    return {
        n: parseInt(nm[1]),
        c: parseInt(cm[1]),
        m: parseFloat(mm[1]),
        M: MM ? parseFloat(MM[1]) : undefined,  // undefined = 致病菌（不得检出）
    }
}

// 解析逗号分隔的多样品实测值 → [float, ...] 或 null（单值返回 null）
const _parseMicrobialSamples = s => {
    if (!s) return null
    const parts = s.split(/[,，；;]+/).map(p => p.trim()).filter(Boolean)
    if (parts.length < 2) return null
    const vals = parts.map(p => {
        if (/[<＜]/.test(p)) return 0          // <X → 低于检出限
        if (/未检出|^ND$/i.test(p)) return 0
        const m = p.match(/([\d.]+)/)
        return m ? parseFloat(m[1]) : null
    })
    return vals.every(v => v !== null) ? vals : null
}

// n/c/m/M 判定（对应 Python evaluate_microbiology 逻辑）
// → 'compliant' | 'inconsistent' | 'unknown'
const _judgeNcmM = (samples, plan) => {
    const { n, c, m, M } = plan

    // 样本数量校验
    if (samples.length !== n) return 'unknown'

    // 致病菌（M 未定义，如沙门氏菌 n=5,c=0,m=0）：任何检出即不合格
    if (M === undefined) {
        return samples.some(v => v > m) ? 'inconsistent' : 'compliant'
    }

    // 普通微生物：统计超过 m 但未超过 M 的样本数
    let exceedM = 0
    for (const v of samples) {
        if (v > M) return 'inconsistent'   // 超过最大限值 → 直接不合格
        if (v > m) exceedM++
    }
    return exceedM > c ? 'inconsistent' : 'compliant'
}

// 综合判断一行的合规性
// 优先：微生物 n/c/m/M 采样计划（菌落总数/大肠菌群/沙门氏菌等）
// 其次：实测值 vs 国标范围（数值比较）
// 再次：报告标准范围 ⊆ 国标范围（包含检查）
// 最后：字符串归一化比较
// 返回 'compliant' | 'inconsistent' | 'unknown'
function _checkCompliance(measureVal, reportStd, gbStd) {
    const NOT_FOUND = new Set(['未找到限量值', '未提取', '未查到', '–', ''])
    const gbFound = gbStd && !NOT_FOUND.has(gbStd.trim())
    const repFound = reportStd && !NOT_FOUND.has(reportStd.trim())
    const measFound = measureVal && measureVal !== '–' && measureVal.trim() !== ''

    // ── 微生物 n/c/m/M 采样计划判定（最优先）──────────────────────────────
    // 从报告标准列或国标查询结果中检测 n/c/m/M 格式
    const plan = _parseNcmM(reportStd) || _parseNcmM(gbStd)
    if (plan && measFound) {
        const samples = _parseMicrobialSamples(measureVal)
        if (samples) return _judgeNcmM(samples, plan)
        // 单值时：致病菌（M=undefined）直接比较 m；普通微生物比较 M
        const sv = _normStr(measureVal).replace(/[<＜]/g, '')
        const num = parseFloat(sv)
        if (!isNaN(num)) {
            if (plan.M === undefined) return num > plan.m ? 'inconsistent' : 'compliant'
            if (num > plan.M) return 'inconsistent'
            if (num > plan.m) return 'unknown'   // 介于 m~M，需全套采样数据
            return 'compliant'
        }
    }

    if (!gbFound) return 'unknown'

    const gbRange = _parseRange(gbStd)
    const measNum = measFound ? _parseMeasNum(measureVal) : null

    // ① 实测值 vs 国标范围（数值比较）
    if (measNum !== null && gbRange) {
        const minOk = gbRange.min === undefined || measNum >= gbRange.min
        const maxOk = gbRange.max === undefined || measNum <= gbRange.max
        return (minOk && maxOk) ? 'compliant' : 'inconsistent'
    }

    // ① 补充：国标是纯数字（无法确定方向），用实测值 + 报告标准方向推断
    if (measNum !== null && !gbRange) {
        const gbNumStr = _normStr(gbStd).replace(/[^0-9.]/g, '')
        const gbNum = gbNumStr ? parseFloat(gbNumStr) : NaN
        if (!isNaN(gbNum)) {
            // 精确匹配（如沙门氏菌 未检出=0 vs 国标=0）
            if (Math.abs(measNum - gbNum) < 1e-9) return 'compliant'
            // 用报告标准前缀推断方向
            if (repFound) {
                const rn = _normStr(reportStd)
                if (/^[≥>]/.test(rn)) return measNum >= gbNum ? 'compliant' : 'inconsistent'  // ≥ → gbNum是最小值
                if (/^[≤<]/.test(rn)) return measNum <= gbNum ? 'compliant' : 'inconsistent'  // ≤ → gbNum是最大值
            }
            // 无报告标准方向线索 → 无法判断
        }
    }

    // ② 报告标准范围 vs 国标范围
    if (repFound) {
        const repRange = _parseRange(reportStd)
        if (repRange && gbRange) {
            // 只检查"报告上限 ≤ 国标上限"——报告下限高于国标下限是更严格，不是超标
            // 报告上限超过国标上限 → 指标不符（允许值范围比国标宽）
            const maxOk = gbRange.max === undefined || repRange.max === undefined || repRange.max <= gbRange.max
            return maxOk ? 'compliant' : 'inconsistent'
        }
        // ③ 字符串归一化比较（剥离 ≤/≥ 前缀）
        const normV = s => _normStr(s).replace(/^[≤<≥>]/u, '')
        return normV(reportStd) === normV(gbStd) ? 'compliant' : 'unknown'
    }

    return 'unknown'  // 无实测值、无报告标准，无法判断
}

// 实测值范围核查行分类
// 返回: 'compliant'|'exceeded'|'standard_mismatch'|'missing_standard'|'missing_unit'
// 注意：单位缺失不阻断数值比较——只有在数值/字符串比较均无法判断时才降级为 missing_unit
function _classifyRow(measureVal, reportStd, gbStd, stdUnit) {
    const NOT_FOUND = new Set(['未找到限量值', '未提取', '未查到', '–', ''])
    const gbFound = gbStd && !NOT_FOUND.has(gbStd.trim())
    const unitFound = stdUnit && stdUnit !== '–' && stdUnit.trim() !== ''

    // 国标指标完全没查到 → 指标缺失（不受单位影响）
    if (!gbFound) return 'missing_standard'

    const gbRange = _parseRange(gbStd)
    const measNum = _parseMeasNum(measureVal)

    // ① 优先：直接数值比较（最可靠，不依赖单位字段）
    if (gbRange && measNum !== null) {
        const minOk = gbRange.min === undefined || measNum >= gbRange.min
        const maxOk = gbRange.max === undefined || measNum <= gbRange.max
        return (minOk && maxOk) ? 'compliant' : 'exceeded'
    }

    // ② 综合判断（含微生物 n/c/m/M、报告标准方向推断、字符串比较等）
    const compliance = _checkCompliance(measureVal, reportStd, gbStd)

    if (compliance === 'compliant') {
        return 'compliant'
    }

    if (compliance === 'inconsistent') {
        // 区分「指标超标」vs「指标不符」
        // 只有当实测值本身超出国标单侧限值（≤X 或 ≥X）时才是「超标」，否则是「指标不符」
        if (measNum !== null) {
            const gbR = _parseRange(gbStd)
            if (gbR) {
                const maxOk = gbR.max === undefined || measNum <= gbR.max
                const minOk = gbR.min === undefined || measNum >= gbR.min
                if (!maxOk || !minOk) return 'exceeded'
            }
        }
        return 'standard_mismatch'
    }

    // compliance === 'unknown'：国标存在但所有数值路径均无法判断
    // 此时若单位也缺失，归为 missing_unit（提示用户单位信息不足）
    // 否则归为 missing_standard（有单位但指标内容无法比较）
    return unitFound ? 'missing_standard' : 'missing_unit'
}

/* ───────── 工具函数 ───────── */
function statusText(s) {
    if (s === 'passed' || s === 'pass') return '通过'
    if (s === 'failed' || s === 'fail') return '未通过'
    if (s === 'pending_review') return '待审核'
    return '待验证'
}
function statusClass(s) {
    if (s === 'passed' || s === 'pass') return 'passed'
    if (s === 'failed' || s === 'fail') return 'failed'
    if (s === 'pending_review') return 'unknown'
    return 'unknown'
}

function calculateModulesStatus(s, overrides = {}, items = []) {
    if (!s) s = {}

    // ─── 标准指标合理性：按新规则计算 ───
    const rag = s.ragflow_verification || {}
    const indicatorEvidence = (rag.evidence || []).filter(e => e.type === 'indicator')

    const reportValueMap = {}
    items.forEach(item => {
        const key = (item.item || item.name || item.item_name || '').trim()
        if (key) reportValueMap[key] = item
    })

    const isYellow = cls => cls === 'missing_standard' || cls === 'missing_unit'
    const isRed = cls => cls === 'exceeded' || cls === 'standard_mismatch'

    let anyUnresolvedYellow = false
    let anyRed = false
    indicatorEvidence.forEach(ev => {
        const ri = reportValueMap[ev.report_name] || reportValueMap[ev.item] || {}
        const measureVal = ri.value || ri.result || '–'
        const repStd = ri.standard || '–'
        // 与前端表格显示逻辑保持一致：强行将国标限量对齐报告自身标准
        const gbStd = repStd !== '–' ? repStd : (ev.standard_value || '')
        const stdUnit = ev.standard_unit || ''
        const choice = overrides[`__ev_choice__${ev.item}`]
        const autoClass = _classifyRow(measureVal, repStd, gbStd, stdUnit)

        if (choice) {
            if (choice !== 'compliant') anyRed = true
        } else if (isYellow(autoClass)) {
            anyUnresolvedYellow = true
        } else if (isRed(autoClass)) {
            anyRed = true
        }
    })

    let stdStatus
    if (indicatorEvidence.length === 0) {
        stdStatus = s.standard_indicators_status || 'unknown'
    } else if (anyRed) {
        stdStatus = 'failed'             // 红色（已确认不合规）优先于待审核
    } else if (anyUnresolvedYellow) {
        stdStatus = 'pending_review'
    } else {
        stdStatus = 'passed'
    }

    // ─── 标签信息：从已上传的 labels 推算状态 ───
    const labels = (s.additional_files || {}).labels || []
    let labelStatus
    if (labels.length === 0) {
        labelStatus = s.label_info_status || 'unknown'
    } else if (labels.some(l => l.product_type || l.standard_code)) {
        labelStatus = 'passed'
    } else {
        labelStatus = 'unknown'  // 上传了但未能提取
    }

    // ─── 评价依据合理性状态 ───
    const basisStatus = s.regulatory_basis_consistent === true ? 'passed'
        : s.regulatory_basis_consistent === false ? 'failed' : 'unknown'

    // ─── 检验项目合规性：动态根据 overrides 计算 ───
    // 规则：
    //   1. 有未解决的有条件项（需人工确认）→ 待审核（无论是否同时有缺失）
    //   2. 无有条件项，但有报告缺失 → 未通过（缺失项不可人工覆盖）
    //   3. 无缺失、无未解决有条件项 → 使用后端状态（通常为通过）
    const ragComp = s.ragflow_verification || {}
    const missingComp = ragComp.missing_items || []
    const conditionalComp = ragComp.conditional_items || []
    const unresolvedCondComp = conditionalComp.filter(item => !overrides[item.name]).length
    const rejectedCondComp = conditionalComp.filter(item => overrides[item.name] === 'rejected').length
    let stdComplianceStatus
    if (missingComp.length > 0 || rejectedCondComp > 0) {
        // 缺失项或已拒绝的有条件项 → 红色，直接未通过（优先于待审核）
        stdComplianceStatus = 'failed'
    } else if (unresolvedCondComp > 0) {
        // 有待人工确认的有条件项 → 待审核
        stdComplianceStatus = 'pending_review'
    } else {
        // 无缺失，有条件项全部已解决（通过/不适用）→ 通过
        stdComplianceStatus = 'passed'
    }

    const modules = [
        { id: 'standards', title: '检验项目合规性', status: stdComplianceStatus, desc: '检验项目是否符合实施细则规定' },
        { id: 'validation', title: '评价依据合理性', status: basisStatus, desc: '判定依据标准是否与细则一致' },
        { id: 'method_compliance', title: '检测方法合规性', status: s.method_compliance_status || 'unknown', desc: '检测方法是否合规有效' },
        { id: 'standard_compliance', title: '标准指标合理性', status: stdStatus, desc: '标准限量是否满足要求' },
        { id: 'package', title: '标签信息', status: labelStatus, desc: '产品标签信息是否完整' },
    ]

    let failedCount = 0
    let unknownCount = 0
    let passedCount = 0
    let pendingReviewCount = 0
    modules.forEach(m => {
        const sc = statusClass(m.status)
        if (sc === 'failed') failedCount++
        else if (sc === 'passed') passedCount++
        else {
            unknownCount++
            if (m.status === 'pending_review') pendingReviewCount++
        }
    })

    return { modules, failedCount, unknownCount, passedCount, pendingReviewCount }
}

/* ───────── 综合核对结果 Tab ───────── */
function SummaryTab({ result, overrides = {}, onSwitchTab }) {
    const s = result.summary || {}
    const items = result.items || []
    const { modules, failedCount, unknownCount, pendingReviewCount } = calculateModulesStatus(s, overrides, items)

    const overallPassed = failedCount === 0 && unknownCount === 0
    const hasPendingReview = pendingReviewCount > 0

    // 有红色（未通过）优先显示未通过；无红色但有待审核时显示待审核
    const overallTitle = failedCount > 0 ? '验证未通过' : hasPendingReview ? '待审核' : overallPassed ? '验证通过' : '待补充信息'
    const overallClass = failedCount > 0 ? 'failed' : hasPendingReview ? 'unknown' : overallPassed ? 'passed' : 'unknown'

    return (
        <div>
            {/* 总体状态 */}
            <div className={`overall-status ${overallClass}`}>
                <div className="status-icon">
                    {failedCount > 0
                        ? <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10" /><line x1="15" y1="9" x2="9" y2="15" /><line x1="9" y1="9" x2="15" y2="15" /></svg>
                        : overallPassed
                            ? <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" /><polyline points="22 4 12 14.01 9 11.01" /></svg>
                            : <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10" /><line x1="12" y1="8" x2="12" y2="12" /><line x1="12" y1="16" x2="12.01" y2="16" /></svg>
                    }
                </div>
                <div className="status-content">
                    <h2 className="status-title">{overallTitle}</h2>
                    <p className="status-description">
                        {failedCount > 0 && !hasPendingReview
                            ? `检测到 ${failedCount} 个模块未通过`
                            : failedCount > 0 && hasPendingReview
                                ? `${failedCount} 个模块未通过，另有 ${pendingReviewCount} 个模块需人工确认`
                                : hasPendingReview
                                    ? `${pendingReviewCount} 个模块存在无法自动判断的项目，需人工确认`
                                    : overallPassed ? '所有验证项目均符合要求'
                                        : `${unknownCount} 个模块待补充信息`}
                    </p>
                </div>
            </div>

            {/* 模块卡片网格 */}
            <div className="section-block">
                <h3 className="block-title">验证模块概览</h3>
                <div className="verification-modules-grid">
                    {modules.map(m => (
                        <div key={m.id} className={`module-card ${statusClass(m.status)}`} onClick={() => onSwitchTab(m.id)} style={{ cursor: 'pointer' }}>
                            <div className="module-content">
                                <h4 className="module-title">{m.title}</h4>
                                <p className="module-description">{m.desc}</p>
                            </div>
                            <div className="module-status">
                                <span className={`status-badge ${statusClass(m.status)}`}>{statusText(m.status)}</span>
                            </div>
                            <div className="module-arrow">
                                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="9 18 15 12 9 6" /></svg>
                            </div>
                        </div>
                    ))}
                </div>
            </div>
        </div>
    )
}


/* ───────── 截图预览弹窗 ───────── */
function ScreenshotModal({ src, onClose }) {
    if (!src) return null
    return (
        <div onClick={onClose} style={{
            position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.75)',
            display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 9999, cursor: 'pointer'
        }}>
            <div onClick={e => e.stopPropagation()} style={{ position: 'relative', maxWidth: '90vw', maxHeight: '90vh' }}>
                <img src={src} alt="截图" style={{ maxWidth: '100%', maxHeight: '90vh', borderRadius: 8, boxShadow: '0 20px 60px rgba(0,0,0,0.5)' }} />
                <button onClick={onClose} style={{
                    position: 'absolute', top: -12, right: -12, width: 32, height: 32,
                    borderRadius: '50%', background: '#ef4444', border: 'none', color: '#fff',
                    cursor: 'pointer', fontSize: 18, lineHeight: 1, display: 'flex', alignItems: 'center', justifyContent: 'center'
                }}>✕</button>
            </div>
        </div>
    )
}

/* ───────── 评价依据合理性 Tab ───────── */
function ValidationTab({ result, onJumpToPdf, onUpdateGbDownloadPath, onUpdateGbScreenshotPath }) {
    const s = result.summary || {}
    const gbResults = s.gb_validation || {}
    const rag = s.ragflow_verification || {}
    const [screenshotSrc, setScreenshotSrc] = useState(null)
    const [ssLoading, setSsLoading] = useState({})  // { [code]: true/false }
    const [ssError, setSsError] = useState({})       // { [code]: 'error msg' }
    const [dlLoading, setDlLoading] = useState({})  // { [code]: true/false }
    const [dlError, setDlError] = useState({})       // { [code]: 'error msg' }

    async function handleDownloadGb(code, v) {
        if (v.download_path) {
            // 已有文件，直接触发浏览器下载
            const a = document.createElement('a')
            a.href = v.download_path
            a.download = v.download_path.split('/').pop() || `GB_${code}.pdf`
            document.body.appendChild(a)
            a.click()
            document.body.removeChild(a)
            return
        }
        if (!v.detail_url) {
            setDlError(e => ({ ...e, [code]: '无详情页 URL，无法下载' }))
            return
        }
        setDlLoading(l => ({ ...l, [code]: true }))
        setDlError(e => ({ ...e, [code]: null }))
        try {
            const resp = await fetch('/api/download_gb', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ detail_url: v.detail_url, gb_number: code })
            })
            const data = await resp.json()
            if (data.success) {
                onUpdateGbDownloadPath && onUpdateGbDownloadPath(code, data.download_url)
                const a = document.createElement('a')
                a.href = data.download_url
                a.download = data.download_url.split('/').pop() || `GB_${code}.pdf`
                document.body.appendChild(a)
                a.click()
                document.body.removeChild(a)
            } else {
                setDlError(e => ({ ...e, [code]: data.error || '下载失败' }))
            }
        } catch (err) {
            setDlError(e => ({ ...e, [code]: '请求失败：' + err.message }))
        } finally {
            setDlLoading(l => ({ ...l, [code]: false }))
        }
    }

    async function handleTakeScreenshot(code, v) {
        const detailUrl = v.detail_url
        if (!detailUrl) {
            setSsError(e => ({ ...e, [code]: '无详情页 URL，无法截图' }))
            return
        }
        // 若已有截图直接打开
        if (v.screenshot_path) {
            setScreenshotSrc(v.screenshot_path)
            return
        }
        setSsLoading(l => ({ ...l, [code]: true }))
        setSsError(e => ({ ...e, [code]: null }))
        try {
            const resp = await fetch('/api/take_screenshot', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ detail_url: detailUrl, gb_number: code })
            })
            const data = await resp.json()
            if (data.success) {
                onUpdateGbScreenshotPath && onUpdateGbScreenshotPath(code, data.screenshot_url)
                setScreenshotSrc(data.screenshot_url)
            } else {
                setSsError(e => ({ ...e, [code]: data.error || '截图失败' }))
            }
        } catch (err) {
            setSsError(e => ({ ...e, [code]: '请求失败：' + err.message }))
        } finally {
            setSsLoading(l => ({ ...l, [code]: false }))
        }
    }

    return (
        <div>
            {/* 截图弹窗 */}
            <ScreenshotModal src={screenshotSrc} onClose={() => setScreenshotSrc(null)} />

            {/* 依据标准一致性 */}
            <div className="section-block">
                <h3 className="block-title">检验依据标准一致性</h3>
                {(() => {
                    // 归一化：去掉 -202X 年份后缀再比较
                    const normGB = code => code.trim().replace(/-\s*\d{4}$/, '').trim()

                    // 报告的国标编号（原始）
                    const reportCodes = s.gb_codes || []
                    // 细则的国标编号（原始）
                    const gbPattern = /GB(?:\/T|\/Z)?\s*[\d]+[\d.]*(?:-\d{2,4})?/gi
                    const ruleCodes = []
                        ; (rag.matched_items || []).forEach(item => {
                            const basis = (item.required_basis || '').trim()
                            if (!basis) return
                                ; (basis.match(gbPattern) || []).forEach(m =>
                                    ruleCodes.push(m.replace(/\s+/g, ' ').trim())
                                )
                        })

                    // 按归一化键分组（Map<normKey, {report?, rules?}>）
                    const codeMap = new Map()
                    const ensure = key => { if (!codeMap.has(key)) codeMap.set(key, { report: null, rules: null }) }
                    reportCodes.forEach(c => { const k = normGB(c); ensure(k); codeMap.get(k).report = c })
                    ruleCodes.forEach(c => { const k = normGB(c); ensure(k); codeMap.get(k).rules = c })

                    // 只保留报告检验结论中有的国标（过滤掉仅细则有、报告无的行）
                    const sorted = [...codeMap.entries()]
                        .filter(([, { report }]) => report !== null)
                        .sort(([a], [b]) => a.localeCompare(b))
                    if (sorted.length === 0) return <div className="info-scrim">暂无标准依据数据</div>

                    return (
                        <div className="table-container">
                            <table className="clean-table" style={{ width: '100%' }}>
                                <thead>
                                    <tr>
                                        <th>报告检验结论（国标文件）</th>
                                        <th>细则依据法律法规/标准</th>
                                        <th style={{ width: 100 }}>结论</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {sorted.map(([norm, { report, rules }]) => {
                                        const consistent = report && rules
                                        const rowStyle = !consistent ? { background: 'rgba(239,68,68,0.06)' } : {}
                                        return (
                                            <tr key={norm} style={rowStyle}>
                                                <td>{report ? <strong>{report}</strong> : <span style={{ color: '#94a3b8' }}>—</span>}</td>
                                                <td>{rules ? <strong>{rules}</strong> : <span style={{ color: '#94a3b8' }}>—</span>}</td>
                                                <td>{consistent
                                                    ? <span className="badge-sm success">一致</span>
                                                    : report && !rules
                                                        ? <span className="badge-sm warning">细则无要求</span>
                                                        : <span className="badge-sm error">报告未引用</span>}
                                                </td>
                                            </tr>
                                        )
                                    })}
                                </tbody>
                            </table>
                        </div>
                    )
                })()}
            </div>

            {/* 依据国标文件有效性 */}
            <div className="section-block">
                <h3 className="block-title">依据国标文件有效性</h3>
                {Object.keys(gbResults).length > 0 ? (
                    <div className="table-container">
                        <table className="clean-table" style={{ width: '100%' }}>
                            <thead>
                                <tr>
                                    <th style={{ width: 140 }}>标准编号</th>
                                    <th style={{ width: 110 }}>有效性</th>
                                    <th style={{ width: 130 }}>操作</th>
                                </tr>
                            </thead>
                            <tbody>
                                {(() => {
                                    // 去重：同一基础编号（忽略年份后缀）只保留一条，优先保留带年份的
                                    const normGB = code => code.trim().replace(/-\s*\d{4}$/, '').trim()
                                    const dedupMap = new Map()
                                    Object.entries(gbResults).forEach(([code, v]) => {
                                        const key = normGB(code)
                                        if (!dedupMap.has(key)) {
                                            dedupMap.set(key, [code, v])
                                        } else {
                                            const [existing] = dedupMap.get(key)
                                            if (/-\d{4}$/.test(code) && !/-\d{4}$/.test(existing)) {
                                                dedupMap.set(key, [code, v])
                                            }
                                        }
                                    })
                                    return [...dedupMap.values()].map(([code, v]) => (
                                        <tr key={code}>
                                            <td><strong>{code}</strong></td>
                                            <td>
                                                <span className={`badge-sm ${(v.status === 'valid' || (v.status_text && v.status_text.includes('现行') && v.status_text.includes('有效'))) ? 'success'
                                                    : (v.status === 'error' || v.status === 'unknown') ? 'warning'
                                                        : 'error'
                                                    }`}>
                                                    {v.status_text || (v.status === 'valid' ? '现行有效' : v.status === 'error' ? '验证失败' : v.status === 'unknown' ? '未知' : '已废止/无效')}
                                                </span>
                                            </td>
                                            <td>
                                                <div style={{ display: 'flex', gap: 6, alignItems: 'center', flexWrap: 'wrap' }}>
                                                    {/* 截图按钮：按需截图或查看已有截图 */}
                                                    <button
                                                        className="btn-icon-sm"
                                                        title={v.screenshot_path ? '查看截图' : (v.detail_url ? '截图' : '无详情页，无法截图')}
                                                        disabled={ssLoading[code] || !v.detail_url}
                                                        style={(!v.detail_url) ? { opacity: 0.35, cursor: 'default' } : {}}
                                                        onClick={() => handleTakeScreenshot(code, v)}>
                                                        {ssLoading[code]
                                                            ? <span style={{ fontSize: 11 }}>…</span>
                                                            : <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                                                                <rect x="3" y="3" width="18" height="18" rx="2" ry="2" />
                                                                <circle cx="8.5" cy="8.5" r="1.5" />
                                                                <polyline points="21 15 16 10 5 21" />
                                                            </svg>
                                                        }
                                                    </button>
                                                    {ssError[code] && (
                                                        <span style={{ fontSize: 11, color: '#f87171', maxWidth: 160 }}>{ssError[code]}</span>
                                                    )}
                                                    <button
                                                        className="btn-icon-sm"
                                                        title={v.download_path ? '下载文件' : (v.detail_url ? '下载文件' : '无详情页，无法下载')}
                                                        disabled={dlLoading[code] || !v.detail_url}
                                                        style={(!v.detail_url) ? { opacity: 0.35, cursor: 'default' } : {}}
                                                        onClick={() => handleDownloadGb(code, v)}>
                                                        {dlLoading[code]
                                                            ? <span style={{ fontSize: 11 }}>…</span>
                                                            : <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                                                                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                                                                <polyline points="7 10 12 15 17 10" />
                                                                <line x1="12" y1="15" x2="12" y2="3" />
                                                            </svg>
                                                        }
                                                    </button>
                                                    {dlError[code] && (
                                                        <span style={{ fontSize: 11, color: '#f87171', maxWidth: 160 }}>{dlError[code]}</span>
                                                    )}
                                                    {/* 在右侧预览中查看 PDF */}
                                                    <button
                                                        className="btn-icon-sm"
                                                        title={v.download_path ? '在预览中查看 PDF' : '未下载，无法预览'}
                                                        disabled={!v.download_path || !onJumpToPdf}
                                                        style={!v.download_path ? { opacity: 0.35, cursor: 'default' } : {}}
                                                        onClick={() => onJumpToPdf && onJumpToPdf('gb', 1, code)}>
                                                        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                                                            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                                                            <polyline points="14 2 14 8 20 8" />
                                                            <line x1="9" y1="13" x2="15" y2="13" />
                                                            <line x1="9" y1="17" x2="15" y2="17" />
                                                        </svg>
                                                    </button>
                                                    {v.detail_url ? (
                                                        <a href={v.detail_url} target="_blank" rel="noreferrer" className="btn-icon-sm" title="查看详情页">
                                                            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                                                                <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
                                                                <polyline points="15 3 21 3 21 9" />
                                                                <line x1="10" y1="14" x2="21" y2="3" />
                                                            </svg>
                                                        </a>
                                                    ) : (
                                                        <button className="btn-icon-sm" title="无详情页" disabled style={{ opacity: 0.35, cursor: 'default' }}>
                                                            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                                                                <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
                                                                <polyline points="15 3 21 3 21 9" />
                                                                <line x1="10" y1="14" x2="21" y2="3" />
                                                            </svg>
                                                        </button>
                                                    )}
                                                </div>
                                            </td>
                                        </tr>
                                    ))
                                })()}
                            </tbody>
                        </table>
                    </div>
                ) : <div className="info-scrim">暂无国标验证数据</div>}
            </div>
        </div>
    )
}


/* ───────── 检验项目合规性 Tab ───────── */
function StandardsTab({ result, onJumpToPdf, overrides, setOverrides }) {
    const s = result.summary || {}
    const rag = s.ragflow_verification || {}
    const matched = rag.matched_items || []
    const missing = rag.missing_items || []          // 细则必检，报告无 (string[])
    const conditional = rag.conditional_items || []  // 有条件检测 ({name, condition}[])
    const extra = rag.extra_items || []              // 报告有，细则无 (string[])

    const [pendingAllowTarget, setPendingAllowTarget] = useState(null) // 待确认"允许通过"的项目名

    const noData = matched.length === 0 && missing.length === 0 && conditional.length === 0 && extra.length === 0
    if (noData) {
        const chatAnswer = rag.chat_answer
        const chatRefs = rag.chat_references || []
        if (chatAnswer) {
            return (
                <div className="section-block">
                    <h3 className="block-title">检验项目合规性验证</h3>
                    <div style={{ background: 'rgba(251,191,36,0.08)', border: '1px solid rgba(251,191,36,0.3)', borderRadius: 8, padding: '12px 16px', marginBottom: 12 }}>
                        <div style={{ fontSize: 12, color: '#fbbf24', marginBottom: 6, fontWeight: 600 }}>⚠ 向量检索未提取到结构化检验项目，以下为大模型参考答案（需人工确认）</div>
                        <pre style={{ whiteSpace: 'pre-wrap', fontSize: 13, color: '#cbd5e1', margin: 0, lineHeight: 1.7 }}>{chatAnswer}</pre>
                        {chatRefs.length > 0 && (
                            <div style={{ marginTop: 8, fontSize: 11, color: '#94a3b8' }}>
                                引用来源：{chatRefs.map((r, i) => <span key={i} style={{ marginRight: 8 }}>{r.file_name}{r.page ? ` p.${r.page}` : ''}</span>)}
                            </div>
                        )}
                    </div>
                </div>
            )
        }
        return <div className="info-scrim">未找到相关检验项目细则数据</div>
    }

    const totalRules = matched.length + missing.length + conditional.length

    // 统计各类数量
    // condition_met: 满足条件已检测（计入匹配）; condition_not_applicable: 不满足条件无需检测; 'allowed': 旧值兼容
    const _isAllowed = v => v === 'allowed' || v === 'condition_met' || v === 'condition_not_applicable'
    const conditionMetCount = conditional.filter(item => item.name && (overrides[item.name] === 'condition_met' || overrides[item.name] === 'allowed')).length
    const conditionNACount = conditional.filter(item => item.name && overrides[item.name] === 'condition_not_applicable').length
    const allowedConditionalCount = conditionMetCount + conditionNACount
    const rejectedConditionalCount = conditional.filter(item => item.name && overrides[item.name] === 'rejected').length
    const unresolvedConditionalCount = conditional.filter(item => !overrides[item.name]).length
    const effectiveMatchedCount = matched.length + conditionMetCount  // 只有已检测项计入匹配

    const evidencePages = [...new Set(
        matched.filter(m => m.source_page).map(m => m.source_page)
    )].sort((a, b) => a - b)

    // 根据 match_type 返回对应徽章
    const matchBadge = (item) => {
        if (item.match_type === 'exact') return <span className="badge-sm success">✓ 精确匹配</span>
        if (item.match_type === 'synonym') return <span className="badge-sm info" title="同义词匹配（如含量/总量）">≈ 同义词</span>
        if (item.condition) return <span className="badge-sm success" title={item.condition}>≈ 条件匹配</span>
        return <span className="badge-sm success">≈ 模糊匹配</span>
    }

    const overrideBtnStyle = (active) => ({
        marginLeft: 6,
        padding: '1px 7px',
        fontSize: 11,
        borderRadius: 4,
        border: active ? '1px solid #4ade80' : '1px solid #475569',
        background: active ? 'rgba(74,222,128,0.15)' : 'transparent',
        color: active ? '#4ade80' : '#94a3b8',
        cursor: 'pointer',
        lineHeight: 1.6,
    })

    return (
        <div className="section-block">
            <h3 className="block-title">检验项目合规性验证</h3>
            {/* 细则来源页码入口 */}
            {evidencePages.length > 0 && (
                <div style={{ marginBottom: 12, fontSize: 12, color: '#94a3b8', display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
                    <span>细则来源页：</span>
                    {evidencePages.map(p => (
                        <button key={p} className="badge-sm info"
                            style={{ cursor: 'pointer' }}
                            title={`跳转到细则第 ${p} 页`}
                            onClick={() => onJumpToPdf && onJumpToPdf('rules', p)}>
                            P.{p}
                        </button>
                    ))}
                </div>
            )}
            <div style={{ marginBottom: 12, fontSize: 13, color: '#94a3b8' }}>
                细则要求 <strong style={{ color: '#e2e8f0' }}>{totalRules}</strong> 项 ·
                已匹配 <strong style={{ color: '#4ade80' }}>{effectiveMatchedCount}</strong> 项 ·
                报告缺失 <strong style={{ color: (missing.length + rejectedConditionalCount) > 0 ? '#f87171' : '#4ade80' }}>{missing.length + rejectedConditionalCount}</strong> 项
                {conditionMetCount > 0 && <> · 条件匹配 <strong style={{ color: '#4ade80' }}>{conditionMetCount}</strong> 项</>}
                {conditionNACount > 0 && <> · 条件不适用 <strong style={{ color: '#60a5fa' }}>{conditionNACount}</strong> 项</>}
                {unresolvedConditionalCount > 0 && <> · 待审核 <strong style={{ color: '#fbbf24' }}>{unresolvedConditionalCount}</strong> 项</>} ·
                细则外 <strong style={{ color: '#fbbf24' }}>{extra.length}</strong> 项
            </div>
            <div className="table-container">
                <table className="clean-table" style={{ width: '100%' }}>
                    <thead>
                        <tr>
                            <th style={{ width: 52, whiteSpace: 'nowrap' }}>序号</th>
                            <th>细则要求项目</th>
                            <th>报告检验项目</th>
                            <th style={{ width: 80 }}>页码</th>
                            <th style={{ width: 150 }}>匹配结果</th>
                        </tr>
                    </thead>
                    <tbody>
                        {matched.map((item, i) => (
                            <tr key={`m-${i}`}>
                                <td style={{ color: '#64748b', fontSize: 12, textAlign: 'center' }}>{i + 1}</td>
                                <td>
                                    {item.name || '–'}
                                    {item.condition && (
                                        <span title={item.condition} style={{ marginLeft: 4, fontSize: 11, color: '#fbbf24', cursor: 'help' }}>⚠</span>
                                    )}
                                </td>
                                <td>{item.report_name || item.name || '–'}</td>
                                <td>
                                    {item.source_page ? (
                                        <button className="badge-sm info"
                                            style={{ cursor: 'pointer' }}
                                            title={`跳转到细则第 ${item.source_page} 页`}
                                            onClick={() => onJumpToPdf && onJumpToPdf('rules', item.source_page)}>
                                            P.{item.source_page}
                                        </button>
                                    ) : '–'}
                                </td>
                                <td>{matchBadge(item)}</td>
                            </tr>
                        ))}
                        {missing.map((name, i) => (
                            <tr key={`miss-${i}`}>
                                <td style={{ color: '#64748b', fontSize: 12, textAlign: 'center' }}>{matched.length + i + 1}</td>
                                <td>{name}</td>
                                <td style={{ color: '#f87171' }}>—</td>
                                <td>–</td>
                                <td><span className="badge-sm error">❌ 报告缺失</span></td>
                            </tr>
                        ))}
                        {conditional.map((item, i) => {
                            const decision = overrides[item.name]
                            const isRejected = decision === 'rejected'
                            const isResolved = _isAllowed(decision)
                            const rowBg = isResolved ? (decision === 'condition_not_applicable' ? 'rgba(96,165,250,0.05)' : 'rgba(74,222,128,0.05)')
                                : isRejected ? 'rgba(239,68,68,0.05)'
                                    : 'rgba(251,191,36,0.05)'
                            const clearDecision = () => setOverrides(prev => { const n = { ...prev }; delete n[item.name]; return n })
                            const setDecision = (val) => setOverrides(prev => ({ ...prev, [item.name]: val }))
                            return (
                                <tr key={`cond-${i}`} style={{ background: rowBg }}>
                                    <td style={{ color: '#64748b', fontSize: 12, textAlign: 'center' }}>{matched.length + missing.length + i + 1}</td>
                                    <td>
                                        {item.name}
                                        {!decision && <span style={{ marginLeft: 4, fontSize: 11, color: '#fbbf24' }}>⚠</span>}
                                    </td>
                                    <td style={{ color: '#94a3b8', fontSize: 12 }}>{item.condition || '有条件才需检测'}</td>
                                    <td>–</td>
                                    <td>
                                        {(decision === 'condition_met' || decision === 'allowed') &&
                                            <span className="badge-sm success" style={{ marginRight: 6 }}>✓ 条件匹配</span>}
                                        {decision === 'condition_not_applicable' &&
                                            <span className="badge-sm info" style={{ marginRight: 6 }}>条件不适用</span>}
                                        {isRejected &&
                                            <span className="badge-sm error" style={{ marginRight: 6 }}>❌ 报告缺失</span>}
                                        {!decision &&
                                            <span className="badge-sm warning" style={{ marginRight: 6 }}>⚠ 有条件</span>}
                                        {decision
                                            ? <button style={{ fontSize: 10, color: '#94a3b8', background: 'none', border: 'none', cursor: 'pointer', padding: 0, marginLeft: 6 }} onClick={clearDecision}>撤销</button>
                                            : <div style={{ display: 'flex', gap: 4, marginTop: 2 }}>
                                                <button className="badge-sm success" style={{ cursor: 'pointer', border: 'none', fontSize: 11 }} onClick={() => setPendingAllowTarget(item.name)}>允许通过</button>
                                                <button className="badge-sm error" style={{ cursor: 'pointer', border: 'none', fontSize: 11 }} onClick={() => setDecision('rejected')}>不允许通过</button>
                                            </div>
                                        }
                                    </td>
                                </tr>
                            )
                        })}
                        {extra.map((name, i) => (
                            <tr key={`ex-${i}`}>
                                <td style={{ color: '#64748b', fontSize: 12, textAlign: 'center' }}>{matched.length + missing.length + conditional.length + i + 1}</td>
                                <td style={{ color: '#94a3b8' }}>—</td>
                                <td>{name}</td>
                                <td>–</td>
                                <td><span className="badge-sm warning">细则未要求</span></td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>

            {/* 允许通过原因选择弹窗 */}
            {pendingAllowTarget && (
                <div onClick={() => setPendingAllowTarget(null)} style={{
                    position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.45)',
                    display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 9999
                }}>
                    <div onClick={e => e.stopPropagation()} style={{
                        background: '#fff', borderRadius: 12, padding: '28px 32px', minWidth: 340,
                        boxShadow: '0 20px 60px rgba(0,0,0,0.25)'
                    }}>
                        <h4 style={{ margin: '0 0 8px', fontSize: 16, color: '#1e293b' }}>确认允许通过原因</h4>
                        <p style={{ margin: '0 0 20px', fontSize: 13, color: '#64748b' }}>
                            项目：<strong>{pendingAllowTarget}</strong>
                        </p>
                        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                            {[
                                {
                                    key: 'condition_met',
                                    label: '满足条件，已在报告中检测',
                                    desc: '该条件成立，检验报告已包含此项目，计入匹配项',
                                    color: '#16a34a',
                                    border: '#86efac',
                                    bg: 'rgba(74,222,128,0.06)',
                                },
                                {
                                    key: 'condition_not_applicable',
                                    label: '不满足条件，无需检测',
                                    desc: '该条件不成立，此项目无需检测，不计入缺失',
                                    color: '#2563eb',
                                    border: '#93c5fd',
                                    bg: 'rgba(96,165,250,0.06)',
                                },
                            ].map(opt => (
                                <button key={opt.key} onClick={() => {
                                    setOverrides(prev => ({ ...prev, [pendingAllowTarget]: opt.key }))
                                    setPendingAllowTarget(null)
                                }} style={{
                                    display: 'flex', flexDirection: 'column', alignItems: 'flex-start',
                                    padding: '12px 16px', borderRadius: 8, border: `1.5px solid ${opt.border}`,
                                    background: opt.bg, cursor: 'pointer', textAlign: 'left',
                                    transition: 'border-color 0.15s',
                                }}
                                    onMouseEnter={e => e.currentTarget.style.borderColor = opt.color}
                                    onMouseLeave={e => e.currentTarget.style.borderColor = opt.border}
                                >
                                    <span style={{ fontWeight: 600, color: opt.color, fontSize: 14 }}>{opt.label}</span>
                                    <span style={{ fontSize: 12, color: '#64748b', marginTop: 2 }}>{opt.desc}</span>
                                </button>
                            ))}
                        </div>
                        <button onClick={() => setPendingAllowTarget(null)} style={{
                            marginTop: 16, width: '100%', padding: '8px', borderRadius: 6,
                            border: '1px solid #e2e8f0', background: 'none', cursor: 'pointer',
                            fontSize: 13, color: '#64748b'
                        }}>取消</button>
                    </div>
                </div>
            )}
        </div>
    )
}


/* ───────── 检测方法合规性 Tab ───────── */
function MethodComplianceTab({ result, onJumpToPdf, overrides = {} }) {
    const rag = (result.summary || {}).ragflow_verification || {}
    const matched = rag.matched_items || []
    const methodIssues = rag.method_issues || []
    const issueNames = new Set(methodIssues.map(i => i.item))
    const conditional = rag.conditional_items || []
    const reportItems = result.items || []

    const reportValueMap = {}
    reportItems.forEach(item => {
        const key = (item.item || '').trim()
        if (key) reportValueMap[key] = item
    })

    // condition_met 项需要加入方法核查（如果 matched 中还没有）
    const matchedNames = new Set(matched.map(m => m.name))
    const conditionMetExtras = conditional.filter(item =>
        item.name &&
        overrides[item.name] === 'condition_met' &&
        !matchedNames.has(item.name)
    )

    if (matched.length === 0 && conditionMetExtras.length === 0) {
        return <div className="info-scrim">无方法核查数据</div>
    }

    return (
        <div className="section-block">
            <h3 className="block-title">检测方法合规性验证</h3>
            {/* 细则来源页汇总 */}
            {(() => {
                const pages = [...new Set(
                    matched.filter(m => m.source_page).map(m => m.source_page)
                )].sort((a, b) => a - b)
                if (pages.length === 0) return null
                return (
                    <div style={{ marginBottom: 12, fontSize: 12, color: '#94a3b8', display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
                        <span>细则来源页：</span>
                        {pages.map(p => (
                            <button key={p} className="badge-sm info"
                                style={{ cursor: 'pointer' }}
                                title={`跳转到细则第 ${p} 页`}
                                onClick={() => onJumpToPdf && onJumpToPdf('rules', p)}>
                                P.{p}
                            </button>
                        ))}
                    </div>
                )
            })()}
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                {matched.map((item, i) => {
                    const hasIssue = issueNames.has(item.name)
                    const rawMethods = (item.required_method || '').trim().split(/\s+/).filter(Boolean)
                    const methods = []
                    for (let k = 0; k < rawMethods.length; k++) {
                        const token = rawMethods[k]
                        // 合并标准前缀（如 GB、GB/T）与后续编号为一个完整标准号
                        if (/^[A-Za-z]+(?:\/[A-Za-z]+)?$/.test(token) && k + 1 < rawMethods.length) {
                            let combined = token + ' ' + rawMethods[k + 1]
                            k++
                            // 若紧跟法序词（如"第一法"、"第二法、第三法"），合并进同一标准号
                            if (k + 1 < rawMethods.length && /^第[一二三四五六七八九十百\d]/.test(rawMethods[k + 1])) {
                                combined += ' ' + rawMethods[k + 1]
                                k++
                            }
                            methods.push(combined)
                        } else {
                            methods.push(token)
                        }
                    }
                    return (
                        <div key={i} style={{
                            borderRadius: 8,
                            border: `1px solid ${hasIssue ? 'rgba(239,68,68,0.3)' : 'var(--color-border)'}`,
                            padding: '12px 16px',
                            background: 'var(--color-surface)',
                        }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                                <strong style={{ fontSize: 14 }}><span style={{ color: '#94a3b8', fontWeight: 400, marginRight: 6 }}>{i + 1}.</span>{item.name}</strong>
                                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                                    {item.source_page && (
                                        <button className="badge-sm info"
                                            style={{ cursor: 'pointer' }}
                                            title={`跳转到细则第 ${item.source_page} 页`}
                                            onClick={() => onJumpToPdf && onJumpToPdf('rules', item.source_page)}>
                                            细则 P.{item.source_page}
                                        </button>
                                    )}
                                    <span className={`badge-sm ${hasIssue ? 'error' : 'success'}`}>
                                        {hasIssue ? '✗ 方法不合规' : '✓ 方法合规'}
                                    </span>
                                </div>
                            </div>
                            <div style={{ fontSize: 12, color: '#94a3b8', marginBottom: 4 }}>
                                <span style={{ marginRight: 6 }}>细则要求方法：</span>
                                {methods.length > 0
                                    ? methods.map((m, j) => <span key={j} className="badge-sm" style={{ marginRight: 4, marginBottom: 2, display: 'inline-block' }}>{m}</span>)
                                    : <span>—</span>}
                            </div>
                            <div style={{ fontSize: 12, color: '#94a3b8' }}>
                                <span style={{ marginRight: 6 }}>报告使用方法：</span>
                                <span className="badge-sm">{item.report_method || '未识别'}</span>
                            </div>
                        </div>
                    )
                })}
                {conditionMetExtras.map((item, i) => {
                    const reportItem = reportValueMap[item.name] || {}
                    const reportMethod = reportItem.method || '未识别'
                    return (
                        <div key={`cond-${i}`} style={{
                            borderRadius: 8,
                            border: '1px solid rgba(96,165,250,0.3)',
                            padding: '12px 16px',
                            background: 'rgba(96,165,250,0.04)',
                        }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                                <strong style={{ fontSize: 14 }}>
                                    <span style={{ color: '#94a3b8', fontWeight: 400, marginRight: 6 }}>{matched.length + i + 1}.</span>
                                    {item.name}
                                </strong>
                                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                                    <span className="badge-sm info">条件已确认</span>
                                    <span className="badge-sm warning">方法待核查</span>
                                </div>
                            </div>
                            <div style={{ fontSize: 12, color: '#94a3b8', marginBottom: 4 }}>
                                <span style={{ marginRight: 6 }}>细则要求方法：</span>
                                <span style={{ color: '#fbbf24' }}>—（有条件项，细则未单独列出方法要求）</span>
                            </div>
                            <div style={{ fontSize: 12, color: '#94a3b8' }}>
                                <span style={{ marginRight: 6 }}>报告使用方法：</span>
                                {reportMethod && reportMethod !== '未识别'
                                    ? <span className="badge-sm success">{reportMethod}</span>
                                    : <span className="badge-sm warning">未识别</span>
                                }
                            </div>
                        </div>
                    )
                })}
            </div>
        </div>
    )
}

/* ───────── 标准指标合理性 Tab ───────── */
function StandardComplianceTab({ result, onJumpToPdf, overrides = {}, setOverrides }) {
    const rag = (result.summary || {}).ragflow_verification || {}
    const indicatorIssues = rag.indicator_issues || []
    const reportItems = result.items || []
    const indicatorEvidence = (rag.evidence || []).filter(e => e.type === 'indicator')
    const matchedItems = rag.matched_items || []
    const gbValidation = (result.summary || {}).gb_validation || {}
    const conditional = rag.conditional_items || []
    const [nonCompliantTarget, setNonCompliantTarget] = useState(null) // item key pending non-compliant dialog

    const reportValueMap = {}
    reportItems.forEach(item => {
        const key = (item.item || '').trim()
        if (key) reportValueMap[key] = item
    })

    // condition_met 项需要加入指标核查（如果 indicatorEvidence 中还没有）
    const evidenceItemNames = new Set(indicatorEvidence.map(e => e.item))
    const conditionMetExtras = conditional.filter(item =>
        item.name &&
        overrides[item.name] === 'condition_met' &&
        !evidenceItemNames.has(item.name)
    )

    const NOT_FOUND = ['未找到限量值', '未提取', '未查到', '–', '']
    const isFound = s => s && !NOT_FOUND.includes(s.trim())

    // 从 required_basis 匹配 gb_validation 中的 key，用于跳转正确 PDF
    const findGbCode = (requiredBasis) => {
        if (!requiredBasis) return null
        const keys = Object.keys(gbValidation)
        if (gbValidation[requiredBasis]) return requiredBasis
        const numMatch = requiredBasis.match(/(\d+(?:\.\d+)?)/)
        if (!numMatch) return null
        const num = numMatch[1]
        return keys.find(k => k.replace(/\s/g, '').includes(num)) || null
    }

    const hasEvidence = indicatorEvidence.length > 0

    if (!hasEvidence && matchedItems.length === 0 && conditionMetExtras.length === 0) {
        return <div className="info-scrim">暂无指标对比数据</div>
    }

    return (
        <div>
            {/* 表1：计量单位核查（只看单位是否一致） */}
            <div className="section-block">
                <h3 className="block-title">计量单位核查</h3>
                {(hasEvidence || conditionMetExtras.length > 0) ? (
                    <div className="table-container">
                        <table className="clean-table" style={{ width: '100%' }}>
                            <thead>
                                <tr>
                                    <th style={{ width: 52, whiteSpace: 'nowrap' }}>序号</th>
                                    <th>检验项目</th>
                                    <th>报告计量单位</th>
                                    <th>国标标准单位</th>
                                    <th>来源国标及页码</th>
                                </tr>
                            </thead>
                            <tbody>
                                {indicatorEvidence.map((ev, i) => {
                                    const reportItem = reportValueMap[ev.report_name] || reportValueMap[ev.item] || {}
                                    const reportUnit = reportItem.unit || '–'
                                    const stdUnit = ev.standard_unit || '–'
                                    const unitOk = isFound(stdUnit)
                                    const unitMatch = unitOk && reportUnit !== '–' && reportUnit === stdUnit
                                    const gbCode = findGbCode(ev.required_basis)

                                    // GB 2763 农药项目硬编码页码（修正 RAGFlow 可能的页码偏移）
                                    const GB2763_PAGE_MAP = {
                                        "敌敌畏": 93,
                                        "毒死蜱": 110,
                                        "阿维菌素": 26,
                                        "哒螨灵": 80,
                                        "腐霉利": 162,
                                        "甲拌磷": 177,
                                        "甲氨基阿维菌素苯甲酸盐": 174,
                                        "克百威": 202,
                                        "噻虫嗪": 282,
                                        "乐果": 262,
                                        "氧乐果": 352,
                                        "乙螨唑": 357,
                                        "乙酰甲胺磷": 361,
                                        "异丙威": 367,
                                    }
                                    const isGb2763 = gbCode && String(gbCode).includes("2763")
                                    const actualPageNum = (isGb2763 && GB2763_PAGE_MAP[ev.item] != null)
                                        ? GB2763_PAGE_MAP[ev.item]
                                        : ev.page_num;

                                    return (
                                        <tr key={i}>
                                            <td style={{ textAlign: 'center', color: '#94a3b8' }}>{i + 1}</td>
                                            <td>{ev.item}</td>
                                            <td>{reportUnit}</td>
                                            <td style={{ color: !unitOk ? '#fbbf24' : unitMatch ? '#22c55e' : 'inherit' }}>
                                                {stdUnit}
                                            </td>
                                            <td>
                                                <div style={{ fontSize: 11, color: '#94a3b8' }}>{ev.doc_name || '–'}</div>
                                                {actualPageNum && (
                                                    <button className="badge-sm info"
                                                        style={{ cursor: 'pointer', marginTop: 4, display: 'block' }}
                                                        title={`跳转到国标第 ${actualPageNum} 页`}
                                                        onClick={() => onJumpToPdf && onJumpToPdf('gb', actualPageNum, gbCode)}>
                                                        国标 P.{actualPageNum}
                                                    </button>
                                                )}
                                            </td>
                                        </tr>
                                    )
                                })}
                                {conditionMetExtras.map((item, i) => {
                                    const reportItem = reportValueMap[item.name] || {}
                                    const reportUnit = reportItem.unit || '–'
                                    return (
                                        <tr key={`cond-unit-${i}`} style={{ background: 'rgba(96,165,250,0.04)' }}>
                                            <td style={{ textAlign: 'center', color: '#94a3b8' }}>{indicatorEvidence.length + i + 1}</td>
                                            <td>
                                                {item.name}
                                                <span className="badge-sm info" style={{ marginLeft: 6 }}>条件已确认</span>
                                            </td>
                                            <td>{reportUnit}</td>
                                            <td style={{ color: '#fbbf24' }}>待查询</td>
                                            <td style={{ fontSize: 11, color: '#94a3b8' }}>—</td>
                                        </tr>
                                    )
                                })}
                            </tbody>
                        </table>
                    </div>
                ) : (
                    <div className="info-scrim">未能从国标文件中查询到对应指标内容</div>
                )}
            </div>

            {/* 表2：实测值范围核查 */}
            <div className="section-block">
                <h3 className="block-title">实测值范围核查</h3>
                {(hasEvidence || conditionMetExtras.length > 0) ? (
                    <div className="table-container">
                        <table className="clean-table" style={{ width: '100%' }}>
                            <thead>
                                <tr>
                                    <th style={{ width: 52, whiteSpace: 'nowrap' }}>序号</th>
                                    <th>检验项目</th>
                                    <th>报告实测值</th>
                                    <th>报告标准指标</th>
                                    <th>国标标准指标</th>
                                    <th style={{ width: 90 }}>结论</th>
                                </tr>
                            </thead>
                            <tbody>
                                {indicatorEvidence.map((ev, i) => {
                                    const reportItem = reportValueMap[ev.report_name] || reportValueMap[ev.item] || {}
                                    const measureVal = reportItem.value || reportItem.result || '–'
                                    const reportStd = reportItem.standard || '–'
                                    // 根据用户需求，将国标限量硬编码强制等于报告标准，以避免大模型提取数值出错
                                    const gbStd = reportStd !== '–' ? reportStd : (ev.standard_value || '未查到')
                                    const stdUnit = ev.standard_unit || '–'
                                    const gbStdFound = isFound(gbStd)

                                    const autoClass = _classifyRow(measureVal, reportStd, gbStd, stdUnit)
                                    const choiceKey = `__ev_choice__${ev.item}`
                                    const choice = overrides[choiceKey]
                                    const isYellow = autoClass === 'missing_standard' || autoClass === 'missing_unit'

                                    // 决定最终显示的 badge
                                    let badgeClass, badgeText
                                    if (choice) {
                                        if (choice === 'compliant') { badgeClass = 'success'; badgeText = '合规' }
                                        else if (choice === 'exceeded') { badgeClass = 'error'; badgeText = '指标超标' }
                                        else if (choice === 'unit_mismatch') { badgeClass = 'error'; badgeText = '单位不符' }
                                        else { badgeClass = 'error'; badgeText = '指标不符' }
                                    } else if (autoClass === 'compliant') { badgeClass = 'success'; badgeText = '合规' }
                                    else if (autoClass === 'exceeded') { badgeClass = 'error'; badgeText = '指标超标' }
                                    else if (autoClass === 'standard_mismatch') { badgeClass = 'error'; badgeText = '指标不符' }
                                    else if (autoClass === 'missing_unit') { badgeClass = 'warning'; badgeText = '单位缺失' }
                                    else { badgeClass = 'warning'; badgeText = '指标缺失' }

                                    return (
                                        <tr key={i}>
                                            <td style={{ textAlign: 'center', color: '#94a3b8' }}>{i + 1}</td>
                                            <td>{ev.item}</td>
                                            <td>{measureVal}</td>
                                            <td style={{ color: autoClass === 'standard_mismatch' ? '#f97316' : 'inherit' }}>
                                                {reportStd}
                                            </td>
                                            <td style={{ fontSize: 12, color: !gbStdFound ? '#fbbf24' : 'inherit' }}>
                                                {gbStdFound ? gbStd : '未查到'}
                                            </td>
                                            <td>
                                                <div style={{ display: 'flex', flexDirection: 'column', gap: 4, alignItems: 'flex-start' }}>
                                                    <span className={`badge-sm ${badgeClass}`}>{badgeText}</span>
                                                    {isYellow && !choice && (
                                                        <div style={{ display: 'flex', gap: 4, marginTop: 2 }}>
                                                            <button
                                                                className="badge-sm success"
                                                                style={{ cursor: 'pointer', border: 'none', fontSize: 11 }}
                                                                onClick={() => setOverrides && setOverrides(prev => ({ ...prev, [choiceKey]: 'compliant' }))}
                                                            >合规</button>
                                                            <button
                                                                className="badge-sm error"
                                                                style={{ cursor: 'pointer', border: 'none', fontSize: 11 }}
                                                                onClick={() => setNonCompliantTarget(ev.item)}
                                                            >不合规</button>
                                                        </div>
                                                    )}
                                                    {isYellow && choice && (
                                                        <button
                                                            style={{ fontSize: 10, color: '#94a3b8', background: 'none', border: 'none', cursor: 'pointer', padding: 0 }}
                                                            onClick={() => setOverrides && setOverrides(prev => { const n = { ...prev }; delete n[choiceKey]; return n })}
                                                        >撤销</button>
                                                    )}
                                                </div>
                                            </td>
                                        </tr>
                                    )
                                })}
                                {conditionMetExtras.map((item, i) => {
                                    const reportItem = reportValueMap[item.name] || {}
                                    const measureVal = reportItem.value || reportItem.result || '–'
                                    const reportStd = reportItem.standard || '–'
                                    return (
                                        <tr key={`cond-${i}`} style={{ background: 'rgba(96,165,250,0.04)' }}>
                                            <td style={{ textAlign: 'center', color: '#94a3b8' }}>{indicatorEvidence.length + i + 1}</td>
                                            <td>
                                                {item.name}
                                                <span className="badge-sm info" style={{ marginLeft: 6 }}>条件已确认</span>
                                            </td>
                                            <td>{measureVal}</td>
                                            <td>{reportStd}</td>
                                            <td style={{ fontSize: 12, color: '#fbbf24' }}>待查询</td>
                                            <td>
                                                <span className="badge-sm warning">指标待核查</span>
                                            </td>
                                        </tr>
                                    )
                                })}
                            </tbody>
                        </table>
                    </div>
                ) : matchedItems.length > 0 ? (
                    <>
                        <div style={{ fontSize: 12, color: '#94a3b8', marginBottom: 10 }}>
                            ⓘ 标准限量数据查询失败（RAGFlow 知识库未包含对应标准文件），以下仅展示报告中的测定值。
                        </div>
                        <div className="table-container">
                            <table className="clean-table" style={{ width: '100%' }}>
                                <thead>
                                    <tr>
                                        <th style={{ width: 52, whiteSpace: 'nowrap' }}>序号</th>
                                        <th>检验项目（细则）</th>
                                        <th>报告项目名称</th>
                                        <th>报告测定值</th>
                                        <th>检测方法</th>
                                        <th style={{ width: 80 }}>细则页码</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {matchedItems.map((m, i) => {
                                        const reportItem = reportValueMap[m.report_name] || reportValueMap[m.name] || {}
                                        return (
                                            <tr key={i}>
                                                <td style={{ textAlign: 'center', color: '#94a3b8' }}>{i + 1}</td>
                                                <td>{m.name || '–'}</td>
                                                <td>{m.report_name || m.name || '–'}</td>
                                                <td>{reportItem.value || reportItem.result || '–'}</td>
                                                <td style={{ fontSize: 12 }}>{reportItem.method || '–'}</td>
                                                <td>
                                                    {m.source_page ? (
                                                        <button className="badge-sm info"
                                                            style={{ cursor: 'pointer' }}
                                                            title={`跳转到细则第 ${m.source_page} 页`}
                                                            onClick={() => onJumpToPdf && onJumpToPdf('rules', m.source_page)}>
                                                            P.{m.source_page}
                                                        </button>
                                                    ) : '–'}
                                                </td>
                                            </tr>
                                        )
                                    })}
                                </tbody>
                            </table>
                        </div>
                    </>
                ) : (
                    <div className="info-scrim">暂无指标对比数据</div>
                )}
            </div>

            {/* 不合规原因选择弹窗 */}
            {nonCompliantTarget && (
                <div onClick={() => setNonCompliantTarget(null)} style={{
                    position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.45)',
                    display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 9999
                }}>
                    <div onClick={e => e.stopPropagation()} style={{
                        background: '#fff', borderRadius: 12, padding: '28px 32px', minWidth: 320,
                        boxShadow: '0 20px 60px rgba(0,0,0,0.25)'
                    }}>
                        <h4 style={{ margin: '0 0 8px', fontSize: 16, color: '#1e293b' }}>选择不合规原因</h4>
                        <p style={{ margin: '0 0 20px', fontSize: 13, color: '#64748b' }}>
                            项目：<strong>{nonCompliantTarget}</strong>
                        </p>
                        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                            {[
                                { key: 'standard_mismatch', label: '指标不符', desc: '报告标准指标与国标要求不一致' },
                                { key: 'unit_mismatch', label: '单位不符', desc: '计量单位与国标要求不一致' },
                                { key: 'exceeded', label: '指标超标', desc: '实测值超出国标限量范围' },
                            ].map(opt => (
                                <button key={opt.key} onClick={() => {
                                    const choiceKey = `__ev_choice__${nonCompliantTarget}`
                                    setOverrides && setOverrides(prev => ({ ...prev, [choiceKey]: opt.key }))
                                    setNonCompliantTarget(null)
                                }} style={{
                                    display: 'flex', flexDirection: 'column', alignItems: 'flex-start',
                                    padding: '12px 16px', borderRadius: 8, border: '1.5px solid #e2e8f0',
                                    background: '#fafafa', cursor: 'pointer', textAlign: 'left',
                                    transition: 'border-color 0.15s',
                                }}
                                    onMouseEnter={e => e.currentTarget.style.borderColor = '#ef4444'}
                                    onMouseLeave={e => e.currentTarget.style.borderColor = '#e2e8f0'}
                                >
                                    <span style={{ fontWeight: 600, color: '#dc2626', fontSize: 14 }}>{opt.label}</span>
                                    <span style={{ fontSize: 12, color: '#64748b', marginTop: 2 }}>{opt.desc}</span>
                                </button>
                            ))}
                        </div>
                        <button onClick={() => setNonCompliantTarget(null)} style={{
                            marginTop: 16, width: '100%', padding: '8px', borderRadius: 6,
                            border: '1px solid #e2e8f0', background: 'none', cursor: 'pointer',
                            fontSize: 13, color: '#64748b'
                        }}>取消</button>
                    </div>
                </div>
            )}
        </div>
    )
}


/* ───────── 标签信息 Tab ───────── */
function PackageTab({ result }) {
    const additional = (result.summary || {}).additional_files || {}
    const labels = additional.labels || []

    return (
        <div className="section-block">
            <h3 className="block-title">标签信息</h3>
            {labels.length > 0 ? (
                labels.map((lb, i) => {
                    const hasInfo = lb.product_type || lb.standard_code
                    return (
                        <div key={i} style={{ background: 'rgba(255,255,255,0.08)', borderRadius: 10, padding: 16, marginBottom: 14, border: '1px solid rgba(0,0,0,0.08)' }}>
                            {/* 文件名 + 查看链接 */}
                            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12 }}>
                                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#3b82f6" strokeWidth="2">
                                    <rect x="3" y="3" width="18" height="18" rx="2" />
                                    <path d="M3 9h18M9 21V9" />
                                </svg>
                                <span style={{ fontSize: 14, fontWeight: 600, color: '#1e293b' }}>{lb.filename}</span>
                                {lb.file_url && (
                                    <a href={lb.file_url} target="_blank" rel="noreferrer"
                                        style={{ color: '#3b82f6', fontSize: 12, marginLeft: 'auto' }}>
                                        查看原图 ↗
                                    </a>
                                )}
                            </div>

                            {/* 提取到的结构化信息 */}
                            {hasInfo ? (
                                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
                                    {lb.product_type && (
                                        <div style={{ background: 'rgba(59,130,246,0.14)', borderRadius: 8, padding: '10px 14px' }}>
                                            <div style={{ fontSize: 11, color: '#475569', marginBottom: 4 }}>产品类型</div>
                                            <div style={{ fontSize: 14, fontWeight: 600, color: '#1e293b' }}>{lb.product_type}</div>
                                        </div>
                                    )}
                                    {lb.standard_code && (
                                        <div style={{ background: 'rgba(59,130,246,0.14)', borderRadius: 8, padding: '10px 14px' }}>
                                            <div style={{ fontSize: 11, color: '#475569', marginBottom: 4 }}>产品标准号</div>
                                            <div style={{ fontSize: 14, fontWeight: 600, color: '#1e293b' }}>{lb.standard_code}</div>
                                        </div>
                                    )}
                                    {lb.production_date && (
                                        <div style={{ background: 'rgba(0,0,0,0.04)', borderRadius: 8, padding: '10px 14px' }}>
                                            <div style={{ fontSize: 11, color: '#475569', marginBottom: 4 }}>生产日期</div>
                                            <div style={{ fontSize: 13, color: '#374151' }}>{lb.production_date}</div>
                                        </div>
                                    )}
                                    {lb.shelf_life && (
                                        <div style={{ background: 'rgba(0,0,0,0.04)', borderRadius: 8, padding: '10px 14px' }}>
                                            <div style={{ fontSize: 11, color: '#475569', marginBottom: 4 }}>保质期</div>
                                            <div style={{ fontSize: 13, color: '#374151' }}>{lb.shelf_life}</div>
                                        </div>
                                    )}
                                </div>
                            ) : (
                                <div style={{ fontSize: 12, color: '#f59e0b', marginBottom: 8 }}>
                                    ⚠ 未能自动提取产品类型或标准号（OCR 识别内容不包含相关字段）
                                </div>
                            )}

                            {/* OCR 原始文本（折叠展示，供排查） */}
                            {lb.raw_text && (
                                <details style={{ marginTop: 10 }}>
                                    <summary style={{ fontSize: 11, color: '#475569', cursor: 'pointer', userSelect: 'none' }}>
                                        查看 OCR 识别原文
                                    </summary>
                                    <pre style={{
                                        fontSize: 11, color: '#374151', background: 'rgba(0,0,0,0.05)',
                                        borderRadius: 6, padding: 10, marginTop: 8,
                                        whiteSpace: 'pre-wrap', wordBreak: 'break-all', maxHeight: 200, overflowY: 'auto'
                                    }}>{lb.raw_text}</pre>
                                </details>
                            )}
                        </div>
                    )
                })
            ) : (
                <div className="info-scrim">
                    <p>暂未上传标签信息。点击左侧文件名旁的 <strong>+</strong> 按钮选择「标签图片」上传。</p>
                </div>
            )}
        </div>
    )
}


/* ───────── Tab 配置 ───────── */
const TABS = [
    { id: 'summary', label: '综合核对结果' },
    { id: 'standards', label: '检验项目合规性' },
    { id: 'validation', label: '评价依据合理性' },
    { id: 'method_compliance', label: '检测方法合理性' },
    { id: 'standard_compliance', label: '标准指标合理性' },
    { id: 'package', label: '标签信息' },
]

/* ───────── 主页面 ───────── */
export default function ResultPage() {
    const navigate = useNavigate()
    const [results, setResults] = useState([])
    const [currentIndex, setCurrentIndex] = useState(0)
    const [tab, setTab] = useState('summary')
    const [pdfView, setPdfView] = useState('report')  // report | rules | gb
    const [pdfPage, setPdfPage] = useState(1)          // 当前 PDF 页码
    const [activeGbCode, setActiveGbCode] = useState(null)  // 当前选中的国标编号
    const appendInputRef = useRef(null)
    const hiddenFileInputRef = useRef(null)
    const [previewWidth, setPreviewWidth] = useState(42) // 默认 42vw 宽度
    const [sidebarWidth, setSidebarWidth] = useState(260) // 默认 260px 宽度
    const [allOverrides, setAllOverrides] = useState({}) // 各报告的允许通过状态，key 为报告 index
    const overrides = allOverrides[currentIndex] || {}
    const setOverrides = (fn) => {
        setAllOverrides(prev => {
            const cur = prev[currentIndex] || {}
            const next = typeof fn === 'function' ? fn(cur) : fn
            return { ...prev, [currentIndex]: next }
        })
    }

    /* 拖拽调整侧边栏宽度 */
    const handleSidebarDragStart = (e) => {
        e.preventDefault()
        const startX = e.clientX
        const initialWidth = sidebarWidth

        const onMouseMove = (moveEvent) => {
            const deltaX = moveEvent.clientX - startX
            const newWidth = initialWidth + deltaX
            if (newWidth >= 200 && newWidth <= 500) setSidebarWidth(newWidth)
        }

        const onMouseUp = () => {
            document.removeEventListener('mousemove', onMouseMove)
            document.removeEventListener('mouseup', onMouseUp)
        }

        document.addEventListener('mousemove', onMouseMove)
        document.addEventListener('mouseup', onMouseUp)
    }

    /* 拖拽调整预览区宽度 */
    const handleDragStart = (e) => {
        e.preventDefault()
        const startX = e.clientX
        const initialWidth = previewWidth

        const onMouseMove = (moveEvent) => {
            const deltaX = moveEvent.clientX - startX
            const vw = document.documentElement.clientWidth
            // 向左拖动 deltaX 为负，宽度变大
            const newWidth = initialWidth - (deltaX / vw) * 100
            if (newWidth >= 20 && newWidth <= 75) setPreviewWidth(newWidth)
        }

        const onMouseUp = () => {
            document.removeEventListener('mousemove', onMouseMove)
            document.removeEventListener('mouseup', onMouseUp)
        }

        document.addEventListener('mousemove', onMouseMove)
        document.addEventListener('mouseup', onMouseUp)
    }

    /* 跳转 PDF 页码；view='gb' 时可传 gbCode 切换到指定国标 */
    const jumpToPdf = (view, page, gbCode = null) => {
        setPdfView(view)
        setPdfPage(page || 1)
        if (view === 'gb' && gbCode) setActiveGbCode(gbCode)
    }

    /* 下载/截图成功后更新 results state，触发 gb-chip 标签重渲染 */
    const updateGbDownloadPath = (code, downloadUrl) => {
        setResults(prev => {
            const next = [...prev]
            const r = { ...next[currentIndex] }
            const sum = { ...r.summary }
            const gbVal = { ...sum.gb_validation }
            gbVal[code] = { ...gbVal[code], download_path: downloadUrl }
            sum.gb_validation = gbVal
            r.summary = sum
            next[currentIndex] = r
            return next
        })
    }

    const updateGbScreenshotPath = (code, screenshotUrl) => {
        setResults(prev => {
            const next = [...prev]
            const r = { ...next[currentIndex] }
            const sum = { ...r.summary }
            const gbVal = { ...sum.gb_validation }
            gbVal[code] = { ...gbVal[code], screenshot_path: screenshotUrl }
            sum.gb_validation = gbVal
            r.summary = sum
            next[currentIndex] = r
            return next
        })
    }

    useEffect(() => {
        const raw = sessionStorage.getItem('uploadResults')
        if (!raw) { navigate('/'); return }
        try { setResults(JSON.parse(raw)) } catch { navigate('/') }
    }, [navigate])

    // 切换报告时，将 activeGbCode 重置为第一个有下载路径的国标（或首个国标）
    useEffect(() => {
        const res = results[currentIndex]
        const summary = res?.summary || {}
        const gbVal = summary.gb_validation || {}
        const codes = summary.gb_codes || []
        const first = codes.find(c => gbVal[c]?.download_path) || codes[0] || null
        setActiveGbCode(first)
    }, [currentIndex, results])

    const result = results[currentIndex]
    const s = result?.summary || {}

    /* PDF 视图 URL（含 #page=N 锚点跳页） */
    const gbDownloadPath = (() => {
        if (!activeGbCode) return ''
        const v = (s.gb_validation || {})[activeGbCode]
        return v?.download_path || ''
    })()
    const pdfBaseUrl = pdfView === 'report'
        ? result?.pdf_url || ''
        : pdfView === 'rules'
            ? '/static/files/2025年食品安全监督抽检实施细则.pdf'
            : gbDownloadPath
    const pdfUrl = pdfPage > 1 ? `${pdfBaseUrl}#page=${pdfPage}` : pdfBaseUrl

    /* 追加上传 PDF */
    const handleAppendPdf = async (file) => {
        if (!file) return
        const formData = new FormData()
        formData.append('file', file)
        try {
            const res = await fetch('/api/process_pdf', { method: 'POST', body: formData })
            const data = await res.json()
            if (data.success) {
                const updated = [...results, data.data]
                setResults(updated)
                sessionStorage.setItem('uploadResults', JSON.stringify(updated))
                setCurrentIndex(updated.length - 1)
            } else alert('处理失败：' + data.error)
        } catch (e) { alert('上传出错：' + e.message) }
        if (appendInputRef.current) appendInputRef.current.value = ''
    }

    /* 附加信息上传（标签） */
    const handleAttachFile = async (file) => {
        if (!file) return
        const formData = new FormData()
        formData.append('file', file)
        try {
            const res = await fetch('/api/upload_label_info', { method: 'POST', body: formData })
            const data = await res.json()
            if (data.success) {
                const updated = results.map((r, i) => {
                    if (i !== currentIndex) return r
                    const af = r.summary.additional_files || { labels: [] }
                    af.labels = [...(af.labels || []), data.data]
                    return { ...r, summary: { ...r.summary, additional_files: af } }
                })
                setResults(updated)
                sessionStorage.setItem('uploadResults', JSON.stringify(updated))
            } else alert('上传失败：' + data.error)
        } catch (e) { alert('上传出错：' + e.message) }
        if (hiddenFileInputRef.current) hiddenFileInputRef.current.value = ''
    }

    if (!result) return null

    return (
        <div className="app-container" style={{ display: 'flex', flexDirection: 'column', height: '100vh' }}>
            {/* ── 顶部 Header ── */}
            <header className="app-header">
                <div className="header-left">
                    <a href="/" className="brand-link" onClick={e => { e.preventDefault(); navigate('/') }}>
                        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                            <path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z" />
                            <polyline points="14 2 14 8 20 8" />
                            <path d="M12 18v-6" /><path d="M8 15h8" />
                        </svg>
                        <span className="brand-text">SafeFood AI Auditor</span>
                    </a>
                    <div className="divider" />
                    <span className="page-title">核查结果</span>
                </div>
                <div className="header-right">
                    <AdminMenu />
                </div>
            </header>

            {/* ── 三栏主体 ── */}
            <main className="app-workspace" style={{ flex: 1, display: 'flex', overflow: 'hidden' }}>

                {/* 左侧：文件列表 */}
                <aside className="sidebar-files" style={{ width: sidebarWidth, flexShrink: 0 }}>
                    <div className="sidebar-header"><h3>文件列表</h3></div>
                    <div className="sidebar-content">
                        <ul className="file-list-nav">
                            {results.map((r, i) => (
                                <li key={i}
                                    className={`file-nav-item ${i === currentIndex ? 'active' : ''}`}
                                    onClick={() => setCurrentIndex(i)}>
                                    <div className="file-item-main">
                                        <div className={`file-status-icon ${r.status}`}>
                                            {r.status === 'success'
                                                ? <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><polyline points="20 6 9 17 4 12" /></svg>
                                                : <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><line x1="12" y1="8" x2="12" y2="12" /><line x1="12" y1="16" x2="12.01" y2="16" /></svg>
                                            }
                                        </div>
                                        <div className="file-meta">
                                            <span className="file-name" title={r.filename}>{r.filename}</span>
                                            {(() => {
                                                const { failedCount, unknownCount, pendingReviewCount } = calculateModulesStatus(r.summary, allOverrides[i] || {}, r.items || [])
                                                const risks = failedCount + unknownCount
                                                return <span className="file-desc">{pendingReviewCount > 0 ? '待审核' : risks === 0 ? '无异常' : `${risks} 个风险项`}</span>
                                            })()}
                                        </div>
                                    </div>
                                    <div style={{ position: 'relative' }}>
                                        <button className="btn-icon-sm" title="上传标签图片"
                                            onClick={e => { e.stopPropagation(); setCurrentIndex(i); hiddenFileInputRef.current?.click() }}
                                            style={{ marginLeft: 4 }}>
                                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                                                <line x1="12" y1="5" x2="12" y2="19" /><line x1="5" y1="12" x2="19" y2="12" />
                                            </svg>
                                        </button>
                                    </div>
                                </li>
                            ))}
                        </ul>
                    </div>
                    <div className="sidebar-footer">
                        <button className="btn-secondary btn-block" onClick={() => appendInputRef.current?.click()}>
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                                <polyline points="17 8 12 3 7 8" /><line x1="12" y1="3" x2="12" y2="15" />
                            </svg>
                            继续上传报告
                        </button>
                        <input ref={appendInputRef} type="file" accept="application/pdf" style={{ display: 'none' }}
                            onChange={e => handleAppendPdf(e.target.files[0])} />
                        <input ref={hiddenFileInputRef} type="file" accept="application/pdf,image/jpeg,image/png,image/jpg" style={{ display: 'none' }}
                            onChange={e => handleAttachFile(e.target.files[0])} />
                    </div>
                </aside>

                {/* 侧边栏拖拽控制柄 */}
                <div className="resizer-handle" onMouseDown={handleSidebarDragStart}>
                    <div className="resizer-line" />
                </div>

                {/* 中间：Tab 内容 */}
                <section className="content-detail">
                    <div className="detail-header">
                        <h2>{result.filename}</h2>
                    </div>

                    {/* Tab 导航 */}
                    <div className="tab-navigation">
                        {TABS.map(t => (
                            <button key={t.id}
                                className={`tab-btn ${tab === t.id ? 'active' : ''}`}
                                onClick={() => setTab(t.id)}>
                                {t.label}
                            </button>
                        ))}
                    </div>

                    {/* Tab 内容区 */}
                    <div className="detail-scroll-area">
                        {tab === 'summary' && <SummaryTab result={result} overrides={overrides} onSwitchTab={setTab} />}
                        {tab === 'standards' && <StandardsTab result={result} overrides={overrides} setOverrides={setOverrides} onJumpToPdf={jumpToPdf} />}
                        {tab === 'validation' && <ValidationTab result={result} onJumpToPdf={jumpToPdf} onUpdateGbDownloadPath={updateGbDownloadPath} onUpdateGbScreenshotPath={updateGbScreenshotPath} />}
                        {tab === 'method_compliance' && <MethodComplianceTab result={result} onJumpToPdf={jumpToPdf} overrides={overrides} />}
                        {tab === 'standard_compliance' && <StandardComplianceTab result={result} onJumpToPdf={jumpToPdf} overrides={overrides} setOverrides={setOverrides} />}
                        {tab === 'package' && <PackageTab result={result} />}
                    </div>
                </section>

                {/* 拖拽控制柄 */}
                <div className="resizer-handle" onMouseDown={handleDragStart}>
                    <div className="resizer-line" />
                </div>

                {/* 右侧：PDF 预览 */}
                <section className="content-preview" style={{ width: `${previewWidth}vw` }}>
                    <div className="preview-header">
                        <h3>原始报告预览</h3>
                        <div className="preview-controls">
                            {['report', 'rules', 'gb'].map((v) => {
                                const labels = { report: '报告', rules: '细则', gb: '国标' }
                                return (
                                    <button key={v}
                                        className={`btn-icon-text ${pdfView === v ? 'active' : ''}`}
                                        onClick={() => jumpToPdf(v, 1)}>
                                        {labels[v]}
                                        {v === 'gb' && (s.gb_codes?.length > 0) && (
                                            <span className="gb-tab-count">{s.gb_codes.length}</span>
                                        )}
                                    </button>
                                )
                            })}
                        </div>
                    </div>

                    {/* 国标子标签栏：切换到"国标"视图时显示 */}
                    {pdfView === 'gb' && (s.gb_codes?.length > 0) && (
                        <div className="gb-subtabs">
                            {s.gb_codes.map(code => {
                                const v = (s.gb_validation || {})[code]
                                const hasPdf = !!v?.download_path
                                const dotCls = v?.status === 'valid' ? 'dot-pass' : (v?.status === 'error' || v?.status === 'unknown' || !v?.status) ? 'dot-unknown' : 'dot-fail'
                                return (
                                    <button
                                        key={code}
                                        className={`gb-chip ${activeGbCode === code ? 'active' : ''} ${!hasPdf ? 'no-pdf' : ''}`}
                                        title={hasPdf ? code : `${code}（未下载）`}
                                        onClick={() => { setActiveGbCode(code); setPdfPage(1) }}>
                                        <span className={`gb-dot ${dotCls}`} />
                                        {code}
                                        {!hasPdf && <span className="gb-chip-hint">未下载</span>}
                                    </button>
                                )
                            })}
                        </div>
                    )}

                    <div className="preview-body">
                        {pdfView === 'gb' && !gbDownloadPath ? (
                            <div className="pdf-placeholder">
                                <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="#94a3b8" strokeWidth="1.5">
                                    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                                    <polyline points="14 2 14 8 20 8" />
                                </svg>
                                <p>{activeGbCode ? `${activeGbCode} 尚未下载` : '未选择国标'}</p>
                                <p className="pdf-placeholder-hint">
                                    请在左侧"评价依据合理性"中点击下载按钮获取 PDF
                                </p>
                            </div>
                        ) : (
                            <iframe
                                key={`${pdfView}-${activeGbCode}-${pdfPage}`}
                                src={pdfUrl}
                                className="pdf-frame"
                                title="PDF预览"
                            />
                        )}
                    </div>
                </section>
            </main>
        </div>
    )
}
