from html.parser import HTMLParser

class DOMCleaner(HTMLParser):
    def __init__(self):
        super().__init__()
        self.result = []
        self.ignore_tags = {"script", "style", "svg", "noscript", "iframe", "head"}
        self.ignore_depth = 0
        self.allowed_attrs = {"id", "class", "name", "type", "value", "placeholder", "href", "role", "aria-label", "title"}

    def handle_starttag(self, tag, attrs):
        if tag in self.ignore_tags:
            self.ignore_depth += 1
            return
        if self.ignore_depth > 0:
            return
        attr_str = ""
        for name, value in attrs:
            if name in self.allowed_attrs:
                attr_str += f' {name}="{value}"'
        self.result.append(f"<{tag}{attr_str}>")

    def handle_endtag(self, tag):
        if tag in self.ignore_tags:
            self.ignore_depth = max(0, self.ignore_depth - 1)
            return
        if self.ignore_depth > 0:
            return
        self.result.append(f"</{tag}>")

    def handle_data(self, data):
        if self.ignore_depth > 0:
            return
        text = data.strip()
        if text:
            self.result.append(text)

def clean_html(html_content: str) -> str:
    if not html_content:
        return ""
    parser = DOMCleaner()
    try:
        parser.feed(html_content)
        return "".join(parser.result)
    except Exception:
        # Fallback to simple slice of raw content if parser fails
        return html_content[:20000]
