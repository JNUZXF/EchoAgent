import nbformat as nbf # pip install nbformat
import re


def text_to_jupyter(markdown_content, save_file_name):
    # Use regular expressions to separate code blocks and text
    pattern = r'```python([\s\S]*?)```|([\s\S]*?)(?=```python|$)'
    matches = re.findall(pattern, markdown_content)

    # Store the separated content
    separated_content = []

    for code, text in matches:
        if code:
            # 使用字符串的splitlines方法来分割代码，然后选择去掉第一行
            lines = code.splitlines()[1:]
            # 使用join方法将剩余的行重新组合成字符串
            code = '\n'.join(lines)
            separated_content.append({"type": "code", "content": code.strip()})
        elif text.strip():
            separated_content.append(
                {"type": "markdown", "content": text.strip()})

    # Create a new notebook
    nb = nbf.v4.new_notebook()

    # Loop through the separated content and add to the notebook
    for section in separated_content:
        if section["type"] == "markdown":
            # Add markdown cell
            nb.cells.append(nbf.v4.new_markdown_cell(section["content"]))
        elif section["type"] == "code":
            # Add code cell
            nb.cells.append(nbf.v4.new_code_cell(section["content"]))

    # Write notebook to file
    with open(f"{save_file_name}", "w", encoding="utf-8") as f:
        nbf.write(nb, f)


