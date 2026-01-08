def parse_intent(user_input: str) -> dict:
    """
    意图解析层：
    只判断用户想干什么，不做任何执行
    """

    if "电脑" in user_input or "设备" in user_input:
        return {"type": "system_info"}

    if "是什么" in user_input or "怎么" in user_input:
        return {"type": "research"}

    return {"type": "general"}
