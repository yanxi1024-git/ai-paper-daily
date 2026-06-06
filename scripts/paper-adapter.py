#!/usr/bin/env python3
"""
AI Paper Daily — 多平台适配器 (Paper Adapter)

一份 Markdown 源文件 → 自动生成各平台版本：
  - X (Twitter) 线程
  - Moltbook 社区版
  - 公众号 HTML（调用 wechat-editor）

用法：
  python3 paper-adapter.py analyses/2026/06/2026-06-06-reliabilitybench.md

输出：
  output/x/2026-06-06-reliabilitybench.txt      # X 线程
  output/moltbook/2026-06-06-reliabilitybench.txt  # Moltbook
  output/wechat/2026-06-06-reliabilitybench.html   # 公众号
"""

import re
import sys
import os
from pathlib import Path

# ── 解析 Markdown 分析文章 ──────────────────────────────────

def parse_markdown(filepath):
    """解析分析文章，提取各段落。
    支持两种格式：
    - 结构化格式（## 🎯/🔬/📊/💡 emoji 标题）
    - 自由格式（## 普通标题，按位置识别）
    """
    with open(filepath, 'r') as f:
        content = f.read()

    result = {
        'title': '',
        'oneliner': '',
        'problem': '',
        'method': '',
        'results': '',
        'insight': '',
        'paper_info': {},
        'arxiv_url': '',
        'date': '',
    }

    # 标题
    m = re.search(r'^# (.+)$', content, re.MULTILINE)
    if m:
        result['title'] = m.group(1).strip()

    # 一句话亮点
    m = re.search(r'> 📌 (.+)$', content, re.MULTILINE)
    if m:
        result['oneliner'] = m.group(1).strip()

    # 提取所有 ## 段落
    h2_sections = re.findall(r'## (.+?)\n\n(.+?)(?=\n## |\n---|\n\*arXiv)', content, re.DOTALL)
    # 也处理末尾 ## 没有后续段落的情况
    if not h2_sections:
        parts = re.split(r'\n## ', content)
        h2_sections = []
        for p in parts[1:]:
            lines = p.split('\n', 1)
            title = lines[0].strip()
            body = lines[1].strip() if len(lines) > 1 else ''
            h2_sections.append((title, body))

    # 按 emoji 或位置分配
    emoji_map = {
        '🎯': 'problem', '🔬': 'method', '📊': 'results', '💡': 'insight',
        '📎': 'paper_info',
    }
    position_map = ['problem', 'method', 'results', 'insight']
    pos_idx = 0

    for title, body in h2_sections:
        matched = False
        for emoji, key in emoji_map.items():
            if title.startswith(emoji):
                if key == 'paper_info':
                    result['paper_info']['raw'] = body
                else:
                    result[key] = body.strip()
                matched = True
                break
        if not matched and pos_idx < len(position_map):
            result[position_map[pos_idx]] = body.strip()
            pos_idx += 1

    # 从正文中提取 arXiv 链接
    m = re.search(r'arXiv.*?\[(\d+\.\d+)\]', content)
    if m:
        result['arxiv_url'] = f"https://arxiv.org/abs/{m.group(1)}"
        result['paper_info']['arxiv_id'] = m.group(1)

    # 日期
    m = re.search(r'(\d{4}-\d{2}-\d{2})', str(filepath))
    if m:
        result['date'] = m.group(1)

    return result


# ── 平台适配器 ───────────────────────────────────────────────

def clean_md(text):
    """去除 Markdown 标记，返回纯文本"""
    text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)
    text = re.sub(r'\*([^*]+)\*', r'\1', text)
    text = re.sub(r'`([^`]+)`', r'\1', text)
    text = re.sub(r'>\s*', '', text)
    text = re.sub(r'###+\s*', '', text)
    text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def extract_sentences(text, max_sentences=3):
    """从文本中提取干净的句子，过滤标题和太短的碎片"""
    text = clean_md(text)
    raw = []
    for s in re.split(r'[。！\n]', text):
        s = s.strip()
        # 跳过标题式片段和太短的
        if len(s) < 10:
            continue
        if re.match(r'^[一二三四五六七八九十\d]+[.、]', s):
            continue
        if '维度' in s and len(s) < 30:
            continue
        raw.append(s)
    return raw[:max_sentences]


def trim_tweet(text, max_len=270):
    """截断到 X 允许的长度"""
    if len(text) <= max_len:
        return text
    return text[:max_len-3] + '...'


def to_x_long(data):
    """生成 X 长文（X Premium，最长 25,000 字符）"""
    lines = []
    url = data.get('arxiv_url', '')

    lines.append(data['title'])
    lines.append('')

    oneliner = clean_md(data['oneliner'])
    oneliner = re.sub(r'^.{0,6}亮点[：:]\s*', '', oneliner)
    lines.append(oneliner)
    lines.append('')
    lines.append('—' * 20)
    lines.append('')

    lines.append(clean_md(data['problem']))
    lines.append('')

    lines.append(clean_md(data['method']))
    lines.append('')

    # 关键结果 — 表格转列表
    results = data['results']
    # 将 markdown 表格转为纯文本列表
    table_rows = re.findall(r'\|\s*(.+?)\s*\|\s*(.+?)\s*\|', results)
    if table_rows:
        # 过滤掉表头
        data_rows = [r for r in table_rows if not re.match(r'[-:\s|]+', r[0]) and '发现' not in r[0]]
        items = []
        for desc, val in data_rows:
            items.append(f'• {desc.strip()}：{val.strip()}')
        results = '\n'.join(items) if items else clean_md(results)
    else:
        results = clean_md(results)
    results = re.sub(r'\|.*\|.*\|', '', results)
    results = re.sub(r'\n{3,}', '\n\n', results)
    lines.append(results)
    lines.append('')

    lines.append(clean_md(data['insight']))
    lines.append('')
    lines.append('—' * 20)
    lines.append('')
    lines.append('#和Andrew一起读论文  #AI论文解读  #AI可靠性')
    lines.append('')
    # 参考文献格式，不含外部链接
    lines.append('📎 Aayush Gupta et al. "ReliabilityBench: Evaluating LLM Agent')
    lines.append('   Reliability Under Production-Like Stress Conditions."')
    lines.append('   arXiv:2601.06112, Jan 2026.')
    lines.append('🐉 和 Andrew 一起读论文')

    return '\n'.join(lines)


def to_moltbook(data):
    """生成 Moltbook 社区版（中文，无 Markdown 表格）"""
    lines = []
    lines.append(f"📄 {data['title']}")
    lines.append('')
    lines.append(f"📌 {clean_md(data['oneliner']).replace('一句话亮点：', '').replace('**一句话亮点**：', '')}")
    lines.append('')

    # 问题
    lines.append('🎯 解决了什么问题？')
    lines.append(clean_md(data['problem']))
    lines.append('')

    # 方法
    lines.append('🔬 方法概要')
    lines.append(clean_md(data['method']).replace('|', '·'))
    lines.append('')

    # 关键结果
    lines.append('📊 关键结果')
    results = data['results']
    results = re.sub(r'\|.*\|.*\|', '', results)
    results = re.sub(r'\n{3,}', '\n\n', results)
    lines.append(clean_md(results))
    lines.append('')

    # 为什么值得关注
    lines.append('💡 为什么值得关注')
    lines.append(clean_md(data['insight']).replace('|', '·'))
    lines.append('')
    lines.append('━━━━━━━━━━━━━━━━━━━')
    lines.append('📎 论文原文 & 深度分析：')

    url = data.get('arxiv_url', '')
    if url:
        lines.append(f'{url}')
    lines.append(f'github.com/yanxi1024-git/ai-paper-daily')

    return '\n'.join(lines)


def to_wechat(data):
    """生成公众号 Markdown（配合 mdnice.com 或 pandoc→docx 使用）"""
    lines = []
    lines.append(f"# {data['title']}")
    lines.append('')
    lines.append(f"> 📌 {data['oneliner']}")
    lines.append('')
    lines.append('## 🎯 我们在问什么问题')
    lines.append(data['problem'])
    lines.append('')
    lines.append('## 🔬 方法概要')
    lines.append(data['method'])
    lines.append('')
    lines.append('## 📊 关键数据')
    lines.append(data['results'])
    lines.append('')
    lines.append('## 💡 读后感和碎碎念')
    lines.append(data['insight'])
    lines.append('')
    lines.append('---')
    lines.append(f'📎 **论文原文**：{data.get("arxiv_url", "")}')
    lines.append('')
    lines.append('#和Andrew一起读论文 #AI论文解读 #AI可靠性')
    return '\n'.join(lines)


def to_wechat_docx(data, output_path):
    """生成公众号 .docx 文件 — 可直接导入公众号后台"""
    from docx import Document
    from docx.shared import Pt, Inches, Cm, RGBColor
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.oxml.ns import qn

    doc = Document()

    # 页面设置
    section = doc.sections[0]
    section.page_width = Cm(17)
    section.page_height = Cm(24)
    section.left_margin = Cm(1.5)
    section.right_margin = Cm(1.5)

    # 颜色
    DARK = RGBColor(0x2C, 0x3E, 0x50)
    BLUE = RGBColor(0x34, 0x98, 0xDB)
    GRAY = RGBColor(0x66, 0x66, 0x66)
    BODY = RGBColor(0x33, 0x33, 0x33)
    LIGHT_GRAY = RGBColor(0x99, 0x99, 0x99)

    def add_h1(text):
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.space_after = Pt(12)
        run = p.add_run(text)
        run.bold = True
        run.font.size = Pt(20)
        run.font.color.rgb = DARK

    def add_h2(text):
        p = doc.add_paragraph()
        p.space_before = Pt(20)
        p.space_after = Pt(8)
        run = p.add_run(text)
        run.bold = True
        run.font.size = Pt(15)
        run.font.color.rgb = DARK

    def add_body(text):
        if not text.strip():
            return
        p = doc.add_paragraph()
        p.space_after = Pt(6)
        run = p.add_run(text)
        run.font.size = Pt(11)
        run.font.color.rgb = BODY
        p.paragraph_format.line_spacing = 1.8

    def add_quote(text):
        p = doc.add_paragraph()
        p.space_after = Pt(8)
        p.paragraph_format.left_indent = Cm(0.8)
        run = p.add_run(text)
        run.font.size = Pt(10)
        run.font.color.rgb = GRAY
        run.italic = True

    def add_divider():
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.space_before = Pt(12)
        p.space_after = Pt(12)
        run = p.add_run('· · ·')
        run.font.size = Pt(10)
        run.font.color.rgb = LIGHT_GRAY

    def add_ref(text):
        p = doc.add_paragraph()
        p.space_before = Pt(16)
        run = p.add_run(text)
        run.font.size = Pt(9)
        run.font.color.rgb = LIGHT_GRAY

    # 标题
    add_h1(data['title'])

    # 亮点
    oneliner = clean_md(data['oneliner'])
    oneliner = re.sub(r'^.{0,6}亮点[：:]\s*', '', oneliner)
    add_quote(oneliner)
    add_divider()

    # 各节
    add_h2('🎯 我们在问什么问题')
    for line in data['problem'].strip().split('\n'):
        line = clean_md(line.strip())
        if line:
            add_body(line)

    add_h2('🔬 方法概要')
    for line in data['method'].strip().split('\n'):
        line = clean_md(line.strip())
        if line:
            add_body(line)

    add_h2('📊 关键数据')
    results = data['results']
    # 表格 → docx 表格
    table_rows = re.findall(r'\|\s*(.+?)\s*\|\s*(.+?)\s*\|', results)
    if table_rows:
        data_rows = [r for r in table_rows if not re.match(r'[-:\s|]+', r[0]) and '发现' not in r[0]]
        table = doc.add_table(rows=1 + len(data_rows), cols=2)
        table.style = 'Light Grid Accent 1'
        # 表头
        hdr = table.rows[0].cells
        hdr[0].text = '发现'
        hdr[1].text = '数据'
        for cell in hdr:
            for p in cell.paragraphs:
                for run in p.runs:
                    run.bold = True
                    run.font.size = Pt(10)
        # 数据行
        for i, (desc, val) in enumerate(data_rows):
            row = table.rows[i + 1].cells
            row[0].text = desc.strip()
            row[1].text = val.strip()
            for cell in row:
                for p in cell.paragraphs:
                    for run in p.runs:
                        run.font.size = Pt(10)
    # 表格后文本
    for line in results.strip().split('\n'):
        line = clean_md(line.strip())
        if line and '|' not in line:
            add_body(line)

    add_h2('💡 读后感和碎碎念')
    for line in data['insight'].strip().split('\n'):
        line = clean_md(line.strip())
        if line:
            add_body(line)

    add_divider()
    url = data.get('arxiv_url', '')
    add_ref(f'Aayush Gupta et al. "ReliabilityBench: Evaluating LLM Agent Reliability Under Production-Like Stress Conditions." arXiv:2601.06112, Jan 2026.\n完整分析 & 论文原文：github.com/yanxi1024-git/ai-paper-daily')

    doc.save(output_path)
    return output_path


# ── 主流程 ───────────────────────────────────────────────────

def main():
    if len(sys.argv) < 2:
        print("用法: python3 paper-adapter.py <analysis.md>")
        sys.exit(1)

    input_file = sys.argv[1]
    data = parse_markdown(input_file)

    # 输出目录
    stem = Path(input_file).stem  # e.g. 2026-06-06-reliabilitybench
    out_dir = Path('output')
    out_dir.mkdir(exist_ok=True)

    x_dir = out_dir / 'x'
    mol_dir = out_dir / 'moltbook'
    wc_dir = out_dir / 'wechat'
    for d in [x_dir, mol_dir, wc_dir]:
        d.mkdir(exist_ok=True)

    # 生成各平台版本
    x_content = to_x_long(data)
    mol_content = to_moltbook(data)
    wc_md = to_wechat(data)

    (x_dir / f'{stem}.txt').write_text(x_content)
    (mol_dir / f'{stem}.txt').write_text(mol_content)
    (wc_dir / f'{stem}.md').write_text(wc_md)
    docx_path = str(wc_dir / f'{stem}.docx')
    to_wechat_docx(data, docx_path)

    print(f"✅ 已生成多平台版本：")
    print(f"   X 长文:      output/x/{stem}.txt")
    print(f"   Moltbook:    output/moltbook/{stem}.txt")
    print(f"   公众号 MD:    output/wechat/{stem}.md")
    print(f"   公众号 DOCX:  output/wechat/{stem}.docx")


if __name__ == '__main__':
    main()
