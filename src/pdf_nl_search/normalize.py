ZERO_WIDTH = {"\u200b", "\u200c", "\u200d", "\ufeff", "\u2060"}
LIGATURES = {"ﬁ": "fi", "ﬂ": "fl", "ﬀ": "ff", "ﬃ": "ffi", "ﬄ": "ffl"}


def normalize_range(orig_text: str, start: int, end: int, line_ends: set) -> tuple[str, list[int]]:
    """对 [start,end) 原始片段归一化，返回 (归一化文本, norm->orig 映射)。"""
    norm: list[str] = []
    n2o: list[int] = []
    i = start
    while i < end:
        c = orig_text[i]
        # 规则4：行尾 '-' + 换行（英文断词；须前一字符非空白，区分破折号）
        if c == "-" and i in line_ends and (i == start or not orig_text[i - 1].isspace()):
            if i + 2 < end and orig_text[i + 1] == "\r" and orig_text[i + 2] == "\n":
                i += 3
                continue
            if i + 1 < end and orig_text[i + 1] == "\n":
                i += 2
                continue
        # 规则3：软连字符/零宽/CR
        if c in ZERO_WIDTH or c == "\u00ad" or c == "\r":
            i += 1
            continue
        # 规则2：ligature 展开
        if c in LIGATURES:
            for rc in LIGATURES[c]:
                norm.append(rc)
                n2o.append(i)
            i += 1
            continue
        # 规则6：全角折叠
        if c == "\u3000":
            c = " "
        elif 0xFF01 <= ord(c) <= 0xFF5E:
            c = chr(ord(c) - 0xFEE0)
        # 规则1：小写化
        if "A" <= c <= "Z":
            c = c.lower()
        # 规则5：空白折叠
        if c.isspace():
            if norm and norm[-1] == " ":
                i += 1
                continue
            norm.append(" ")
            n2o.append(i)
            i += 1
            continue
        norm.append(c)
        n2o.append(i)
        i += 1
    return "".join(norm), n2o
