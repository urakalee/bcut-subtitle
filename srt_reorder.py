#!/usr/bin/env python3
"""
SRT 字幕重排脚本
功能：
  1. 解析 SRT 文件
  2. 按时间戳排序
  3. 移除空白字幕条目
  4. 合并时间间隔极短的相邻同文条目（可选）
  5. 重新编号并输出
"""

import re
import argparse
from pathlib import Path
from dataclasses import dataclass, field


# ──────────────────────────────────────────────
# 数据结构
# ──────────────────────────────────────────────

@dataclass
class Subtitle:
    index: int
    start_ms: int       # 开始时间（毫秒）
    end_ms: int         # 结束时间（毫秒）
    lines: list[str] = field(default_factory=list)

    @property
    def text(self) -> str:
        return "\n".join(self.lines).strip()

    @property
    def is_empty(self) -> bool:
        return not self.text


# ──────────────────────────────────────────────
# 时间戳工具
# ──────────────────────────────────────────────

_TS_RE = re.compile(
    r"(\d{2}):(\d{2}):(\d{2})[,.](\d{3})"
)


def ts_to_ms(ts: str) -> int:
    """'HH:MM:SS,mmm' → 毫秒"""
    m = _TS_RE.match(ts.strip())
    if not m:
        raise ValueError(f"无法解析时间戳: {ts!r}")
    h, mi, s, ms = map(int, m.groups())
    return ((h * 60 + mi) * 60 + s) * 1000 + ms


def ms_to_ts(ms: int) -> str:
    """毫秒 → 'HH:MM:SS,mmm'"""
    ms = max(0, ms)
    h, rem = divmod(ms, 3_600_000)
    mi, rem = divmod(rem, 60_000)
    s, ms_ = divmod(rem, 1_000)
    return f"{h:02d}:{mi:02d}:{s:02d},{ms_:03d}"


_ARROW_RE = re.compile(r"--\s*>")


def parse_timestamp_line(line: str) -> tuple[int, int] | None:
    """解析 'HH:MM:SS,mmm --> HH:MM:SS,mmm'，失败返回 None"""
    parts = _ARROW_RE.split(line)
    if len(parts) != 2:
        return None
    try:
        return ts_to_ms(parts[0]), ts_to_ms(parts[1])
    except ValueError:
        return None


# ──────────────────────────────────────────────
# 解析
# ──────────────────────────────────────────────

def parse_srt(path: Path, encoding: str = "utf-8") -> list[Subtitle]:
    """解析 SRT 文件，返回 Subtitle 列表（保持原始顺序）"""
    try:
        text = path.read_text(encoding=encoding)
    except UnicodeDecodeError:
        text = path.read_text(encoding="utf-8-sig")

    # 统一换行符，按空行分块
    blocks = re.split(r"\n\s*\n", text.strip())
    subtitles: list[Subtitle] = []

    for block in blocks:
        raw_lines = [ln.rstrip() for ln in block.splitlines()]
        if not raw_lines:
            continue

        # 第一行：序号（允许不存在时跳过）
        idx = 0
        line_cursor = 0
        if raw_lines[0].strip().isdigit():
            idx = int(raw_lines[0].strip())
            line_cursor = 1

        if line_cursor >= len(raw_lines):
            continue

        # 时间戳行
        ts = parse_timestamp_line(raw_lines[line_cursor])
        if ts is None:
            # 尝试跳过序号重试
            for li, ln in enumerate(raw_lines[line_cursor:], start=line_cursor):
                ts = parse_timestamp_line(ln)
                if ts is not None:
                    line_cursor = li + 1
                    break
            else:
                continue  # 整块忽略
        else:
            line_cursor += 1

        content_lines = raw_lines[line_cursor:]
        subtitles.append(Subtitle(
            index=idx,
            start_ms=ts[0],
            end_ms=ts[1],
            lines=content_lines,
        ))

    return subtitles


# ──────────────────────────────────────────────
# 处理
# ──────────────────────────────────────────────

def clean_text(text: str) -> str:
    """去掉行首行尾多余的标点/空格"""
    lines = []
    for ln in text.splitlines():
        ln = ln.strip()
        # 去掉孤立的前导逗号/句号
        ln = re.sub(r"^[，。、]+\s*", "", ln)
        lines.append(ln)
    return "\n".join(lines).strip()


def reorder(
    subs: list[Subtitle],
    remove_empty: bool = True,
    merge_gap_ms: int = 0,
    clean: bool = True,
) -> list[Subtitle]:
    """
    排序 → 去空 → 清洗文本 → 合并极短间隔相邻重复条目 → 重编号
    merge_gap_ms: 相邻条目间隔 ≤ 该值（毫秒）且文本相同时合并，0 表示不合并
    """
    result = sorted(subs, key=lambda s: (s.start_ms, s.end_ms))

    if remove_empty:
        result = [s for s in result if not s.is_empty]

    if clean:
        for s in result:
            cleaned = clean_text(s.text)
            s.lines = cleaned.splitlines() if cleaned else []
        if remove_empty:
            result = [s for s in result if not s.is_empty]

    if merge_gap_ms > 0:
        merged: list[Subtitle] = []
        for s in result:
            if (
                merged
                and s.text == merged[-1].text
                and s.start_ms - merged[-1].end_ms <= merge_gap_ms
            ):
                merged[-1].end_ms = s.end_ms   # 延长上一条结束时间
            else:
                merged.append(s)
        result = merged

    # 重编号
    for i, s in enumerate(result, start=1):
        s.index = i

    return result


# ──────────────────────────────────────────────
# 输出
# ──────────────────────────────────────────────

def write_srt(subs: list[Subtitle], path: Path, encoding: str = "utf-8") -> None:
    lines: list[str] = []
    for s in subs:
        lines.append(str(s.index))
        lines.append(f"{ms_to_ts(s.start_ms)} --> {ms_to_ts(s.end_ms)}")
        lines.extend(s.lines)
        lines.append("")   # 空行分隔

    path.write_text("\n".join(lines) + "\n", encoding=encoding)


# ──────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="SRT 字幕重排：排序 / 去空 / 清洗 / 合并 / 重编号",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    p.add_argument("input", type=Path, help="输入 .srt 文件路径")
    p.add_argument(
        "-o", "--output", type=Path, default=None,
        help="输出路径（默认在原文件名后加 _reordered）",
    )
    p.add_argument(
        "--keep-empty", action="store_true",
        help="保留空文本条目（默认删除）",
    )
    p.add_argument(
        "--no-clean", action="store_true",
        help="不清洗文本（默认去掉行首孤立标点）",
    )
    p.add_argument(
        "--merge-gap", type=int, default=0, metavar="MS",
        help="合并间隔 ≤ MS 毫秒的相邻重复文本条目（默认 0 = 不合并）",
    )
    p.add_argument(
        "--encoding", default="utf-8",
        help="文件编码（默认 utf-8）",
    )
    p.add_argument(
        "--stats", action="store_true",
        help="处理完毕后打印统计信息",
    )
    return p


def main() -> None:
    args = build_parser().parse_args()
    src: Path = args.input.expanduser().resolve()

    if not src.exists():
        raise SystemExit(f"[错误] 文件不存在: {src}")
    if src.suffix.lower() != ".srt":
        print(f"[警告] 文件扩展名不是 .srt: {src.name}")

    dst: Path = args.output or src.with_stem(src.stem + "_reordered")
    dst = dst.expanduser().resolve()

    print(f"[解析] {src}")
    raw = parse_srt(src, encoding=args.encoding)
    print(f"  原始条目数: {len(raw)}")

    processed = reorder(
        raw,
        remove_empty=not args.keep_empty,
        merge_gap_ms=args.merge_gap,
        clean=not args.no_clean,
    )
    print(f"  处理后条目数: {len(processed)}")

    write_srt(processed, dst, encoding=args.encoding)
    print(f"[输出] {dst}")

    if args.stats:
        total_dur = sum(s.end_ms - s.start_ms for s in processed)
        h, rem = divmod(total_dur, 3_600_000)
        mi, rem = divmod(rem, 60_000)
        s_ = rem / 1000
        print(f"\n── 统计 ──")
        print(f"  字幕条数  : {len(processed)}")
        print(f"  总字幕时长: {h:02d}:{mi:02d}:{s_:05.2f}")
        first = processed[0] if processed else None
        last = processed[-1] if processed else None
        if first and last:
            print(f"  时间范围  : {ms_to_ts(first.start_ms)} → {ms_to_ts(last.end_ms)}")


if __name__ == "__main__":
    main()
