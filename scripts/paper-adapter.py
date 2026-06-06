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
    """生成公众号内联样式 HTML — 可直接粘贴到公众号后台"""
    css = {
        'h1': 'font-size:22px;font-weight:bold;color:#2c3e50;text-align:center;margin:20px 0 15px;line-height:1.4;',
        'h2': 'font-size:18px;font-weight:bold;color:#2c3e50;margin:24px 0 12px;padding-left:12px;border-left:4px solid #3498db;line-height:1.5;',
        'p': 'font-size:15px;color:#333;line-height:1.85;margin:10px 0;letter-spacing:0.5px;',
        'quote': 'font-size:14px;color:#666;line-height:1.8;margin:12px 0;padding:10px 16px;background:#f8f9fa;border-left:3px solid #3498db;border-radius:0 4px 4px 0;',
        'list': 'font-size:15px;color:#333;line-height:1.85;margin:6px 0;',
        'table': 'border-collapse:collapse;width:100%;margin:12px 0;font-size:14px;',
        'th': 'background:#2c3e50;color:#fff;padding:8px 12px;text-align:left;font-weight:bold;',
        'td': 'border-bottom:1px solid #e0e0e0;padding:8px 12px;color:#333;',
        'ref': 'font-size:13px;color:#999;line-height:1.6;margin:20px 0 10px;padding:10px;background:#f5f5f5;border-radius:4px;',
        'divider': 'text-align:center;color:#ccc;margin:20px 0;font-size:14px;letter-spacing:8px;',
    }

    def tag(t, style_key, text):
        return f'<{t} style="{css[style_key]}">{text}</{t}>'

    def p(text):
        return tag('p', 'p', text) if text.strip() else ''

    body = []

    body.append(tag('h1', 'h1', data['title']))

    oneliner = clean_md(data['oneliner'])
    oneliner = re.sub(r'^.{0,6}亮点[：:]\s*', '', oneliner)
    body.append(tag('blockquote', 'quote', oneliner))
    body.append(tag('p', 'divider', '· · ·'))

    body.append(tag('h2', 'h2', '🎯 我们在问什么问题'))
    for line in data['problem'].strip().split('\n'):
        line = line.strip()
        if not line:
            continue
        line = clean_md(line)
        body.append(p(line))

    body.append(tag('h2', 'h2', '🔬 方法概要'))
    for line in data['method'].strip().split('\n'):
        line = line.strip()
        if not line:
            continue
        line = clean_md(line)
        if line.startswith('- ') or line.startswith('* '):
            body.append(tag('p', 'list', '  ' + line))
        else:
            body.append(p(line))

    body.append(tag('h2', 'h2', '📊 关键数据'))
    results = data['results']
    table_rows = re.findall(r'\|\s*(.+?)\s*\|\s*(.+?)\s*\|', results)
    if table_rows:
        data_rows = [r for r in table_rows if not re.match(r'[-:\s|]+', r[0]) and '发现' not in r[0]]
        body.append(f'<table style="{css["table"]}">')
        body.append(f'<tr><th style="{css["th"]}">发现</th><th style="{css["th"]}">数据</th></tr>')
        for desc, val in data_rows:
            body.append(f'<tr><td style="{css["td"]}">{desc.strip()}</td><td style="{css["td"]}">{val.strip()}</td></tr>')
        body.append('</table>')
    for line in results.strip().split('\n'):
        if '|' in line and '-' in line:
            continue
        line = clean_md(line.strip())
        if line and '|' not in line:
            body.append(p(line))

    body.append(tag('h2', 'h2', '💡 读后感和碎碎念'))
    for line in data['insight'].strip().split('\n'):
        line = line.strip()
        if not line:
            continue
        line = clean_md(line)
        if line.startswith('**') and '**' in line[2:]:
            bold_end = line.index('**', 2)
            bold_text = line[2:bold_end]
            rest = line[bold_end+2:].strip()
            body.append(tag('p', 'p', f'<strong style="color:#2c3e50;">{bold_text}</strong> {rest}'))
        else:
            body.append(p(line))

    body.append(tag('p', 'divider', '· · ·'))
    ref_text = f'📎 Aayush Gupta et al. "ReliabilityBench: Evaluating LLM Agent Reliability Under Production-Like Stress Conditions." arXiv:2601.06112, Jan 2026.<br>完整分析 & 论文原文：github.com/yanxi1024-git/ai-paper-daily'
    body.append(tag('p', 'ref', ref_text))
    body.append(tag('p', 'p', '<span style="color:#3498db;">#和Andrew一起读论文</span>  <span style="color:#999;">#AI论文解读</span>  <span style="color:#999;">#AI可靠性</span>'))

    body_html = '\n'.join(body)

    # 包装成一个自包含页面，带一键复制按钮
    return f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{data['title']}</title>
<style>
body {{ font-family: -apple-system,"PingFang SC","Microsoft YaHei",sans-serif; max-width:680px; margin:0 auto; padding:20px; }}
.toolbar {{ position:sticky; top:0; background:#fff; padding:12px 0; border-bottom:1px solid #eee; margin-bottom:20px; z-index:10; }}
.btn {{ display:inline-block; padding:10px 24px; background:#2c3e50; color:#fff; border:none; border-radius:6px; font-size:15px; cursor:pointer; margin-right:10px; }}
.btn:hover {{ background:#3498db; }}
.msg {{ display:inline-block; margin-left:12px; font-size:14px; color:#27ae60; opacity:0; transition:opacity 0.3s; }}
.msg.show {{ opacity:1; }}
</style>
</head>
<body>
<div class="toolbar">
  <button class="btn" onclick="copyToWechat()">📋 一键复制到公众号</button>
  <span class="msg" id="msg">✅ 已复制！去公众号后台 Ctrl+V 粘贴</span>
</div>
<div id="content">
{body_html}
</div>
<script>
function copyToWechat() {{
  const content = document.getElementById('content');
  const range = document.createRange();
  range.selectNodeContents(content);
  const sel = window.getSelection();
  sel.removeAllRanges();
  sel.addRange(range);
  document.execCommand('copy');
  sel.removeAllRanges();
  const msg = document.getElementById('msg');
  msg.classList.add('show');
  setTimeout(() => msg.classList.remove('show'), 3000);
}}
</script>
</body>
</html>'''


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
    wc_content = to_wechat(data)

    # 写入文件
    (x_dir / f'{stem}.txt').write_text(x_content)
    (mol_dir / f'{stem}.txt').write_text(mol_content)
    (wc_dir / f'{stem}.html').write_text(wc_content)

    print(f"✅ 已生成多平台版本：")
    print(f"   X 长文:      output/x/{stem}.txt")
    print(f"   Moltbook:    output/moltbook/{stem}.txt")
    print(f"   公众号:       output/wechat/{stem}.html")


if __name__ == '__main__':
    main()
