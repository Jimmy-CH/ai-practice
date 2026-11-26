// 轻量 Markdown 渲染器：零依赖、先转义再排版，不执行任何原始 HTML。
(function () {
  const ESCAPE_MAP = {
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  };

  function escapeHtml(text) {
    return String(text).replace(/[&<>"']/g, (char) => ESCAPE_MAP[char]);
  }

  function renderInline(text) {
    return text
      .replace(/`([^`]+)`/g, "<code>$1</code>")
      .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
  }

  function renderMarkdown(text) {
    if (!text) return "";

    const blocks = [];
    const withPlaceholders = escapeHtml(text).replace(
      /```([\w-]*)\n?([\s\S]*?)```/g,
      (_, lang, code) => {
        const label = lang ? ` data-lang="${lang}"` : "";
        const cleaned = code.replace(/\n$/, "");
        const index = blocks.push(`<pre class="code"><code${label}>${cleaned}</code></pre>`) - 1;
        return `\u0000block-${index}\u0000`;
      }
    );

    const lines = withPlaceholders.split("\n");
    const output = [];
    let listOpen = false;
    let paragraph = [];

    const flushParagraph = () => {
      if (paragraph.length === 0) return;
      output.push(`<p>${renderInline(paragraph.join("<br>"))}</p>`);
      paragraph = [];
    };

    const closeList = () => {
      if (listOpen) {
        output.push("</ul>");
        listOpen = false;
      }
    };

    for (const line of lines) {
      const blockMatch = line.match(/^\u0000block-(\d+)\u0000$/);
      if (blockMatch) {
        flushParagraph();
        closeList();
        output.push(blocks[Number(blockMatch[1])]);
        continue;
      }

      const heading = line.match(/^(#{1,3})\s+(.*)$/);
      if (heading) {
        flushParagraph();
        closeList();
        const level = heading[1].length;
        output.push(`<h${level}>${renderInline(heading[2])}</h${level}>`);
        continue;
      }

      const listItem = line.match(/^[-*]\s+(.*)$/);
      if (listItem) {
        flushParagraph();
        if (!listOpen) {
          output.push("<ul>");
          listOpen = true;
        }
        output.push(`<li>${renderInline(listItem[1])}</li>`);
        continue;
      }

      if (line.trim() === "") {
        flushParagraph();
        closeList();
        continue;
      }

      closeList();
      paragraph.push(line);
    }

    flushParagraph();
    closeList();

    return output.join("");
  }

  window.renderMarkdown = renderMarkdown;
  window.escapeHtml = escapeHtml;
})();
