# apps/workflow/annotation/utils.py


def parse_time_str(time_str):
    # ... (保持不变) ...
    try:
        time_str = time_str.replace(",", ".")
        h, m, s = time_str.split(":")
        seconds = float(h) * 3600 + float(m) * 60 + float(s)
        return seconds
    except ValueError:
        return 0.0


def parse_srt_content(content):
    """
    解析 SRT 文本内容，返回字典列表
    [{'start': 1.0, 'end': 2.0, 'text': 'Hello', 'speaker': 'Unknown', 'original_text': 'Raw Line'}]
    """
    content = content.replace("\r\n", "\n").replace("\r", "\n")
    blocks = content.strip().split("\n\n")

    dialogues = []
    for block in blocks:
        lines = block.strip().split("\n")
        if len(lines) < 3:
            continue

        time_line_index = 0
        if "-->" in lines[1]:
            time_line_index = 1
        elif "-->" in lines[0]:
            time_line_index = 0
        else:
            continue

        time_line = lines[time_line_index]
        text_lines = lines[time_line_index + 1 :]

        try:
            start_str, end_str = time_line.split(" --> ")
            start = parse_time_str(start_str.strip())
            end = parse_time_str(end_str.strip())

            # 获取完整文本
            full_text = "\n".join(text_lines)

            # 分离角色与内容
            speaker = "Unknown"
            text = full_text
            if ":" in full_text or "：" in full_text:
                sep = ":" if ":" in full_text else "："
                parts = full_text.split(sep, 1)
                speaker = parts[0].strip()
                text = parts[1].strip()

            dialogues.append(
                {
                    "start": start,
                    "end": end,
                    "text": text,
                    "speaker": speaker,
                    # [核心修复] 将原始文本存入 original_text
                    # 这里的逻辑可以根据需求调整，比如直接存 full_text，或者存未清洗的 text
                    "original_text": full_text,
                }
            )
        except Exception:
            continue

    return dialogues
