from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import re
from typing import Any, Optional


_DATE_FLEX_PATTERN = re.compile(r"^\s*(\d{4})\D(\d{1,2})\D(\d{1,2})\s*$")


def parse_flexible_date(s: str) -> date:
    """
    Accepts: YYYY-MM-DD, YYYY-M-D, YYYY/MM/DD, YYYY.M.D, etc.
    """
    if not isinstance(s, str) or not s.strip():
        raise ValueError("empty date string")
    m = _DATE_FLEX_PATTERN.match(s)
    if not m:
        raise ValueError(f"invalid date format: {s!r}")
    y, mo, d = (int(m.group(1)), int(m.group(2)), int(m.group(3)))
    return date(y, mo, d)


def _normalize_status(status: Optional[str]) -> Optional[str]:
    if not isinstance(status, str):
        return None
    return status.strip()


def is_currently_effective(status: Optional[str]) -> bool:
    """
    "现行有效" => True
    "已废止" => False
    Conservative fallback: unknown => False (forces user to inspect).
    """
    s = _normalize_status(status)
    if not s:
        return False
    if "废止" in s or "作废" in s or "停止" in s:
        return False
    if "现行" in s and "有效" in s:
        return True
    # Some sites might only show "有效"
    if s == "有效":
        return True
    return False


@dataclass(frozen=True)
class ValidationResult:
    passed: bool
    reasons: list[str]
    production_date: date
    implement_date: Optional[date]
    status: Optional[str]


def validate_standard_for_production_date(
    *,
    production_date: str | date,
    standard_info: dict[str, Any],
) -> ValidationResult:
    """
    校验逻辑（按你的描述顺序）：
      1) 标准状态是否现行有效
      2) 生产日期是否晚于(>=) 实施日期
    """
    if isinstance(production_date, date):
        prod_dt = production_date
    else:
        prod_dt = parse_flexible_date(production_date)

    status = (standard_info or {}).get("status")
    reasons: list[str] = []

    # 1) status
    if not is_currently_effective(status):
        reasons.append(f"标准状态不是现行有效（当前为：{status or '未知'}）")

    # 2) implement date
    impl_raw = (standard_info or {}).get("implement_date")
    impl_dt: Optional[date] = None
    if isinstance(impl_raw, str) and impl_raw.strip():
        try:
            impl_dt = parse_flexible_date(impl_raw)
        except ValueError:
            impl_dt = None
            reasons.append(f"实施日期无法解析（原值：{impl_raw}）")
    else:
        reasons.append("缺少实施日期（implement_date）")

    if impl_dt is not None and prod_dt < impl_dt:
        reasons.append(f"生产日期早于实施日期（生产日期：{prod_dt.isoformat()}，实施日期：{impl_dt.isoformat()}）")

    return ValidationResult(
        passed=(len(reasons) == 0),
        reasons=reasons,
        production_date=prod_dt,
        implement_date=impl_dt,
        status=_normalize_status(status),
    )


def format_user_friendly_report(
    *, 
    standard_info: dict[str, Any], 
    result: ValidationResult,
    screenshot_path: Optional[str] = None,
    download_path: Optional[str] = None
) -> str:
    """
    把校验结果 + 指定字段，以用户友好的形式打印。
    """
    gb_number = (standard_info or {}).get("gb_number")
    publish_date = (standard_info or {}).get("publish_date")
    implement_date = (standard_info or {}).get("implement_date")
    abolish_date = (standard_info or {}).get("abolish_date")
    status = (standard_info or {}).get("status")
    detail_url = (standard_info or {}).get("foodmate_detail_page_url")

    lines: list[str] = []
    lines.append(f"校验结论：{'通过' if result.passed else '不通过'}")
    lines.append(f"生产日期：{result.production_date.isoformat()}")
    if result.reasons:
        lines.append("不通过原因：")
        for i, r in enumerate(result.reasons, start=1):
            lines.append(f"  {i}. {r}")

    lines.append("")
    lines.append("标准信息（来源：standard_info.json）：")
    lines.append(f"  - 国标号：GB {gb_number}" if gb_number else "  - 国标号：未知")
    lines.append(f"  - 标准状态：{status or '未知'}")
    lines.append(f"  - 发布日期：{publish_date or '未知'}")
    lines.append(f"  - 实施日期：{implement_date or '未知'}")
    lines.append(f"  - 废止日期：{abolish_date or '未知/未提供'}")
    lines.append(f"  - 详情页：{detail_url or '未知'}")
    if screenshot_path:
        lines.append(f"  - 详情截图：{screenshot_path}")
    if download_path:
        lines.append(f"  - 标准文件：{download_path}")

    return "\n".join(lines)
