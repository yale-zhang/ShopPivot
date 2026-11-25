"""日报 Excel 渲染（openpyxl）。

导出必须带：口径版本、生成时间、run_id、已脱敏标记（表 3-18 / 设计文案「导出水印」）。
"""
from __future__ import annotations

from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from kernel.contexts.metric_data.domain.report import DailyReportView

_HEADER_FILL = PatternFill("solid", fgColor="E8EEF2")
_THIN = Side(style="thin", color="C9D2D8")
_BORDER = Border(left=_THIN, right=_THIN, top=_THIN, bottom=_THIN)


def render_daily_report(view: DailyReportView) -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "经营日报"

    sheet["A1"] = f"店枢 ShopPivot · 经营日报 · {view.watermark}"
    sheet["A1"].font = Font(bold=True, size=11)
    sheet.merge_cells("A1:J1")

    sheet["A2"] = (
        f"平台/店铺：{view.platform} / {view.shop_id}    "
        f"时间窗：{view.window.label}    取数通道：{view.channel.label}"
    )
    sheet["A2"].font = Font(size=9, color="555555")
    sheet.merge_cells("A2:J2")

    headers = ["平台 / 店铺", "统计日期"]
    for column in sorted(view.columns, key=lambda c: (c.display_order, c.key)):
        label = f"{column.label}（{column.unit}）" if column.unit else column.label
        if column.additivity.value != "ADDITIVE":
            label += " 不可加"
        headers.append(label)
    headers.extend(["口径版本", "生成时间", "run_id"])

    header_row = 4
    for index, label in enumerate(headers, start=1):
        cell = sheet.cell(row=header_row, column=index, value=label)
        cell.font = Font(bold=True, size=9)
        cell.fill = _HEADER_FILL
        cell.border = _BORDER
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

    columns = sorted(view.columns, key=lambda c: (c.display_order, c.key))
    if not view.rows:
        sheet.cell(row=header_row + 1, column=1, value="该时间窗暂无数据（非取数失败）")
        sheet.merge_cells(
            start_row=header_row + 1,
            start_column=1,
            end_row=header_row + 1,
            end_column=len(headers),
        )
    else:
        for offset, row in enumerate(view.rows, start=header_row + 1):
            values = [f"{view.platform} / {view.shop_id}", row.stat_date.isoformat()]
            for column in columns:
                cell = row.cells.get(column.key)
                values.append(cell.value if cell else "不适用")
            values.extend(
                [
                    view.metric_version,
                    view.generated_at.strftime("%Y-%m-%d %H:%M"),
                    view.run_id,
                ]
            )
            for index, value in enumerate(values, start=1):
                cell = sheet.cell(row=offset, column=index, value=value)
                cell.border = _BORDER
                cell.font = Font(size=9)
                cell.alignment = Alignment(horizontal="right" if index > 2 else "left")

    sheet.freeze_panes = f"A{header_row + 1}"
    sheet.column_dimensions["A"].width = 22
    sheet.column_dimensions["B"].width = 12
    for index in range(3, len(headers) + 1):
        sheet.column_dimensions[get_column_letter(index)].width = 15

    buffer = BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()
