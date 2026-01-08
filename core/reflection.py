def reflect(results: list) -> bool:
    """
    判断执行是否成功
    """
    for r in results:
        if "error" in r:
            return False
    return True
