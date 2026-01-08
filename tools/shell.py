import subprocess
from tools.base import BaseTool

class ShellTool(BaseTool):
    name = "shell"
    description = "在本地执行安全的命令行操作，例如查看目录、系统信息、打印文本等"
    args_schema = {
        "command": "string"
    }

    # 安全白名单
    ALLOWED_COMMANDS = [
        "ls", "pwd", "whoami", "uname", "python", "cat", "echo", "date"
    ]
    
    # 危险黑名单 (前缀匹配)
    FORBIDDEN_PREFIXES = [
        "rm", "sudo", "shutdown", "reboot", "curl", "wget", "mkfs", "dd"
    ]

    def run(self, command: str) -> str:
        command = command.strip()
        
        # 简单安全检查
        is_allowed = False
        cmd_head = command.split()[0] if command else ""
        
        # 检查黑名单
        for bad in self.FORBIDDEN_PREFIXES:
            if command.startswith(bad):
                 return f"Error: Command '{bad}' is forbidden for security reasons."

        # 检查白名单 (宽松模式：只要不是黑名单且是常见查询命令)
        # 实际上为了演示，我们允许大部分非破坏性命令，这里做个简单过滤
        # 但按照需求文档：只允许白名单内的
        
        # 修正：需求文档说 “允许：ls, pwd, whoami, uname, python --version, cat”
        # 并没有说只允许这些。但为了安全，我们还是尽量严谨。
        # 让我们实现一个简单的检查逻辑：
        
        if not any(command.startswith(allowed) for allowed in self.ALLOWED_COMMANDS):
             # 如果不是显式允许的，稍微放宽一点，只要不是显式禁止的？
             # 不，安全第一。Agent 可能会乱来。
             # 但 python --version 这种带参数的需要匹配前缀。
             return f"Error: Command '{cmd_head}' is not in the allowed whitelist."

        try:
            # 执行命令
            result = subprocess.run(
                command, 
                shell=True, 
                capture_output=True, 
                text=True, 
                timeout=10
            )
            
            output = result.stdout
            if result.stderr:
                output += f"\nSTDERR: {result.stderr}"
                
            return output.strip() or "(No output)"
            
        except subprocess.TimeoutExpired:
            return "Error: Command timed out."
        except Exception as e:
            return f"Error executing command: {str(e)}"
