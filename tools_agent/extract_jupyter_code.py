import nbformat
import os 

def extract_code_cells(notebook_path, output_path):
    # 打开并读取Jupyter Notebook文件
    with open(notebook_path, 'r', encoding='utf-8') as nb_file:
        notebook = nbformat.read(nb_file, as_version=4)

    # 提取所有代码单元格
    code_cells = []
    for cell in notebook.cells:
        if cell.cell_type == 'code':
            code_cells.append(cell.source)

    # 将提取的代码写入一个输出文件中
    with open(output_path, 'w', encoding='utf-8') as output_file:
        for code in code_cells:
            output_file.write(code + '\n\n')  # 每个代码块后添加两个换行

    print(f"所有代码已提取并保存至 {output_path}")
    return code_cells
