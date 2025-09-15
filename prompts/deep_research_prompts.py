

from textwrap import dedent


SELECT_PROMPT = dedent("""
    请你根据我的需求，判断我下面检索到的信息哪些是有价值的，然后以markdown形式输出你筛选后的结果。
    (格式参考下方的<示例输出>里的内容)

    <示例输出>
    # 标题1
    内容
    [链接](url)

    # 标题2
    内容
    [链接](url)

    # 标题3
    内容
    [链接](url)
    </示例输出>
    
    # 我的需求
    {question}

    # 检索到的信息
    {result}
 
    # 注意
    - 你仅需要输出有价值的符合我的需求的内容
    - 你的输出必须是markdown样式，包括链接也是markdown格式。
        - 图片格式：![图片描述](图片链接) ； 示例：![一只猫](https://img.yzcdn.cn/vant/cat.jpeg)
        - 链接格式：[文本标题](链接) ； 示例：[今日天气](https://www.weather.com.cn/)
    
""").strip()








