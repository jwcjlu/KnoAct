/// Mermaid 渲染用迷你 HTML 页（Web iframe / 移动端 WebView 共用）
String mermaidHtmlDocument(String code) {
  final safe = code.replaceAll('\\', '\\\\').replaceAll('`', '\\`').replaceAll(r'${', r'\${');
  return '''
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<script src="https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.min.js"></script>
<style>body{margin:0;padding:8px;background:#fff;font-family:sans-serif}svg{max-width:100%;height:auto}</style>
</head>
<body>
<div id="graph"></div>
<script>
const code = `$safe`;
function render() {
  const el = document.getElementById('graph');
  if (typeof mermaid === 'undefined') {
    el.textContent = code;
    return;
  }
  mermaid.initialize({ startOnLoad: false, theme: 'default' });
  mermaid.render('graph-' + Date.now(), code).then(({svg}) => {
    el.innerHTML = svg;
  }).catch(() => {
    el.textContent = code;
  });
}
render();
</script>
</body>
</html>
''';
}
