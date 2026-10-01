from html import escape
from typing import List, Optional


def render_email_template(
    title: str,
    paragraphs: List[str],
    action_label: Optional[str] = None,
    action_url: Optional[str] = None,
    code: Optional[str] = None,
    security_notice: Optional[str] = None,
) -> str:
    paragraph_html = "".join(
        f'<p style="margin:0 0 16px;color:#334155;line-height:1.6">'
        f'{escape(paragraph).replace(chr(10), "<br>")}</p>'
        for paragraph in paragraphs
    )
    code_html = ""
    if code:
        code_html = (
            '<p style="margin:24px 0;padding:16px;background:#f1f5f9;'
            'font-size:28px;font-weight:700;letter-spacing:4px;text-align:center;'
            f'color:#0f172a">{escape(code)}</p>'
        )
    action_html = ""
    if action_label and action_url:
        action_html = (
            '<p style="margin:24px 0"><a '
            f'href="{escape(action_url, quote=True)}" '
            'style="display:inline-block;padding:12px 20px;background:#0f766e;'
            'border-radius:4px;color:#ffffff;text-decoration:none;font-weight:600">'
            f'{escape(action_label)}</a></p>'
        )
    notice_html = ""
    if security_notice:
        notice_html = (
            '<p style="margin:24px 0 0;padding-top:16px;border-top:1px solid #e2e8f0;'
            'color:#64748b;font-size:13px;line-height:1.5">'
            f'{escape(security_notice)}</p>'
        )

    return (
        '<!doctype html><html><body style="margin:0;background:#f8fafc;'
        'font-family:Arial,sans-serif;color:#0f172a">'
        '<table role="presentation" width="100%" cellspacing="0" cellpadding="0">'
        '<tr><td align="center" style="padding:32px 16px">'
        '<table role="presentation" width="100%" cellspacing="0" cellpadding="0" '
        'style="max-width:600px;background:#ffffff;border:1px solid #e2e8f0">'
        '<tr><td style="padding:24px 28px;background:#0f766e;color:#ffffff;'
        'font-size:18px;font-weight:700">IntelliBusiness</td></tr>'
        '<tr><td style="padding:28px">'
        f'<h1 style="margin:0 0 20px;font-size:22px">{escape(title)}</h1>'
        f'{paragraph_html}{code_html}{action_html}{notice_html}'
        '</td></tr><tr><td style="padding:16px 28px;background:#f8fafc;'
        'color:#64748b;font-size:12px">IntelliBusiness account security</td></tr>'
        '</table></td></tr></table></body></html>'
    )