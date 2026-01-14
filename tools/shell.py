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
        "ls", "pwd", "whoami", "uname", "python", "cat", "echo", "date",
        "mkdir", "touch", "cp", "mv", "grep", "find", "head", "tail", "wc"
    ]
    
    # 危险黑名单 (前缀匹配)
    FORBIDDEN_PREFIXES = [
        "rm", "sudo", "shutdown", "reboot", "curl", "wget", "mkfs", "dd",
        ":(){ :|:& };:" # Fork bomb
    ]

    def run(self, command: str) -> str:
        command = command.strip()
        
        # 简单安全检查
        cmd_head = command.split()[0] if command else ""
        
        # 1. 优先检查黑名单 (Explicit Deny)
        for bad in self.FORBIDDEN_PREFIXES:
            # 检查命令开头，防止 rm -rf
            # 也要防止 ; rm -rf 这种多命令注入 (简单起见，暂不处理复杂 shell 解析，假设 Agent 比较规矩)
            if command.startswith(bad):
                 return f"Error: Command '{bad}' is forbidden for security reasons."

        # 2. 检查白名单 (Explicit Allow)
        if not any(command.startswith(allowed) for allowed in self.ALLOWED_COMMANDS):
             return f"Error: Command '{cmd_head}' is not in the allowed whitelist. Allowed: {', '.join(self.ALLOWED_COMMANDS)}"

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
