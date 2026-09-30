"""Small pieces of admin markup, styled by classes in static/admin/css/gabstep.css.

Nothing here carries a colour of its own. Colours live in the stylesheet, which
has a light and a dark version, so labels stay readable in both themes.
"""

from django.utils.html import format_html


def pill(text, tone="idle"):
    """A status label. tone: ok, wait, bad, info or idle."""
    return format_html('<span class="gs-pill gs-pill--{}">{}</span>', tone, text)


def muted(text):
    return format_html('<span class="gs-muted">{}</span>', text)


def button_link(url, text, primary=False, new_tab=False):
    return format_html(
        '<a class="gs-button{}" href="{}"{}>{}</a>',
        " gs-button--primary" if primary else "",
        url,
        format_html(' target="_blank" rel="noopener"') if new_tab else "",
        text,
    )


def plural(count, noun):
    return f"{count} {noun}{'' if count == 1 else 's'}"
